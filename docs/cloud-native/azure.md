# Azure: Foundry, Application Insights and OpenTelemetry

## The pieces

| Capability | What it gives you |
|---|---|
| **Microsoft Foundry Observability** | **Observability > Traces** (agent runs: LLM calls, tool invocations, decision flow), evaluations and monitoring for agents and models. Traces are stored in **Application Insights** using OpenTelemetry semantic conventions |
| **Application Insights / Azure Monitor** | Trace, metric and log storage, Log Analytics (KQL), alerts, Workbooks, Managed Grafana |
| **Azure Monitor OTLP ingestion** | Native OTLP paths: **OpenTelemetry Collector** (sends to Azure Monitor endpoints with **Microsoft Entra** authentication, usable anywhere), **Azure Monitor Agent** (VMs, VMSS, Arc-enabled servers), **AKS onboarding** (autoinstrumentation/autoconfiguration). Traces, metrics and logs |
| **Microsoft OpenTelemetry distro** (`microsoft-opentelemetry`) | One call, `use_microsoft_opentelemetry(...)`, enables Azure Monitor export plus framework instrumentation (LangChain/LangGraph, Agent Framework) and adds agent identity attributes |
| **Native framework tracing** | Microsoft Agent Framework and Semantic Kernel emit traces automatically when tracing is enabled for a Foundry project |
| **API Management AI gateway** | Token metering and limits, semantic caching, load balancing across model deployments |
| **Safety** | Azure AI Content Safety, Foundry guardrails and evaluators |

!!! warning "Status labels differ between pages"
    Microsoft's docs describe OTLP ingestion in Azure Monitor as **preview** (Learn page dated May 2026) while a Tech Community post (May 2026) announces direct OTLP ingestion as **generally available**. Foundry states tracing is **GA for prompt and hosted agents**, **preview for workflow and external agents**. Confirm the current status on Learn before production use.

## Which ingestion path

| Your workload | Use |
|---|---|
| Agents on Foundry (hosted/prompt) | Connect Application Insights to the Foundry project; traces flow automatically |
| Microsoft Agent Framework / Semantic Kernel | Built-in; no extra packages when project tracing is enabled |
| LangChain / LangGraph / OpenAI Agents SDK anywhere | Microsoft OpenTelemetry distro (Python) or OpenInference instrumentors; set the Application Insights connection string |
| AKS workloads | AKS OTLP onboarding (autoconfiguration works for apps already instrumented with OTel) |
| VMs / Arc servers | Azure Monitor Agent receiving OTLP locally |
| Multi-cloud / on-prem, central control | Your **OpenTelemetry Collector** → Azure Monitor (Entra auth) or the `azuremonitor` exporter |

## Instrumenting an agent (from Microsoft's Foundry docs)

```python
from microsoft.opentelemetry import use_microsoft_opentelemetry

use_microsoft_opentelemetry(
    enable_azure_monitor=True,          # connection string from APPLICATIONINSIGHTS_CONNECTION_STRING
    sampling_ratio=1.0,
    instrumentation_options={
        "langchain": {"enabled": True, "agent_id": "support-agent-v3", "agent_name": "Support agent"},
    },
)
```

```bash
pip install microsoft-opentelemetry langchain langgraph langchain-openai azure-identity
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=..."
```

**Content capture is a development switch.** Prompts, tool arguments and outputs are captured only when you enable it:

```bash
# development only; leave unset in production
export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=SPAN_AND_EVENT
export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
export AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true
```

Note the opt-in to the *latest experimental* GenAI conventions: attribute names can change between releases, so pin versions.

## Collector configuration

```yaml title="examples/cloud/otel-collector-azure.yaml"
--8<-- "examples/cloud/otel-collector-azure.yaml"
```

Validated with `otelcol-contrib validate` (v0.120.0); not run against a live subscription. For the native OTLP path with Entra authentication, follow Microsoft's current "Ingest OTLP data into Azure Monitor with OTel Collector" page for exact endpoint and role settings.

## Permissions and access

* **Contributor** (or higher) on the Application Insights resource for trace ingestion (Foundry docs).
* Viewers need access to the connected Application Insights resource; for KQL add **Log Analytics Reader**, and **Privileged Monitoring Data Reader** if the tables are protected.
* Use managed identity/`DefaultAzureCredential` for model calls; keep connection strings in **Key Vault**.
* Private networking: Azure Private Link scopes (AMPLS) for Monitor ingestion and query.

## Metering and cost on Azure

* **APIM AI gateway** emits token metrics per consumer/product/deployment (the cleanest source for chargeback) and enforces token limits.
* Application Insights data is billed by ingestion and retention: use sampling (adaptive or ratio), retention tiers and basic-logs tables for high-volume diagnostic data; see [Storage & retention](../architecture/storage-and-retention.md).
* Export to **ADLS/Fabric** for long-range FinOps and quality trends.

```kusto
// Tokens and p95 latency per model per day (App Insights; adjust property names to your telemetry)
AppDependencies
| where Name startswith "chat"
| extend model = tostring(Properties["gen_ai.request.model"]),
         tin = toint(Properties["gen_ai.usage.input_tokens"]),
         tout = toint(Properties["gen_ai.usage.output_tokens"])
| summarize requests = count(), p95_ms = percentile(DurationMs, 95), in_tokens = sum(tin), out_tokens = sum(tout)
  by bin(TimeGenerated, 1d), model
```

## Strengths and watch-outs

| Strengths | Watch-outs |
|---|---|
| Native agent tracing for Microsoft frameworks; Entra identity end to end | Status labels (preview vs GA) vary by feature; check per component |
| Application Insights + Log Analytics: powerful KQL, Workbooks, Grafana | OTLP onboarding needs Azure resources (App Insights, collection configuration) and Entra roles |
| APIM AI gateway for metering and governance | Python-first for some tracing integrations (LangChain/LangGraph) |
| Private Link, RBAC, Policy, compliance inheritance | Cross-cloud views still need a neutral plane |
