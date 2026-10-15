# GCP: Cloud Observability, Vertex AI and OpenTelemetry

## The pieces

| Capability | What it gives you |
|---|---|
| **Telemetry (OTLP) API** `telemetry.googleapis.com` | Google's first-party OTLP endpoint in front of Cloud Trace, Cloud Monitoring and Cloud Logging. Own quotas, separate from the older Monitoring/Logging APIs |
| **Cloud Trace** | Trace storage and Explorer; **OTLP trace ingestion is the recommended path** (announced Sep 2025) with larger limits than the legacy API (attribute value 64 KiB, up to 1024 attributes/span) |
| **Cloud Monitoring** | Metrics; the Telemetry API for **OTLP metric ingestion reached GA on 5 Aug 2026** (Monitoring release notes) |
| **Cloud Logging** | Logs; the Ops Agent (≥ 2.71.0, Sep 2026) can export metrics, logs and traces through the Telemetry API. Confirm GA status for direct OTLP logs |
| **Google-built OpenTelemetry Collector** | Google-maintained Collector distribution with Google exporters/auth preconfigured; deployable on Cloud Run/GKE |
| **Managed OpenTelemetry for GKE** | Managed collection for workloads on GKE |
| **Vertex AI / Agent Runtime** (formerly Agent Engine) | Model and agent platform; agents export OTel spans via a configured OTLP trace exporter in the agent process |
| **Vertex AI evaluation, Model Armor** | Quality evaluation services; prompt/response protection and verdicts |
| **BigQuery + Looker** | Long-range analytics via log/billing exports |

## OTLP details to design around

| Topic | Detail |
|---|---|
| Endpoint | `telemetry.googleapis.com` (gRPC/HTTP via standard OTLP exporters) |
| Auth | Google identity (Application Default Credentials, workload identity); the Collector uses `googleclientauth` |
| Project routing | `x-goog-user-project` / `gcp.project_id` resource attribute; enable the API: `gcloud services enable telemetry.googleapis.com` |
| Regions | Log and trace data may be moved between regions by the backend; **metric data is stored only when its location label matches the endpoint's region or a zone within it** |
| Quotas | Telemetry API has its own quotas; migrate alerts/charts on API usage to `telemetry.googleapis.com` |
| Cloud Trace Explorer filters | Uses OTel semantic conventions; `service.name` identifies the service |

Check the [Telemetry API overview](https://docs.cloud.google.com/stackdriver/docs/reference/telemetry/overview) and the [Monitoring release notes](https://docs.cloud.google.com/monitoring/docs/release-notes) for current signal-by-signal status.

## Collector configuration

```yaml title="examples/cloud/otel-collector-gcp.yaml"
--8<-- "examples/cloud/otel-collector-gcp.yaml"
```

Validated with `otelcol-contrib validate` (v0.120.0); not run against a live project. Exact headers, endpoint form and metric label requirements should follow Google's current Telemetry API documentation.

## Instrumenting a Vertex AI / LangGraph agent

Google's LangGraph guide sends traces through the Telemetry API using the OTLP gRPC exporter and the Vertex AI instrumentation:

```bash
pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc opentelemetry-instrumentation-vertexai
gcloud services enable telemetry.googleapis.com cloudtrace.googleapis.com monitoring.googleapis.com \
  logging.googleapis.com aiplatform.googleapis.com
```

For agents hosted on **Agent Runtime**, configure an OTLP trace exporter inside the agent process (a third-party integration guide describes this; confirm against Google's Agent Runtime docs).

## Metering and cost on GCP

* **Billing export to BigQuery** gives cost per project/label; use labels per application and tenant.
* Emit your own token/cost metrics through OTLP metrics (`tenant`, `feature`, `model` labels), keeping label cardinality in check.
* **Log sinks to BigQuery** retain request metadata for months for trend analysis; join with billing export for cost per answer.

## Strengths and watch-outs

| Strengths | Watch-outs |
|---|---|
| Single first-party OTLP endpoint; larger trace limits | Per-signal maturity differs (traces GA first, metrics GA Aug 2026, logs rolling out) |
| Strong BigQuery integration for trends and FinOps | Metric region/location rules; separate Telemetry API quotas |
| Google-built Collector and managed GKE OTel reduce ops | Fewer agent-specific UI affordances than Foundry/Omni; pair with an eval tool if needed |
| IAM, VPC-SC, CMEK | GCP-centric; cross-cloud views need a neutral plane |
