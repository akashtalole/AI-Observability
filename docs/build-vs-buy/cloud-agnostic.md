# Cloud-agnostic approach

**Goal:** keep instrumentation, data and dashboards portable across AWS, Azure, GCP, on-prem and multiple model providers.

## Principles

1. **OpenTelemetry end to end** — SDK → Collector → any backend.
2. **Own the Collector** — redaction, sampling and routing logic lives in your config, not in a vendor.
3. **Own the wide fact table** — long-range truth sits in a store you control (ClickHouse, Iceberg/Parquet lakehouse, or your warehouse).
4. **Gateway abstraction** — LiteLLM/Portkey/Envoy AI Gateway/TensorZero abstract providers and meter usage uniformly.
5. **Kubernetes-friendly** — everything deployable via Helm/Terraform on any cloud.

## Reference stack options

=== "OSS core"
    | Concern | Choice |
    |---|---|
    | Instrumentation | OpenTelemetry SDK + OpenLLMetry / OpenInference / OpenLIT |
    | Pipeline | OpenTelemetry Collector (contrib) |
    | LLM traces, prompts, evals UI | Langfuse (self-host) or Arize Phoenix |
    | Metrics | Prometheus + Mimir/Thanos/VictoriaMetrics |
    | Traces (infra) | Tempo or Jaeger |
    | Wide facts / trends | ClickHouse |
    | Dashboards | Grafana |
    | Alerts | Alertmanager / Grafana Alerting → PagerDuty/Opsgenie |
    | Evals | Ragas / DeepEval / TruLens in pipelines |
    | Gateway | LiteLLM or Envoy AI Gateway |

=== "Multi-cloud SaaS"
    | Concern | Choice |
    |---|---|
    | Instrumentation | OpenTelemetry SDK |
    | Pipeline | Your Collector → vendor OTLP endpoint |
    | Platform | Datadog LLM Observability, Dynatrace, New Relic, Grafana Cloud AI Observability, or LLM-native SaaS (LangSmith, Braintrust, Arize AX, Langfuse Cloud) |
    | Trends | Vendor retention + export to your warehouse |

=== "Hybrid (common)"
    OTel → Collector → (a) APM for infra and golden signals, (b) LLM-native platform for traces/evals/prompts, (c) warehouse/ClickHouse for the wide fact table, cost and trends.

## Portability checklist

- [ ] No vendor SDK in business code; only your wrapper + OTel.
- [ ] Attributes use `gen_ai.*` plus your `app.*`/`rag.*` namespace.
- [ ] Prompts stored in Git (or a registry with export), referenced by `prompt.id@version`.
- [ ] Datasets and eval definitions exportable (JSONL/Parquet).
- [ ] Dashboards defined as code (Grafana JSON/Terraform) and SQL in Git.
- [ ] Pricing table (model → $/token) maintained by you, not inferred by the vendor.

## Strengths and costs

| Strengths | Costs |
|---|---|
| Lowest lock-in; negotiating leverage | You integrate the pieces and own upgrades |
| Consistent estate-wide view | Lowest common denominator — may miss cloud-specific features (e.g. native model-invocation logs) |
| Works with sovereign / air-gapped deployments | Requires platform engineering capacity |

## When to choose
Multi-cloud or hybrid estates, sovereignty needs, many model providers, or a strategic intent to avoid platform lock-in. See the [decision framework](decision-framework.md).
