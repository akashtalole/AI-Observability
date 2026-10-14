# Enterprise implementation guide: cloud-native AI observability

How to roll out observability for enterprise AI apps (RAG, agents, chatbots) on **AWS, Azure and GCP**, using each cloud's native stack with **OpenTelemetry as the portable layer**. Written for platform, SRE, security and AI teams.

## 1. Principles

1. **OpenTelemetry at the edge, native backend behind it.** Applications emit OTel only; a Collector tier you own handles redaction, sampling, enrichment and routing to the cloud-native backend(s).
2. **One telemetry contract for all clouds.** Same span names, attributes and metric names everywhere ([contract](#4-the-telemetry-contract)); the cloud-specific parts are exporters and identity.
3. **Metadata by default, content by exception.** Capture IDs, counts, scores and versions; gate prompts/responses behind policy, redaction and short retention.
4. **Central visibility, local ownership.** Workload accounts/subscriptions/projects send to a central observability plane; teams see their own slice.
5. **Measure all three pillars.** Latency, quality (scores) and cost on every dashboard ([RAG playbook](../rag/rag-observability-playbook.md), [scoring](../scoring/index.md)).
6. **Telemetry must not break the app**, and **its own health is monitored**.

## 2. Reference architecture

```mermaid
flowchart TB
    subgraph W1[Workload account / subscription / project - team A]
      A1[AI app + OTel SDK] --> C1[Collector agent<br/>sidecar / DaemonSet]
    end
    subgraph W2[Workload account - team B]
      A2[Agents + OTel SDK] --> C2[Collector agent]
    end
    subgraph SH[Shared network / platform]
      G[Collector gateway tier<br/>HA, tail sampling, redaction,<br/>routing, rate limits]
    end
    subgraph OBS[Central observability account / subscription / project]
      N1[(Native backend<br/>CloudWatch + Omni | Azure Monitor + Foundry | Cloud Trace/Monitoring/Logging)]
      LAKE[(Long-range store<br/>S3+Athena | ADLS/Fabric | BigQuery)]
      DASH[Dashboards, alerts, SLOs]
    end
    C1 --> G
    C2 --> G
    G -->|native OTLP or exporter| N1
    G -->|batch export| LAKE
    N1 --> DASH
    LAKE --> DASH
    G -.optional.-> X[Second backend:<br/>OSS stack or LLM-native tool]
```

| Tier | Role | Notes |
|---|---|---|
| **SDK in the app** | Spans, metrics, logs with the contract | Auto-instrumentation + thin wrapper ([Instrumentation guide](../implementation/instrumentation.md)) |
| **Collector agent** (optional) | Local buffering, resource detection | Sidecar (ECS/ACA/Cloud Run), DaemonSet (EKS/AKS/GKE) |
| **Collector gateway** | Redact, tail-sample, enrich, route, authenticate to the cloud | ≥ 2 replicas; load-balance by `trace_id` in front of tail sampling |
| **Native backend** | Storage, UI, alerts, AI-aware views | Per cloud ([AWS](aws.md), [Azure](azure.md), [GCP](gcp.md)) |
| **Long-range store** | Months of facts/rollups for FinOps and trend | [Storage & retention](../architecture/storage-and-retention.md) |

## 3. Phased rollout

| Phase | Weeks | Deliverables | Exit criteria |
|---|---|---|---|
| **0. Decide** | 0-2 | Backend per cloud, multi-cloud pattern ([§9](#9-multi-cloud-patterns)), data-classification and retention policy, owners, ADR | Signed ADR; security/privacy sign-off on content policy |
| **1. Foundations** | 2-6 | Landing zone ([§5](#5-landing-zone-checklists)), Collector gateway, identity, private connectivity, telemetry contract + CI check | Synthetic app visible end to end in each cloud with the contract passing |
| **2. First workloads** | 6-10 | 1-2 apps instrumented; latency/cost dashboards; SLOs; alerts to on-call | Pilot team debugs a real incident from traces |
| **3. Quality** | 8-14 | Online evaluators on a sample, golden set + CI gate ([scoring](../scoring/index.md)), feedback capture | Quality time series with sample sizes and an alert |
| **4. Scale-out** | 12-24 | Templates/modules, onboarding automation, tenant/cost attribution, long-range store | New app onboarded in < 1 day |
| **5. Optimize** | 20+ | Sampling/retention tuning, canary/rollback automation, FinOps reports, multi-cloud single pane | Observability cost ≤ target share of AI spend |

## 4. The telemetry contract

Define it once (OpenTelemetry terms) and enforce it in CI. Full attribute guidance: [Telemetry model](../fundamentals/telemetry-model.md), [Data to collect](../metrics/data-to-collect.md).

| Level | Required |
|---|---|
| **Resource** | `service.name`, `service.version`, `deployment.environment`, cloud attributes (`cloud.provider`, `cloud.account.id`/`cloud.region` via resource detection), `app.team`, `app.cost_center` |
| **Request / agent root span** | `app.tenant.id`, `app.feature`, `app.release.id`, `gen_ai.conversation.id`, `cost.usd.total` |
| **Model call span** (`chat`) | `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `app.prompt.id`, `app.prompt.version` |
| **Retrieval span** | `rag.index.version`, `rag.embedding.model`, `rag.retrieval.count`, `rag.retrieval.top1_score` (IDs, not text) |
| **Agent / tool spans** | `gen_ai.agent.name`, `gen_ai.tool.name`, `tool.side_effect`, step index, termination reason |
| **Forbidden by default** | `gen_ai.prompt`, `gen_ai.completion`, message bodies, auth headers |

Pin the OpenTelemetry **GenAI semantic-convention version** you target. The conventions are in *Development*; Azure's distro, for example, uses an explicit opt-in (`OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`).

Enforce it with a contract test in every service's pipeline: [`examples/cloud/check_telemetry_contract.py`](https://github.com/akashtalole/ai-observability/blob/main/examples/cloud/check_telemetry_contract.py) (in-memory exporter, fails on missing attributes and content leaks):

```text
$ python examples/cloud/check_telemetry_contract.py --break
  VIOLATION: chat model-x: missing gen_ai.usage.output_tokens
  VIOLATION: chat model-x: forbidden attribute gen_ai.prompt
CONTRACT: FAIL
```

## 5. Landing zone checklists

### AWS

- [ ] Central observability account (AWS Organizations); cross-account observability for CloudWatch; Omni Spaces mapped to teams ([Omni](omni.md))
- [ ] **CloudWatch Transaction Search enabled** per region (`aws xray update-trace-segment-destination --destination CloudWatchLogs`)
- [ ] Log groups/streams for the OTLP logs endpoint (`x-aws-log-group` / `x-aws-log-stream`); retention set; KMS key
- [ ] Collector IAM role (IRSA / EKS Pod Identity / ECS task role) scoped to PutTraceSegments, PutLogEvents, PutMetricData as needed; **IAM Roles Anywhere** for non-AWS callers
- [ ] VPC interface endpoints for CloudWatch/X-Ray/Logs; egress via NAT only where required
- [ ] Bedrock invocation logging destination + application inference profiles with cost-allocation tags
- [ ] Bedrock Guardrails configured; verdicts emitted as metrics/spans
- [ ] Quotas reviewed: logs 5,000 TPS/region, metrics 500 TPS and series-creation rate, 10,000 spans/request

### Azure

- [ ] Application Insights (workspace-based) per environment connected to Foundry projects; central Log Analytics workspace strategy
- [ ] OTLP ingestion path chosen (Collector with Entra auth / Azure Monitor Agent / AKS onboarding); data collection resources created; current preview/GA status confirmed
- [ ] RBAC: Contributor on App Insights for ingestion, Log Analytics Reader / Privileged Monitoring Data Reader for query; managed identities for the Collector
- [ ] Private Link scope (AMPLS) for ingestion/query; Key Vault for connection strings
- [ ] APIM AI gateway in front of model endpoints: token metrics, limits, semantic cache
- [ ] Content recording **off** in production (`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` unset); sampling and retention tiers configured
- [ ] Azure Policy: require diagnostic settings, tags (`app`, `team`, `cost_center`)

### GCP

- [ ] Central observability project; metrics scopes for multi-project views
- [ ] APIs enabled: `telemetry.googleapis.com`, `cloudtrace`, `monitoring`, `logging`, `aiplatform`
- [ ] Workload identity (GKE) / service accounts for the Collector with trace/metric/log writer roles; `googleclientauth`
- [ ] Telemetry API quotas reviewed; alerts moved from legacy API usage to the new endpoint
- [ ] Metric location labels aligned with the endpoint region (metrics are stored only when location matches)
- [ ] Log sinks to BigQuery; billing export with labels; VPC Service Controls where required; CMEK
- [ ] Model Armor policies; verdicts emitted as telemetry

## 6. Collector tier: patterns by platform

| Platform | Agent tier | Gateway tier | Identity to cloud |
|---|---|---|---|
| **AWS ECS/Fargate** | Sidecar container | ECS service behind NLB | Task role (SigV4) |
| **AWS EKS** | DaemonSet | Deployment (≥ 2) + `loadbalancing` exporter | IRSA / Pod Identity |
| **Azure AKS / Container Apps** | DaemonSet / sidecar | Deployment (≥ 2) | Managed identity / workload identity (Entra) |
| **GKE / Cloud Run** | DaemonSet / sidecar; or Google-built Collector | Deployment (≥ 2) | Workload identity (ADC) |
| **VMs / on-prem** | Host agent (Azure Monitor Agent, Ops Agent, ADOT/OTel Collector) | Central gateway | IAM Roles Anywhere / Arc / federated identity |

Gateway configuration (all clouds), starting from the [reference Collector](../implementation/collector-pipeline.md):

* `memory_limiter` first, `batch` last; batches under the target's per-request limits (AWS: ≤ 10,000 spans / 5 MB).
* **Metrics before sampling** (`spanmetrics`), then redaction, then **tail sampling**: keep 100 % of errors, slow, flagged and low-score traces; sample the rest at 1-10 %.
* `resourcedetection` to add cloud/account/region; `attributes`/`transform` to enforce the tagging standard.
* Persistent sending queues and retry; alert on drops (`otelcol_exporter_send_failed_*`).
* Per-cloud configs: [AWS](https://github.com/akashtalole/ai-observability/blob/main/examples/cloud/otel-collector-aws.yaml), [Azure](https://github.com/akashtalole/ai-observability/blob/main/examples/cloud/otel-collector-azure.yaml), [GCP](https://github.com/akashtalole/ai-observability/blob/main/examples/cloud/otel-collector-gcp.yaml).

## 7. Instrumentation matrix

| Framework / runtime | AWS | Azure | GCP |
|---|---|---|---|
| **Strands** | ADOT + `strands-agents[otel]` (native) | Collector → Azure Monitor | OTLP → Telemetry API |
| **LangChain / LangGraph** | ADOT or OpenInference → CloudWatch/Omni | **Microsoft OpenTelemetry distro** (`langchain` option) | `opentelemetry-instrumentation-vertexai` + OTLP (Google LangGraph guide) |
| **Microsoft Agent Framework / Semantic Kernel** | OTLP → CloudWatch | **Native** with Foundry tracing | OTLP → Telemetry API |
| **CrewAI / OpenAI Agents SDK / Vercel AI SDK** | ADOT/OpenInference (supported by Omni) | OTel instrumentors + Azure Monitor exporter / distro | OTel instrumentors + OTLP |
| **Direct provider SDKs** | OpenLLMetry/OpenInference/OpenLIT | same | same |
| **Hosted agent runtimes** | Bedrock AgentCore (native) | Foundry hosted agents (native) | Agent Runtime (OTLP exporter in process) |

Keep a **wrapper library** so every team emits the same contract regardless of framework.

## 8. Quality, safety and cost in a cloud-native stack

| Concern | AWS | Azure | GCP | Neutral layer |
|---|---|---|---|---|
| **Online scoring** | Omni evaluators on traces | Foundry evaluators | Vertex AI evaluation | Own judge workers writing `*.eval.score` metrics ([online scoring](../scoring/online-scoring.md)) |
| **Offline gates** | Omni experiments/golden datasets | Foundry evaluation runs | Vertex evaluation | CI gate ([offline scoring](../scoring/offline-scoring.md)) |
| **Safety verdicts** | Bedrock Guardrails | Content Safety | Model Armor | Emit as metrics/spans with `category`/`action` |
| **Metering** | Bedrock logs + inference profiles | APIM token metrics | Vertex usage + billing export | Own price table → `cost.usd.*` |
| **Long-range** | S3 + Athena | ADLS/Fabric | BigQuery | [Wide-fact table](../architecture/storage-and-retention.md) |

Use native evaluators for speed, but **record scorer version and judge model** on every score and keep your calibration set ([Designing scorers](../scoring/designing-scorers.md)); otherwise scores are not comparable across clouds or over time.

## 9. Multi-cloud patterns

| Pattern | How | Pros | Cons | Fits |
|---|---|---|---|---|
| **A. Native per cloud + neutral aggregator** | Each cloud's workloads go to its native backend; the Collector also exports to a shared OSS stack/warehouse for cross-cloud views | Best native UX per cloud; true cross-cloud analysis | Two places to look; cost of dual ingest | Most large enterprises |
| **B. Single native pane (e.g. Omni with connectors)** | Ingest other clouds into one provider's UI | One UI, AI-assisted investigation across clouds | Depends on connector coverage and pricing; lock-in to one UI | AWS-centric estates with a few outside workloads |
| **C. Everything to one neutral stack** | Collector → Tempo/Prometheus/Loki/ClickHouse (or a vendor) in every cloud | Maximum portability and cost control | You run it; lose native AI-aware UIs | Platform-engineering-led orgs, sovereign requirements ([OSS use cases](../use-cases/index.md)) |

Cross-cloud trace propagation: use W3C `traceparent` over every hop (gateways, queues, MCP/tool calls). Inject the same `app.*` attributes in each cloud so queries and dashboards port unchanged. Keep tenant and region residency rules in Collector routing (EU tenants → EU backends).

## 10. Security, privacy and governance

| Control | Implementation |
|---|---|
| **Content policy** | Default no content; allow-list apps/tenants/environments with time-boxed capture; redaction in the gateway ([Security & privacy](../architecture/security-privacy.md)) |
| **Encryption** | KMS / Key Vault / Cloud KMS keys on log, trace and lake storage; TLS to endpoints |
| **Network** | PrivateLink / Private Link / Private Service Connect to telemetry endpoints; egress allow-lists for Collectors |
| **Access** | Team-scoped views (Omni Spaces, Azure RBAC per workspace/resource, GCP metrics scopes and IAM conditions); break-glass for raw content; audit access |
| **Retention** | Tiered TTLs enforced by the platform (log-group retention, Log Analytics table plans, bucket lifecycle); erasure by pseudonymous ID |
| **Residency** | Region-pinned backends; Collector routing rules; verify where each service stores data (for example GCP metric location rules) |
| **Compliance evidence** | Retain score history, scorer/dataset versions, change events and incident records ([Operating a scoring program](../scoring/operating.md)) |
| **Credentials** | No long-lived keys; workload identity everywhere; secrets in vault; rotate bearer tokens if used |

## 11. Cost control

* **Know the unit prices.** CloudWatch bills ingestion/storage/queries by signal; App Insights by GB and retention; Cloud Trace/Monitoring/Logging by usage. Model them with the [TCO sketch](../build-vs-buy/tco.md).
* **Sample traces, not metrics.** Metrics and the per-request fact row cover 100 %; traces 1-10 % plus all errors/slow/flagged.
* **Cap cardinality:** `tenant` only for bounded lists; no `user_id`/`trace_id` on metric labels; mind AWS's 150-label and new-series limits and Azure/GCP custom-metric limits.
* **Tier storage:** hot (days) → warm facts (13-24 months) → cold lake; shorter retention for content.
* **Budget the judges:** evaluation cost as a share of inference spend; sample and tier scorers.
* **Alert on observability spend** itself, and on Collector drop rates (cost savings must not be silent data loss).

## 12. Testing and validation

| Test | Where | What it proves |
|---|---|---|
| **Telemetry contract test** | CI per service | Required attributes present; no forbidden content |
| **Collector config validation** | CI | `otelcol validate` for each cloud config |
| **Synthetic canary** | Production | A scripted request per app every minute: trace appears in the backend within N minutes, metrics and logs correlate |
| **Failure injection** | Staging | Exporter down → app unaffected, queue bounded, drop metric increments, alert fires |
| **Redaction fixtures** | CI | Seeded PII/secrets never reach any exporter |
| **Limits test** | Staging | Large spans/batches stay under endpoint limits; high-cardinality label guard works |
| **Dashboard/alert as code** | CI | Queries return data against the canary; no `no data` panels |
| **Game day** | Quarterly | Run a [runbook](../operations/runbooks.md) from alert to root cause using only the new tooling |

## 13. Operating model

* **Ownership:** platform team owns Collectors, contract, backends and cost; product teams own SLOs, dashboards, scorers and golden sets.
* **SLOs:** availability, latency (TTFT and end-to-end), quality (score with minimum n), cost per successful task ([SLOs & alerting](../metrics/slos-alerting.md)).
* **Change events** (deploy, prompt, model, index, guardrail policy) written to the observability plane from CI/CD.
* **Cadence:** weekly triage of flagged traces → regression set; monthly trend and cost review; quarterly contract/semconv version review and provider-status re-check.

## 14. Anti-patterns

| Anti-pattern | Why it hurts | Instead |
|---|---|---|
| App code calls a cloud SDK directly for telemetry | Lock-in; inconsistent attributes | OTel SDK + Collector |
| One global backend and one global access role | Cross-team data exposure | Spaces / RBAC / metrics scopes per team |
| Content capture left on after debugging | PII exposure, storage bill | Time-boxed flags, redaction tests |
| Different attribute names per cloud/team | No cross-cloud dashboards | One contract, enforced in CI |
| Trusting a "GA" label on a feature without reading limits | Surprises at scale | Check quotas, regions and status per signal |
| Relying only on native evaluators with no calibration | Untrustworthy scores | Version and calibrate every scorer |
| No second path out | Lock-in at the UI/storage layer | Keep Collector fan-out and a long-range export |

## 15. Decision record template

```markdown
# ADR: AI observability backend for <cloud/estate>
Context: workloads, data classes, regions, existing tooling, team skills
Options: native only / native + neutral aggregator / neutral only
Evaluation: bake-off results on real traces (setup effort, trace fidelity for agents, evaluators, SQL/PromQL access, cost at 3x)
Decision: ...
Consequences: lock-in surface, exit plan (Collector fan-out, dataset/prompt export), cost model, owners
Review date: ... (re-check preview/GA status, pricing, semconv version)
```
