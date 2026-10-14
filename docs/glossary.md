# Glossary

| Term | Meaning |
|---|---|
| **TTFT** | Time to first token — request start to first streamed token |
| **TPOT** | Time per output token — decode speed |
| **Span / Trace** | Unit of work / tree of spans for one request |
| **OTLP** | OpenTelemetry Protocol for transmitting telemetry |
| **Semconv** | Semantic conventions: standard names for attributes/metrics |
| **GenAI semconv** | OpenTelemetry conventions for LLM calls, agents, tools (`gen_ai.*`) |
| **OpenInference** | Arize-led conventions/instrumentors for LLM frameworks |
| **Groundedness / Faithfulness** | Degree to which the answer is supported by provided context |
| **Context precision / recall** | Share of retrieved context that is relevant / share of needed facts retrieved |
| **LLM-as-judge** | Using a model to score outputs against a rubric |
| **Golden set** | Curated evaluation dataset with expected outcomes |
| **Online / offline eval** | Scoring production traffic / scoring a fixed dataset |
| **Tail sampling** | Keep/drop whole traces after seeing them (errors, latency, flags) |
| **Wide event / fact row** | One denormalized record per request with many columns |
| **Rollup** | Pre-aggregated table at coarser time granularity |
| **Burn rate** | Speed of consuming an SLO error budget |
| **Cardinality** | Number of distinct label combinations in metrics |
| **Gateway** | Proxy layer for model traffic: auth, quotas, routing, metering |
| **MCP** | Model Context Protocol — standard for connecting models to tools/data |
| **Guardrail** | Runtime check that blocks, redacts or flags unsafe input/output |
| **Prompt injection** | Malicious instructions in input or retrieved/tool content |
| **KV cache** | Attention key/value cache in inference servers; pressure causes latency cliffs |
| **Shadow / canary** | Mirror traffic to a candidate / roll out to a small slice |
| **FinOps** | Financial accountability for cloud and AI spend |
| **Showback / chargeback** | Reporting / billing costs to owning teams |
