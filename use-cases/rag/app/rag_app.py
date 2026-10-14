#!/usr/bin/env python3
"""Simulated enterprise RAG service instrumented with OpenTelemetry (traces + metrics + logs).

Run against the stack (see use-cases/stack):
    python use-cases/rag/app/rag_app.py --rps 3 --cycle 240
Run standalone (print telemetry, no stack):
    python use-cases/rag/app/rag_app.py --console --duration 10

--cycle N rotates through failure scenarios every N seconds so every dashboard panel and alert has something to show:
    normal -> slow-llm -> bad-index -> cost-spike -> provider-errors -> normal ...
Or pin one with --scenario NAME.

Model, vector DB and judge calls are simulated; there are no external dependencies or API keys.
Telemetry carries IDs, lengths, scores and versions only - never prompt or answer text.
"""
from __future__ import annotations

import argparse
import itertools
import queue
import random
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from telemetry import setup  # noqa: E402

from opentelemetry import trace  # noqa: E402
from opentelemetry.metrics import Observation  # noqa: E402
from opentelemetry.trace import SpanKind, Status, StatusCode  # noqa: E402

APP = "support-rag"
# Versioned price table (USD per 1M tokens) - owned by you, never inferred from a vendor UI.
PRICE_TABLE_VERSION = "2026-10"
PRICES = {"large-model": (3.00, 15.00), "small-model": (0.25, 1.25), "embed-model": (0.02, 0.0)}
TENANTS = ["acme", "globex", "initech"]
FEATURES = ["faq", "policy-search", "troubleshooting"]


@dataclass
class Scenario:
    name: str
    llm_mult: float = 1.0        # LLM latency multiplier
    retr_mult: float = 1.0       # retrieval latency multiplier
    error_rate: float = 0.01     # provider error probability per call
    quality_shift: float = 0.0   # added to groundedness / relevance
    top1_shift: float = 0.0      # added to top-1 similarity
    empty_rate: float = 0.01     # probability retrieval returns nothing
    ctx_mult: float = 1.0        # context size multiplier
    index_age_h: float = 3.0     # index staleness in hours
    description: str = ""


SCENARIOS = {s.name: s for s in [
    Scenario("normal", description="healthy baseline"),
    Scenario("slow-llm", llm_mult=3.2, description="provider latency degradation -> TTFT / p95 alerts"),
    Scenario("bad-index", quality_shift=-0.22, top1_shift=-0.30, empty_rate=0.12, index_age_h=60,
             description="bad reindex / stale index -> retrieval + quality regression"),
    Scenario("cost-spike", ctx_mult=4.5, description="context bloat -> cost per request spike"),
    Scenario("provider-errors", error_rate=0.50, llm_mult=1.4, description="429/5xx storm -> retries, fallbacks, errors"),
]}
CURRENT = {"s": SCENARIOS["normal"]}


class Providers:
    """Thin instrument set; names follow OTel dotted style and become rag_* in Prometheus."""

    def __init__(self, meter):
        c, h = meter.create_counter, meter.create_histogram
        self.requests = c("rag.requests", description="Requests by outcome")
        self.duration = h("rag.request.duration", unit="s", description="End-to-end latency")
        self.ttft = h("rag.ttft", unit="s", description="Time to first token")
        self.stage = h("rag.stage.duration", unit="s", description="Latency per pipeline stage")
        self.tokens = c("rag.tokens", description="Tokens by direction")
        self.cost = c("rag.cost.usd", description="Cost in USD")
        self.empty = c("rag.retrieval.empty", description="Requests with empty/low-confidence retrieval")
        self.top1 = h("rag.retrieval.top1_score", description="Top-1 similarity score")
        self.ctx = h("rag.context_tokens", description="Context tokens sent to the model")
        self.score = h("rag.eval.score", description="Online evaluation scores (0..1)")
        self.guard = c("rag.guardrail.events", description="Guardrail verdicts")
        self.feedback = c("rag.feedback", description="User feedback")
        self.cache = c("rag.cache.lookups", description="Semantic cache lookups")
        self.retries = c("rag.llm.retries", description="LLM call retries")
        self.fallbacks = c("rag.llm.fallbacks", description="Fallback model used")
        self.eval_backlog = queue.Queue()
        # Pre-create rare series at 0: Prometheus increase() cannot see a series' first increment.
        for k in ("empty", "low_score"):
            self.empty.add(0, {"app": APP, "kind": k})
        self.retries.add(0, {"app": APP, "error_type": "rate_limited"})
        self.fallbacks.add(0, {"app": APP, "to": "small-model"})
        meter.create_observable_gauge("rag.eval.queue_age", callbacks=[self._queue_age], unit="s",
                                      description="Age of the oldest unevaluated trace")
        meter.create_observable_gauge("rag.index.age", callbacks=[self._index_age], unit="s",
                                      description="Age of the newest indexed document")

    def _queue_age(self, _):
        try:
            oldest = self.eval_backlog.queue[0][0]
            yield Observation(max(0.0, time.time() - oldest), {"app": APP})
        except IndexError:
            yield Observation(0.0, {"app": APP})

    def _index_age(self, _):
        yield Observation(CURRENT["s"].index_age_h * 3600, {"app": APP})


