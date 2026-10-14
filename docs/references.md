# References

*Verify all links and facts — this space changes monthly. Collected October 2026.*

## Standards
* [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) — status: Development
* [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) and [tail sampling processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/tailsamplingprocessor)
* [OpenInference](https://github.com/Arize-ai/openinference), [OpenLLMetry](https://github.com/traceloop/openllmetry), [OpenLIT](https://openlit.io)
* [W3C Trace Context](https://www.w3.org/TR/trace-context/)
* [Google SRE Workbook – Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) (burn-rate method)

## Platforms and docs
* Langfuse: <https://langfuse.com/docs> · Phoenix: <https://docs.arize.com/phoenix> · Opik: <https://www.comet.com/docs/opik/> · LangSmith: <https://docs.smith.langchain.com> · Braintrust: <https://www.braintrust.dev/docs>
* Datadog LLM Observability: <https://docs.datadoghq.com/llm_observability/>
* Microsoft Foundry observability: <https://learn.microsoft.com/azure/ai-foundry/concepts/observability>
* Amazon Bedrock model invocation logging: <https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html>
* Vertex AI generative AI evaluation: <https://cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-overview>
* MLflow Tracing: <https://mlflow.org/docs/latest/genai/tracing/>

## Cloud-native observability (verify current status)
* AWS: [CloudWatch OTLP endpoints](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-OTLPEndpoint.html) · [Introducing Amazon CloudWatch Omni (agents)](https://aws.amazon.com/blogs/aws/introducing-amazon-cloudwatch-omni-ai-powered-observability-for-generative-ai-and-agentic-workloads/) · [Omni (applications)](https://aws.amazon.com/blogs/aws/introducing-amazon-cloudwatch-omni-collaborative-ai-powered-observability-for-your-applications/) · [AgentCore Observability for on-prem and multi-cloud agents](https://aws.amazon.com/blogs/machine-learning/monitor-on-premises-and-multi-cloud-ai-agents-with-agentcore-observability/)
* Azure: [OpenTelemetry ingestion options](https://learn.microsoft.com/en-us/azure/azure-monitor/containers/opentelemetry-summary) · [Configure tracing for AI agent frameworks (Foundry)](https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-framework) · [Direct OpenTelemetry ingestion GA announcement](https://techcommunity.microsoft.com/blog/azureobservabilityblog/direct-opentelemetry-ingestion-into-azure-monitor-is-now-generally-available/4524044)
* GCP: [OpenTelemetry now in Google Cloud Observability](https://cloud.google.com/blog/products/management-tools/opentelemetry-now-in-google-cloud-observability) · [Telemetry (OTLP) API overview](https://docs.cloud.google.com/stackdriver/docs/reference/telemetry/overview) · [Monitoring release notes](https://docs.cloud.google.com/monitoring/docs/release-notes) · [Instrument a LangGraph agent with OpenTelemetry](https://docs.cloud.google.com/stackdriver/docs/instrumentation/ai-agent-langgraph)

## Evaluation
* [Ragas](https://docs.ragas.io), [DeepEval](https://deepeval.com), [TruLens](https://www.trulens.org), [promptfoo](https://www.promptfoo.dev), [Inspect AI](https://inspect.aisi.org.uk)
* Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* (2023)
* Es et al., *RAGAS: Automated Evaluation of Retrieval Augmented Generation* (2023)

## Governance
* [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
* [ISO/IEC 42001](https://www.iso.org/standard/81230.html)
* [EU AI Act](https://artificialintelligenceact.eu)
* [OWASP Top 10 for LLM Applications](https://genai.owasp.org)

## Market notes used in this handbook (verify)
* ClickHouse announced the Langfuse acquisition in January 2026; Langfuse states the project remains open source.
* Helicone was reported to have joined Mintlify (March 2026) and moved to maintenance mode.
* CloudWatch Omni reached GA in September 2026 (AWS posts dated 22 Sep); pricing and regions were not in the pages reviewed.
* Azure Monitor OTLP ingestion: Learn labels it preview while a May 2026 Tech Community post announces GA; Foundry tracing is GA for prompt/hosted agents, preview for workflow/external agents.
* Google OTLP: traces GA (Sep 2025); Telemetry API metrics GA (5 Aug 2026 release notes); logs via the Ops Agent from v2.71.0 (Sep 2026), direct-OTLP logs GA unconfirmed.
* Arize ownership reports conflict between sources — confirm directly with the vendor.
