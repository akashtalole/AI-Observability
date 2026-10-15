# AWS: CloudWatch, AgentCore and OpenTelemetry

## The pieces

| Capability | What it gives you |
|---|---|
| **CloudWatch generative AI observability** (GA since Oct 2025) | Out-of-the-box dashboards and trace views for model invocations and agents; deep integration with **Amazon Bedrock AgentCore** (runtime, built-in tools, gateway, memory, identity) |
| **AgentCore Observability** | Agent/session/trace views, token and latency metrics, errors; works for agents on AgentCore **and** external agents that send OTLP (including on-premises and other clouds) |
| **CloudWatch Omni** (GA Sep 2026) | AI-first, team/application-centric experience, agent tracing + evaluation, investigations: see [CloudWatch Omni](omni.md) |
| **Native OTLP endpoints** | Direct OTLP/HTTP ingestion for traces, logs and metrics, SigV4 authenticated |
| **Application Signals** | Application-level SLOs and service maps on OTel data |
| **Bedrock model invocation logging** | Request/response logs to CloudWatch Logs or S3 (content controls apply) |
| **Bedrock Guardrails / evaluations** | Safety verdicts and model/RAG evaluation jobs |
| **CloudWatch PromQL + high-cardinality metrics** | OTLP-ingested metrics queryable with PromQL; up to 150 labels per datapoint vs 30 dimensions for classic custom metrics |
| **X-Ray / Transaction Search** | Span storage for trace analytics; must be enabled for the OTLP traces endpoint |

## OTLP endpoints (from the CloudWatch docs)

| Signal | Endpoint | Auth | Notes |
|---|---|---|---|
| Traces | `https://xray.<region>.amazonaws.com/v1/traces` | SigV4 | Enable **Transaction Search** first; ≤ 10,000 spans and ≤ 5 MB per request; span ≤ 200 KB |
| Logs | `https://logs.<region>.amazonaws.com/v1/logs` | SigV4 **or** bearer token | Headers `x-aws-log-group`, `x-aws-log-stream` required; ≤ 1 MB per event (larger events become large log objects in selected regions); 5,000 TPS per account per Region |
| Metrics | `https://monitoring.<region>.amazonaws.com/v1/metrics` | SigV4 **or** bearer token | ≤ 150 labels, ≤ 1,000 datapoints per request, 500 TPS, new-series creation rate limit (1 M per 10 min) |

Common constraints: **HTTP/1.1 only (no gRPC)**, OTLP 1.x, binary or JSON, `gzip` or none, timestamps within 2 h in the future and 14 days in the past. The Collector **must use the `sigv4authextension`** (or `bearertokenauth` for logs/metrics). Verify current limits on the [OTLP Endpoints page](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-OTLPEndpoint.html).

### Collector configuration

```yaml title="examples/cloud/otel-collector-aws.yaml"
--8<-- "examples/cloud/otel-collector-aws.yaml"
```

Validated with `otelcol-contrib validate` (v0.120.0); not run against a live AWS account.

### Collector-less: ADOT SDK

For agents you can skip the Collector and export directly from the **AWS Distro for OpenTelemetry (ADOT)** SDK, which signs requests with SigV4 (the pattern AWS documents for agents running outside AWS):

```bash
pip install "aws-opentelemetry-distro>=0.10.0" boto3 "strands-agents[otel]"

export AGENT_OBSERVABILITY_ENABLED=true
export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_TRACES_EXPORTER=otlp
export OTEL_RESOURCE_ATTRIBUTES="service.name=my-agent,aws.log.group.names=/aws/bedrock-agentcore/runtimes/my-agent"
export OTEL_EXPORTER_OTLP_LOGS_HEADERS="x-aws-log-group=/aws/bedrock-agentcore/runtimes/my-agent,x-aws-log-stream=runtime-logs,x-aws-metric-namespace=bedrock-agentcore"

opentelemetry-instrument python agent.py
```

* `service.name` becomes the agent name in the dashboard; `aws.log.group.names` routes telemetry into AgentCore Observability.
* Outside AWS use **IAM Roles Anywhere** rather than long-lived keys. Run a pre-flight `sts get-caller-identity`: ADOT fails silently on bad credentials.
* One-time per region: `aws xray update-trace-segment-destination --destination CloudWatchLogs` (Transaction Search).
* Session correlation uses OTel baggage key `session.id`.
* IAM actions needed in AWS's example: `logs:CreateLogGroup/CreateLogStream/PutLogEvents`, `xray:PutTraceSegments`, `xray:PutTelemetryRecords`, `xray:GetSamplingRules`, `xray:GetSamplingTargets`, `cloudwatch:PutMetricData` (plus `bedrock:InvokeModel` for the agent itself). Scope them to the specific log groups.

Source: [AgentCore Observability for on-premises and multi-cloud agents](https://aws.amazon.com/blogs/machine-learning/monitor-on-premises-and-multi-cloud-ai-agents-with-agentcore-observability/).

## GenAI conventions on AWS

ADOT auto-instrumentation (and the Strands `otel` extra) emit spans following the **OpenTelemetry generative AI semantic conventions**: `invoke_agent`, `chat`, `execute_tool`, plus framework spans such as `execute_event_loop_cycle`, with token usage attributes. OpenInference instrumentation is also supported by Omni. Frameworks named by AWS: Strands Agents, LangChain, LangGraph, CrewAI, OpenAI Agents SDK, Vercel AI SDK (Python and TypeScript).

## Metering and cost on AWS

* **Application inference profiles** with cost-allocation tags give per-application/tenant Bedrock spend in Cost Explorer.
* **Model invocation logging** records tokens and latency per call to CloudWatch Logs/S3; query with Logs Insights, or Athena for long ranges.
* Emit your own cost metric (`tokens × your price table`) over OTLP metrics with `tenant`, `feature`, `model` labels; the 150-label limit and PromQL make this practical.

```text
# CloudWatch Logs Insights: tokens by model per day (Bedrock invocation logs)
fields @timestamp, modelId, input.inputTokenCount as tin, output.outputTokenCount as tout
| stats count() as requests, sum(tin) as in_tokens, sum(tout) as out_tokens by bin(1d), modelId
```

## Long-range trends on AWS

CloudWatch retains metrics for up to 15 months (with decreasing resolution) and logs per retention policy. For multi-month cost/quality trends: export logs/metrics to **S3 (Parquet) + Athena**, or run an analytical store (OpenSearch/ClickHouse/Redshift) fed by the same Collector, using the [wide-fact model](../architecture/storage-and-retention.md).

## Strengths and watch-outs

| Strengths | Watch-outs |
|---|---|
| First-party OTLP for all three signals; no vendor SDK needed | HTTP only, SigV4 plumbing, request/series limits to design batching around |
| Deep Bedrock/AgentCore integration; AI-aware views and evaluators | Transaction Search + log/metric namespaces are prerequisites; costs scale with span/log volume |
| Omni adds investigations, agent evaluation, multi-account/multi-cloud view | New (GA Sep 2026): check regional availability, pricing and feature depth for your use |
| IAM, KMS, VPC endpoints, org-wide controls | AWS-centric; cross-cloud comparisons still need a neutral analysis plane |
