#!/usr/bin/env python3
"""CI gate: verify an AI app's spans carry the attributes every cloud backend and dashboard depends on.

    python examples/cloud/check_telemetry_contract.py            # runs the built-in sample app, exit 1 on violations
    python examples/cloud/check_telemetry_contract.py --break    # drops an attribute to show a failing run

Replace `run_app()` with a call into your service (using an in-memory exporter) and keep the CONTRACT in Git.
The same contract works for CloudWatch/Omni, Azure Monitor/Foundry and Google Cloud Trace because it is defined in
OpenTelemetry terms, not in any vendor's.
"""
from __future__ import annotations

import sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# span-name prefix -> attributes that must be present
CONTRACT = {
    "invoke_agent": ["gen_ai.operation.name", "gen_ai.agent.name", "app.tenant.id", "app.release.id"],
    "chat": ["gen_ai.operation.name", "gen_ai.request.model", "gen_ai.response.model",
             "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "app.prompt.version"],
    "execute_tool": ["gen_ai.operation.name", "gen_ai.tool.name"],
    "rag.retrieve": ["rag.index.version", "rag.retrieval.count", "rag.retrieval.top1_score"],
}
FORBIDDEN = ["gen_ai.prompt", "gen_ai.completion", "http.request.header.authorization"]   # content must not leak by default
REQUIRED_RESOURCE = ["service.name", "deployment.environment"]


def run_app(tracer, break_it: bool) -> None:
    with tracer.start_as_current_span("invoke_agent support-agent", attributes={
            "gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "support-agent",
            "app.tenant.id": "acme", "app.release.id": "rel-1"}):
        with tracer.start_as_current_span("rag.retrieve", attributes={
                "rag.index.version": "2026-10-01", "rag.retrieval.count": 4, "rag.retrieval.top1_score": 0.78}):
            pass
        attrs = {"gen_ai.operation.name": "chat", "gen_ai.request.model": "model-x", "gen_ai.response.model": "model-x",
                 "gen_ai.usage.input_tokens": 1200, "gen_ai.usage.output_tokens": 210, "app.prompt.version": "v7"}
        if break_it:
            del attrs["gen_ai.usage.output_tokens"]                 # cost metering would silently under-count
            attrs["gen_ai.prompt"] = "raw user text"                 # content leak
        with tracer.start_as_current_span("chat model-x", attributes=attrs):
            pass
        with tracer.start_as_current_span("execute_tool search", attributes={
                "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "search"}):
            pass


def main() -> int:
    from opentelemetry.sdk.resources import Resource
    exp = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "support-agent", "deployment.environment": "ci"}))
    provider.add_span_processor(SimpleSpanProcessor(exp))
    run_app(provider.get_tracer("contract"), "--break" in sys.argv)
    problems = []
    for span in exp.get_finished_spans():
        attrs = span.attributes or {}
        for prefix, required in CONTRACT.items():
            if span.name.startswith(prefix):
                problems += [f"{span.name}: missing {k}" for k in required if k not in attrs]
        problems += [f"{span.name}: forbidden attribute {k}" for k in FORBIDDEN if k in attrs]
        problems += [f"{span.name}: missing resource attribute {k}" for k in REQUIRED_RESOURCE if k not in span.resource.attributes]
    names = {s.name.split()[0] for s in exp.get_finished_spans()}
    problems += [f"no span emitted for '{p}'" for p in CONTRACT if p not in names]
    print(f"checked {len(exp.get_finished_spans())} spans against {len(CONTRACT)} contract entries")
    for p in problems:
        print("  VIOLATION:", p)
    print("CONTRACT: " + ("PASS" if not problems else "FAIL"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