def jitter(base: float, spread: float = 0.25) -> float:
    return max(0.001, random.gauss(base, base * spread))


def timed_stage(t, p, name, base_s, attrs=None):
    """Run a simulated stage inside a child span and record its latency metric."""
    with t.tracer.start_as_current_span(name, attributes=attrs or {}) as span:
        d = jitter(base_s)
        time.sleep(d)
        p.stage.record(d, {"stage": name.split(".")[-1], "app": APP})
        return span, d


def handle_request(t, p, req_no: int) -> None:
    sc = CURRENT["s"]
    tenant, feature = random.choice(TENANTS), random.choices(FEATURES, [5, 3, 2])[0]
    conv = f"conv-{uuid.uuid4().hex[:8]}"
    model, index_version, prompt_version = "large-model", "2026-10-01", "v7"
    dims = {"app": APP, "feature": feature, "tenant": tenant}
    t0 = time.perf_counter()
    with t.tracer.start_as_current_span("rag.request", kind=SpanKind.SERVER) as root:
        trace_id = format(root.get_span_context().trace_id, "032x")
        root.set_attributes({
            "app.name": APP, "app.feature": feature, "app.tenant.id": tenant, "app.environment": "demo",
            "app.release.id": "rel-2026.10.3", "app.prompt.id": "faq-answer", "app.prompt.version": prompt_version,
            "rag.index.id": "kb-main", "rag.index.version": index_version, "rag.embedding.model": "embed-model",
            "gen_ai.conversation.id": conv, "app.query.length": random.randint(20, 220),   # length only, no text
            "app.price_table.version": PRICE_TABLE_VERSION,
        })
        status = "ok"
        try:
            # --- input guardrail --------------------------------------------------------------
            timed_stage(t, p, "rag.guardrail_in", 0.03)
            if random.random() < 0.006:
                p.guard.add(1, {"app": APP, "category": "prompt_injection", "action": "blocked", "direction": "input"})
                t.log.warning("input blocked by guardrail", extra={"category": "prompt_injection", "tenant": tenant})
                status = "blocked"
                root.set_attribute("guardrail.blocked", True)
                return

            # --- semantic cache ---------------------------------------------------------------
            hit = random.random() < 0.12
            p.cache.add(1, {"app": APP, "result": "hit" if hit else "miss"})
            root.set_attribute("rag.cache.hit", hit)
            if hit:
                time.sleep(jitter(0.04))
                p.ttft.record(0.04, {**dims, "model": "cache"})
                return

            # --- retrieval: embed -> vector search -> rerank ----------------------------------
            with t.tracer.start_as_current_span("rag.retrieve") as rs:
                r = sc.retr_mult
                timed_stage(t, p, "rag.embed", 0.045 * r, {"gen_ai.operation.name": "embeddings", "gen_ai.request.model": "embed-model"})
                timed_stage(t, p, "rag.vector_search", 0.09 * r, {"rag.retrieval.top_k": 20})
                timed_stage(t, p, "rag.rerank", 0.12 * r, {"rag.rerank.model": "reranker-v2"})
                empty = random.random() < sc.empty_rate
                n = 0 if empty else random.randint(3, 6)
                top1 = 0.0 if empty else min(0.99, max(0.05, random.gauss(0.74 + sc.top1_shift, 0.08)))
                rs.set_attributes({"rag.retrieval.count": n, "rag.retrieval.top1_score": top1,
                                   "rag.context.doc_ids": [f"doc-{random.randint(1, 5000)}" for _ in range(n)]})
                p.top1.record(top1, {"app": APP})
                if empty or top1 < 0.35:
                    p.empty.add(1, {"app": APP, "kind": "empty" if empty else "low_score"})
                    root.set_attribute("eval.flagged", True)         # cheap deterministic flag -> tail sampler keeps the trace
                    t.log.warning("weak retrieval", extra={"top1": round(top1, 3), "count": n, "index_version": index_version})
            ctx_tokens = int(random.gauss(1400, 250) * sc.ctx_mult * (0 if empty else 1)) + 200
            p.ctx.record(ctx_tokens, {"app": APP})
            root.set_attribute("rag.context.tokens", ctx_tokens)

            # --- generation with retry + fallback --------------------------------------------
            in_tok, out_tok, ttft = ctx_tokens + 250, int(random.gauss(260, 70)), 0.0
            attempt = 0
            while True:
                attempt += 1
                with t.tracer.start_as_current_span(f"chat {model}", kind=SpanKind.CLIENT) as ls:
                    ls.set_attributes({"gen_ai.operation.name": "chat", "gen_ai.provider.name": "demo-provider",
                                       "gen_ai.request.model": model, "gen_ai.request.temperature": 0.2,
                                       "app.prompt.version": prompt_version})
                    if random.random() < sc.error_rate:
                        time.sleep(jitter(0.25))
                        err = random.choice(["rate_limited", "upstream_5xx", "timeout"])
                        ls.set_status(Status(StatusCode.ERROR, err)); ls.set_attribute("error.type", err)
                        t.log.error("llm call failed", extra={"error_type": err, "attempt": attempt, "model": model})
                        if attempt >= 3:
                            raise RuntimeError(err)
                        p.retries.add(1, {"app": APP, "error_type": err})
                        if attempt == 2 and model != "small-model":
                            model = "small-model"; p.fallbacks.add(1, {"app": APP, "to": model}); root.set_attribute("app.fallback_used", True)
                        time.sleep(0.2 * attempt)
                        continue
                    base = 0.55 if model == "large-model" else 0.25
                    ttft = jitter(base * sc.llm_mult)
                    time.sleep(ttft)
                    decode = max(0.05, out_tok / jitter(90 if model == "large-model" else 160, 0.15)) * min(sc.llm_mult, 2.0)
                    time.sleep(decode)
                    ls.set_attributes({"gen_ai.response.model": model, "gen_ai.usage.input_tokens": in_tok,
                                       "gen_ai.usage.output_tokens": out_tok, "gen_ai.response.finish_reasons": ["stop"],
                                       "app.ttft_ms": round(ttft * 1000, 1)})
                    p.stage.record(ttft + decode, {"stage": "llm", "app": APP})
                    break

            price_in, price_out = PRICES[model]
            usd = (in_tok * price_in + out_tok * price_out) / 1e6
            p.tokens.add(in_tok, {**dims, "direction": "input", "model": model})
            p.tokens.add(out_tok, {**dims, "direction": "output", "model": model})
            p.cost.add(usd, {**dims, "model": model})
            p.ttft.record(ttft, {**dims, "model": model})
            root.set_attributes({"cost.usd.total": usd, "gen_ai.response.model": model})

            # --- output guardrail, feedback, async evaluation --------------------------------
            timed_stage(t, p, "rag.guardrail_out", 0.03)
            if random.random() < 0.004:
                p.guard.add(1, {"app": APP, "category": "pii", "action": "redacted", "direction": "output"})
            if random.random() < 0.08:
                good = random.random() < (0.82 + sc.quality_shift)
                p.feedback.add(1, {"app": APP, "rating": "up" if good else "down", "feature": feature})
            if random.random() < 0.25:                                # stratified sampling in real life
                p.eval_backlog.put((time.time(), root.get_span_context(), sc.quality_shift, top1, empty, model))
        except Exception as exc:  # noqa: BLE001
            status = "error"
            root.record_exception(exc); root.set_status(Status(StatusCode.ERROR, str(exc)))
            t.log.error("request failed", extra={"error": str(exc), "tenant": tenant})
        finally:
            elapsed = time.perf_counter() - t0
            root.set_attribute("app.status", status)
            p.requests.add(1, {**dims, "status": status})
            p.duration.record(elapsed, {**dims, "status": status})


