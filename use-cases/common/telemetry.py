"""Shared OpenTelemetry bootstrap for the use-case demo apps (traces + metrics + logs over OTLP/gRPC).

    pip install -r use-cases/requirements.txt
    t = setup("support-rag")                 # OTLP -> $OTEL_EXPORTER_OTLP_ENDPOINT (default http://localhost:4317)
    t = setup("support-rag", console=True)   # print to stdout instead (no stack needed)

The demo apps simulate model/vector-DB calls so they run with no API keys.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.metrics import Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Latency-oriented default (seconds); score histograms get 0..1 buckets via the view below.
LATENCY_BUCKETS = [0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64]
SCORE_BUCKETS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
COUNT_BUCKETS = [1, 2, 3, 5, 8, 13, 21, 34, 55]


@dataclass
class Telemetry:
    tracer: trace.Tracer
    meter: metrics.Meter
    log: logging.Logger
    shutdown: callable


def setup(service: str, *, console: bool = False, env: str | None = None, extra: dict | None = None) -> Telemetry:
    resource = Resource.create({
        "service.name": service,
        "service.namespace": "ai-observability-demo",
        "deployment.environment": env or os.getenv("DEPLOY_ENV", "dev"),
        **(extra or {}),
    })
    views = [
        # Only duration histograms (unit "s") get latency buckets; a unit-less catch-all would ALSO match the score/count
        # histograms below and emit two bucket sets for one metric, which corrupts histogram_quantile().
        View(instrument_type=Histogram, instrument_unit="s", aggregation=ExplicitBucketHistogramAggregation(LATENCY_BUCKETS)),
        View(instrument_type=Histogram, instrument_name="*.score", aggregation=ExplicitBucketHistogramAggregation(SCORE_BUCKETS)),
        View(instrument_type=Histogram, instrument_name="*.utilization", aggregation=ExplicitBucketHistogramAggregation(SCORE_BUCKETS)),
        View(instrument_type=Histogram, instrument_name="*.top1_score", aggregation=ExplicitBucketHistogramAggregation(SCORE_BUCKETS)),
        View(instrument_type=Histogram, instrument_name="*.steps", aggregation=ExplicitBucketHistogramAggregation(COUNT_BUCKETS)),
        View(instrument_type=Histogram, instrument_name="*.turns", aggregation=ExplicitBucketHistogramAggregation(COUNT_BUCKETS)),
        View(instrument_type=Histogram, instrument_name="*.task.cost", aggregation=ExplicitBucketHistogramAggregation(
            [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2])),
        View(instrument_type=Histogram, instrument_name="*.context_tokens", aggregation=ExplicitBucketHistogramAggregation(
            [250, 500, 1000, 2000, 4000, 8000, 16000, 32000])),
    ]
    if console:
        span_exp, metric_exp, log_exp = ConsoleSpanExporter(), ConsoleMetricExporter(), ConsoleLogExporter()
    else:
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        span_exp, metric_exp, log_exp = OTLPSpanExporter(), OTLPMetricExporter(), OTLPLogExporter()

    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(span_exp))
    trace.set_tracer_provider(tp)

    interval = int(os.getenv("METRIC_EXPORT_INTERVAL_MS", "5000"))
    mp = MeterProvider(resource=resource, views=views,
                       metric_readers=[PeriodicExportingMetricReader(metric_exp, export_interval_millis=interval)])
    metrics.set_meter_provider(mp)

    lp = LoggerProvider(resource=resource)
    lp.add_log_record_processor(BatchLogRecordProcessor(log_exp))
    set_logger_provider(lp)
    logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=lp))
    logging.getLogger().setLevel(logging.INFO)

    def shutdown() -> None:
        tp.force_flush(); mp.force_flush(); lp.force_flush()
        tp.shutdown(); mp.shutdown(); lp.shutdown()

    return Telemetry(trace.get_tracer(service), metrics.get_meter(service), logging.getLogger(service), shutdown)
