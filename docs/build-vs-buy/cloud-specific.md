# Cloud-specific approach

**Goal:** minimum integration effort and deepest native coverage when the AI workload lives in one cloud.

!!! tip "Deep dive"
    Detailed coverage of each cloud's OpenTelemetry support, **CloudWatch Omni**, and a step-by-step enterprise rollout is in [Cloud-native observability](../cloud-native/index.md).

!!! note
    Product names and features change quickly. Confirm current capabilities in each provider's documentation (links in [References](../references.md)).

## Azure

| Concern | Native service |
|---|---|
| Model + agent platform | Microsoft Foundry (Azure AI Foundry) — tracing, evaluators, monitoring for agents and apps |
| Telemetry backend | Azure Monitor / Application Insights (OpenTelemetry via Azure Monitor distro), Log Analytics (KQL) |
| Gateway & metering | Azure API Management AI gateway (token metering, rate limits, semantic caching) |
| Quality & safety | Foundry evaluators (groundedness, relevance, coherence, safety), Azure AI Content Safety |
| Dashboards/alerts | Azure Workbooks, Managed Grafana, Azure Monitor alerts |
| Long-range analytics | Log Analytics retention/archive, export to ADLS / Fabric / Synapse |
| Cost | Cost Management + token metrics from APIM/Foundry |

## AWS

| Concern | Native service |
|---|---|
| Model + agent platform | Amazon Bedrock, Bedrock Agents / AgentCore |
| Telemetry backend | CloudWatch (GenAI observability, Application Signals), X-Ray / OpenTelemetry (ADOT) |
| Invocation logging | Bedrock model invocation logging → S3 / CloudWatch Logs |
| Quality & safety | Bedrock Guardrails, Bedrock/RAG evaluation jobs |
| Dashboards/alerts | CloudWatch dashboards & alarms, Managed Grafana |
| Long-range analytics | S3 + Athena / OpenSearch / Redshift; CloudWatch Metrics Insights |
| Cost | Cost Explorer, application inference profiles with cost-allocation tags |

## Google Cloud

| Concern | Native service |
|---|---|
| Model + agent platform | Vertex AI (Gemini, Agent Engine/Builder) |
| Telemetry backend | Cloud Monitoring, Cloud Trace, Cloud Logging (OpenTelemetry native) |
| Quality & safety | Vertex AI evaluation services, Model Armor |
| Dashboards/alerts | Cloud Monitoring dashboards & alerting, Managed Prometheus |
| Long-range analytics | Log sinks → BigQuery (+ Looker) |
| Cost | Billing export to BigQuery |

## Data/AI platforms

| Platform | Observability features |
|---|---|
| **Databricks** | MLflow Tracing & evaluation, Mosaic AI Gateway/inference tables, system tables for cost |
| **Snowflake** | AI Observability (TruLens-based) and Cortex usage views |

## Strengths and costs

| Strengths | Costs |
|---|---|
| Fastest path; IAM, networking, billing already integrated | Lock-in; each cloud has a different data model |
| Native logs of model invocations and cost tags | Multi-provider/multi-cloud apps get fragmented views |
| Compliance inheritance (region, KMS, private link) | LLM-specific depth (prompt mgmt, eval UX) often lags dedicated tools |

## Recommended pattern: "native + OTel escape hatch"

1. Use the cloud-native backend as the **primary store**.
2. Instrument with **OpenTelemetry** and route via a Collector so a second destination can be added.
3. Export long-range wide facts to the cloud's warehouse (BigQuery / Fabric / Athena-Redshift) for cost and trend analysis.
4. Layer a dedicated eval/prompt tool (OSS or SaaS) if native evaluators are not enough.