def evaluator(t, p, stop: threading.Event) -> None:
    """Async, sampled, off the request path. Writes scores keyed by trace via a span link + metrics."""
    while not stop.is_set():
        try:
            enq, ctx, shift, top1, empty, model = p.eval_backlog.get(timeout=0.5)
        except queue.Empty:
            continue
        time.sleep(jitter(0.4))                       # judge-model latency
        base_ground = 0.88 + shift - (0.04 if model == "small-model" else 0)
        scores = {
            "groundedness": min(1, max(0, random.gauss(base_ground if not empty else 0.4, 0.07))),
            "answer_relevance": min(1, max(0, random.gauss(0.90 + shift * 0.8, 0.06))),
            "context_precision": min(1, max(0, random.gauss(0.70 + shift + (top1 - 0.74) * 0.5, 0.1))),
        }
        with t.tracer.start_as_current_span("rag.evaluate", links=[trace.Link(ctx)], attributes={
                "eval.version": "judge-v3", "eval.judge_model": "small-model", **{f"eval.{k}": v for k, v in scores.items()}}):
            for k, v in scores.items():
                p.score.record(v, {"app": APP, "metric": k})
            if scores["groundedness"] < 0.6:
                t.log.warning("low groundedness", extra={"score": round(scores["groundedness"], 3),
                                                         "trace_id": format(ctx.trace_id, "032x")})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rps", type=float, default=2.0, help="average requests per second")
    ap.add_argument("--duration", type=float, default=0, help="seconds to run (0 = forever)")
    ap.add_argument("--scenario", choices=SCENARIOS, default="normal")
    ap.add_argument("--cycle", type=float, default=0, help="rotate scenarios every N seconds")
    ap.add_argument("--console", action="store_true", help="print telemetry instead of exporting OTLP")
    a = ap.parse_args()

    t = setup(APP, console=a.console)
    p = Providers(t.meter)
    CURRENT["s"] = SCENARIOS[a.scenario]
    stop = threading.Event()
    threading.Thread(target=evaluator, args=(t, p, stop), daemon=True).start()
    order = itertools.cycle([x for f in SCENARIOS.values() if f.name != "normal" for x in (SCENARIOS["normal"], f)])   # healthy phase between faults
    if a.cycle:
        CURRENT["s"] = next(order)
    print(f"[{APP}] scenario={CURRENT['s'].name} ({CURRENT['s'].description})", flush=True)
    start = last_switch = time.time()
    pool = ThreadPoolExecutor(max_workers=64)
    n = 0
    try:
        while not a.duration or time.time() - start < a.duration:
            if a.cycle and time.time() - last_switch >= a.cycle:
                CURRENT["s"] = next(order); last_switch = time.time()
                t.log.warning(f"scenario change: {CURRENT['s'].name}", extra={"scenario": CURRENT["s"].name})
                print(f"[{APP}] scenario -> {CURRENT['s'].name}: {CURRENT['s'].description}", flush=True)
            n += 1
            pool.submit(handle_request, t, p, n)
            time.sleep(random.expovariate(a.rps))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set(); pool.shutdown(wait=True, cancel_futures=True); time.sleep(0.5); t.shutdown()


if __name__ == "__main__":
    main()
