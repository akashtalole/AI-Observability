# Enterprise AI Observability Handbook

Guidance, architecture, design patterns and tooling choices for observing **enterprise AI applications** — RAG systems, agents, chatbots, copilots and more.

!!! tip "The north-star goal"
    Full visibility into **latency, quality and cost** of every AI application, across **any time range** (last 5 minutes to last 18 months), so issues are caught early and trends are tracked over months.

## Where to start

<div class="grid cards" markdown>

- **I need a decision** — [Build vs Buy framework](build-vs-buy/decision-framework.md), then [cloud-agnostic](build-vs-buy/cloud-agnostic.md), [cloud-specific](build-vs-buy/cloud-specific.md) or [open-source](build-vs-buy/open-source.md) guides.
- **I run a RAG app** — go straight to the [RAG observability playbook](rag/rag-observability-playbook.md) and [dashboards & queries](rag/dashboards-and-queries.md).
- **I need to know what to collect** — [Metrics catalog](metrics/metrics-catalog.md) and [Data to collect](metrics/data-to-collect.md).
- **I need to pick a tool** — [Landscape overview](landscape/overview.md), [full catalog](landscape/catalog.md), [comparison by need](landscape/comparison.md).
- **I monitor agents / chatbots / voice** — [Monitoring by app type](monitoring/overview.md).
- **I run on AWS / Azure / GCP** — [Cloud-native observability](cloud-native/index.md): OpenTelemetry support, **CloudWatch Omni**, Foundry, Cloud Trace, and an [enterprise implementation guide](cloud-native/implementation-guide.md).
- **I need to measure quality** — [Online and offline scoring](scoring/index.md): datasets, scorers, judges, sampling, gates.
- **I want runnable OSS implementations** — [Use cases on OTel + Prometheus + Grafana + Loki + Tempo](use-cases/index.md): RAG, multi-agent, chatbot.
- **I want to build it** — [Reference architecture](architecture/reference-architecture.md) and [instrumentation guide](implementation/instrumentation.md).

</div>

## What is in this repo

| Area | Contents |
|---|---|
| `docs/fundamentals` | Why AI observability differs from APM; the telemetry model; OpenTelemetry GenAI conventions |
| `docs/architecture` | Reference architecture, design patterns, storage/retention for long-range trends, security & privacy |
| `docs/build-vs-buy` | Decision framework, cloud-agnostic / cloud-specific / OSS guides, TCO model |
| `docs/landscape` | Popular tools across the whole landscape (generated from `data/tools.json`) |
| `docs/metrics` | Metrics catalog, data to collect, SLOs/alerts, evaluation |
| `docs/cloud-native` | Azure, AWS (incl. CloudWatch Omni) and GCP native observability, OTLP support, enterprise implementation guide |
| `docs/scoring` | Online and offline scoring: datasets, scorers, judges, sampling, gates, cost, by app type |
| `docs/monitoring` | Per-application-type monitoring: RAG, agents, chatbots, tools/MCP, voice, self-hosted |
| `docs/rag` | End-to-end RAG playbook with dashboards, SQL, PromQL |
| `docs/implementation` | Instrumentation, collector pipeline, evals in CI |
| `docs/operations` | Maturity model, runbooks, checklists |
| `use-cases/` | Runnable open-source implementations: docker-compose stack, instrumented RAG / multi-agent / chatbot apps, Grafana dashboards, alert rules |
| `docs/artifacts` | Interactive **HTML artifacts** (decision tool, landscape explorer, RAG dashboard demo, single-file handbook) |
| `examples/` | Runnable OpenTelemetry instrumentation, Collector config, ClickHouse schema, Prometheus alert rules, offline eval gate and online scorer |

!!! warning "Fast-moving space"
    Vendors, licenses and ownership in this market change quickly (acquisitions, relicensing, product shutdowns), and the OpenTelemetry GenAI conventions are still in *Development* status. Every tool fact here carries an "as of" date — **verify against vendor docs before committing**. See [References](references.md).
