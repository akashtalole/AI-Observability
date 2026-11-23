# Other OpenTelemetry changes to adopt

*Taken from changelogs of the specification, Collector and semantic conventions. Release numbers move monthly: verify before pinning.*

## Semantic conventions (core)

| Change | Impact here |
|---|---|
| GenAI conventions removed from the core repo in **v1.42.0** | Cite and pin the GenAI repo separately ([GenAI page](genai-semconv.md)). |
| Resource attribute `deployment.environment` → **`deployment.environment.name`** | The demo apps still emit the old name; Prometheus labels, Loki labels and docs use `deployment_environment`. Rename together. |
| `enduser.id` deprecation in favour of newer user attributes | Do not put user identifiers on spans; hash or use a tenant-scoped surrogate. |
| Cloud-related entity and attribute adjustments (1.43–1.45) | Re-run `weaver registry diff` against your registry after upgrading. |

## Specification

* **Entities** are part of the resource data model: a resource is described by entities (service, host, `gen_ai.main_agent`, …) rather than loose attributes.
* **Profiles** have a data model and are in **public alpha**; not for critical production workloads yet.
* **Environment-variable context propagation** (carrying trace context to child processes), useful for CLI tools, batch jobs and agents that spawn subprocesses.
* **Prometheus compatibility** work continues; keep the Collector's Prometheus exporter and remote-write settings under review after each upgrade.
* **Declarative configuration** (`opentelemetry-configuration` 1.0.0) is stable: one YAML file configures SDK providers, processors and exporters. Support differs by
  language; the Java agent's support is still experimental. Plan it for new services; do not rewrite working env-var setups yet.

## Collector

* Exporter helper: `queue_batch` replaces the older batching settings (rename, beta). Check release notes before upgrading the pinned Collector in
  `use-cases/stack/otel-collector.yaml` (currently 0.120.0) and re-run `otelcol validate`.
* gRPC keepalive defaults changed; review if you front the Collector with load balancers.
* Self-observability metric names have changed between releases (see the note in [The shared stack](../use-cases/stack.md)).

## SDKs and instrumentation

* GenAI instrumentation for Python moved into **`opentelemetry-python-genai`** (`opentelemetry-util-genai`); other languages follow at different speeds. Check each library against the
  [conformance results](weaver-conformance.md#the-conformance-project).
* **OBI** (OpenTelemetry eBPF Instrumentation) reached **1.0**: zero-code HTTP/gRPC/DB telemetry for services you cannot modify, such as model gateways and vector databases. Its
  compatibility commitments cover configuration and deployment; telemetry names follow semconv stability.
* Keep `OTEL_SEMCONV_STABILITY_OPT_IN` explicit while GenAI is in Development.
