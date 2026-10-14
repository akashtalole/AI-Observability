# Comparison by need

Indicative guidance — **not a benchmark**. Run a [bake-off](../build-vs-buy/decision-framework.md#bake-off-plan-2-weeks) on your own traces.

## "I want…" quick picker

| I want… | Strong candidates | Why |
|---|---|---|
| Self-hosted LLM tracing + prompts + evals | Langfuse, Phoenix, Opik | Mature OSS UIs with datasets/evals |
| Deep **RAG retrieval analysis** | Phoenix, TruLens, Langfuse + Ragas | Retriever/reranker spans; context relevance metrics |
| Eval-first / experiment-driven workflow | Braintrust, LangSmith, Confident AI, Opik | Experiments, datasets, online scoring |
| LangChain/LangGraph-heavy stack | LangSmith (or OTel to Langfuse/Phoenix) | Native integration |
| One pane with infra APM | Datadog, Dynatrace, New Relic, Grafana, Elastic | Correlate LLM with services and infra |
| Pure OTel / no lock-in | OpenLIT/OpenLLMetry + Collector + Grafana/SigNoz/ClickHouse | Open standards end to end |
| Months-long **cost and quality trends** with SQL | ClickHouse / warehouse wide table + Grafana/Superset | Cheap aggregation, joins with billing |
| Azure / AWS / GCP native | Foundry+App Insights / Bedrock+CloudWatch / Vertex+Cloud Trace | Integrated IAM, billing, guardrails |
| Lakehouse-centric | Databricks MLflow + system tables / Snowflake AI Observability | Data never leaves platform |
| Cost control across teams | LiteLLM, Portkey, Kong, APIM, Envoy AI Gateway | Central metering, budgets |
| Agent simulation & trajectory evals | Maxim, Laminar, LangSmith, Braintrust, Inspect AI | Multi-step evaluation |
| Runtime safety / PII | Presidio, LLM Guard, NeMo Guardrails, cloud guardrails | Detect and block in-line |

## Capability heat map (indicative)

Legend: ●● strong · ● adequate · ○ limited/DIY

| | Tracing | Prompt mgmt | Datasets/Evals | Online evals | Cost attribution | Long-range trends | Self-host | OTel ingest |
|---|---|---|---|---|---|---|---|---|
| Langfuse | ●● | ●● | ●● | ●● | ●● | ● | ●● | ●● |
| Phoenix | ●● | ● | ●● | ● | ● | ● | ●● | ●● |
| LangSmith | ●● | ●● | ●● | ●● | ●● | ● | ● (ent.) | ● |
| Braintrust | ●● | ●● | ●● | ●● | ● | ●● | ● (hybrid) | ● |
| Datadog LLM Obs | ●● | ○ | ● | ● | ●● | ●● | ○ | ●● |
| Dynatrace | ●● | ○ | ● | ● | ● | ●● | ● (managed) | ●● |
| Grafana stack + OpenLIT | ● | ○ | ○ | ○ | ● | ●● | ●● | ●● |
| ClickHouse + Grafana (DIY) | ● | ○ | ○ | ○ | ●● | ●● | ●● | ●● |
| Azure Foundry + App Insights | ●● | ● | ●● | ●● | ● | ●● | n/a | ●● |
| Bedrock + CloudWatch | ● | ○ | ● | ● | ● | ●● | n/a | ●● |
| LiteLLM / Portkey | ● | ● | ○ | ○ | ●● | ● | ●● / ● | ● |

!!! warning
    Capability ratings are the editors' qualitative summary of public documentation as of the snapshot date and will age. Use them to build a shortlist, not to decide.

## Typical enterprise combinations

| Profile | Stack |
|---|---|
| Regulated bank, multi-cloud | OTel → in-VPC Collector (redaction) → Langfuse/Phoenix self-host + ClickHouse facts + Grafana; gateway = Kong/LiteLLM |
| Azure-first enterprise | Foundry + App Insights + APIM AI gateway; OTel Collector for portability; Fabric for trends |
| AWS-first scale-up | Bedrock + CloudWatch/AgentCore; Langfuse/Braintrust for evals; Athena/Redshift for trends |
| Datadog shop | Datadog LLM Obs for ops; Braintrust/Langfuse for evals; warehouse for cost |
| Startup, speed | LangSmith or Langfuse Cloud or Braintrust; add Collector later |
