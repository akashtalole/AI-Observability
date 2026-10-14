"""Minimal, runnable OpenTelemetry instrumentation for a RAG request.

Emits: stage spans (retrieve / rerank / generate), gen_ai.* + rag.* + app.* attributes,
and metrics (request count, latency, TTFT, tokens, cost) that match examples/alerts/ai-slo-alerts.yml.
No API keys needed: retrieval and generation are stubbed. Swap the exporters for OTLP in production:
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python instrument.py

    pip install opentelemetry-sdk
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

# Versioned price table owned by YOU (USD per 1M tokens). Never infer prices from a vendor UI.
PRICE_TABLE_VERSION = "2026-10"
PRICES = {"example-large": {"in": 3.00, "out": 15.00}, "example-small": {"in": 0.25, "out": 1.25}}

resource = Resource.create({"service.name": "support-rag", "deployment.environment": "dev"})
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)
metrics.set_meter_provider(
    MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=5000)],
    )
)

tracer = trace.get_tracer("rag.app")
meter = metrics.get_meter("rag.app")
requests_total = meter.create_counter("rag_requests_total")
duration = meter.create_histogram("rag_request_duration_seconds", unit="s")
ttft = meter.create_histogram("rag_ttft_seconds", unit="s")
tokens = meter.create_counter("rag_tokens_total")
cost = meter.create_counter("rag_cost_usd_total", unit="USD")
empty_retrieval = meter.create_counter("rag_retrieval_empty_total")


@dataclass
class Config:
    app: str = "support-rag"
    feature: str = "faq"
    tenant: str = "acme"
    model: str = "example-large"
    prompt_id: str = "faq-answer"
    prompt_version: str = "v7"
    index_version: str = "2026-10-01"
    embedding_model: str = "example-embed-1"
    top_k: int = 5


def retrieve(query: str, cfg: Config) -> list[dict]:
    with tracer.start_as_current_span("rag.retrieve") as span:
        span.set_attribute("rag.retrieval.top_k", cfg.top_k)
        span.set_attribute("rag.index.version", cfg.index_version)
        span.set_attribute("rag.embedding.model", cfg.embedding_model)
        time.sleep(random.uniform(0.02, 0.08))  # stand-in for embed + vector search
        chunks = [{"doc_id": f"doc-{i}", "score": round(random.uniform(0.3, 0.9), 2)} for i in range(cfg.top_k)]
        span.set_attribute("rag.retrieval.count", len(chunks))
        span.set_attribute("rag.retrieval.top1_score", max(c["score"] for c in chunks))
        # IDs and scores only. Chunk text stays out of telemetry unless sampled and redacted.
        span.set_attribute("rag.context.doc_ids", [c["doc_id"] for c in chunks])
        return chunks


def generate(query: str, chunks: list[dict], cfg: Config) -> dict:
    with tracer.start_as_current_span(f"chat {cfg.model}") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", cfg.model)
        span.set_attribute("app.prompt.id", cfg.prompt_id)
        span.set_attribute("app.prompt.version", cfg.prompt_version)
        start = time.perf_counter()
        time.sleep(random.uniform(0.15, 0.4))  # time to first token
        first = time.perf_counter() - start
        time.sleep(random.uniform(0.2, 0.6))  # decoding
        usage = {"in": 900 + 150 * len(chunks), "out": random.randint(120, 400)}
        span.set_attribute("gen_ai.response.model", cfg.model)
        span.set_attribute("gen_ai.usage.input_tokens", usage["in"])
        span.set_attribute("gen_ai.usage.output_tokens", usage["out"])
        span.set_attribute("gen_ai.response.finish_reasons", ["stop"])
        span.set_attribute("app.ttft_ms", first * 1000)
        return {"text": "stub answer", "usage": usage, "ttft_s": first}


def answer(query: str, cfg: Config) -> str:
    dims = {"app.feature": cfg.feature, "gen_ai.request.model": cfg.model,
            "app.prompt.version": cfg.prompt_version, "rag.index.version": cfg.index_version}
    start = time.perf_counter()
    with tracer.start_as_current_span("rag.request") as root:
        root.set_attribute("app.tenant.id", cfg.tenant)
        root.set_attribute("app.feature", cfg.feature)
        root.set_attribute("app.environment", "dev")
        root.set_attribute("app.price_table.version", PRICE_TABLE_VERSION)
        root.set_attribute("app.query.length", len(query))  # length/hash, not the text
        status = "ok"
        try:
            chunks = retrieve(query, cfg)
            if not chunks:
                empty_retrieval.add(1, dims)
            result = generate(query, chunks, cfg)
            p = PRICES[cfg.model]
            usd = (result["usage"]["in"] * p["in"] + result["usage"]["out"] * p["out"]) / 1_000_000
            root.set_attribute("cost.usd.total", usd)
            tokens.add(result["usage"]["in"], {**dims, "direction": "input"})
            tokens.add(result["usage"]["out"], {**dims, "direction": "output"})
            cost.add(usd, dims)
            ttft.record(result["ttft_s"], dims)
            return result["text"]
        except Exception as exc:  # noqa: BLE001 - record then re-raise
            status = "error"
            root.record_exception(exc)
            root.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        finally:
            elapsed = time.perf_counter() - start
            requests_total.add(1, {**dims, "status": status})
            duration.record(elapsed, dims)


if __name__ == "__main__":
    cfg = Config()
    for q in ["How do I reset my password?", "What is the refund policy?", "Where is my invoice?"]:
        answer(q, cfg)
    tracer_provider.force_flush()
    time.sleep(0.5)
