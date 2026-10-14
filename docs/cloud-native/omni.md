# Amazon CloudWatch Omni

**Amazon CloudWatch Omni** (generally available, announced 22 September 2026) is AWS's AI-first observability experience. It re-organizes CloudWatch around **teams and the applications they own** instead of AWS resource types, adds **agent observability, evaluation and experimentation**, and uses AI agents to speed investigations. It is built on OpenTelemetry.

!!! info "Sources and confidence"
    Based on AWS's launch posts ([agents/generative AI](https://aws.amazon.com/blogs/aws/introducing-amazon-cloudwatch-omni-ai-powered-observability-for-generative-ai-and-agentic-workloads/), [applications](https://aws.amazon.com/blogs/aws/introducing-amazon-cloudwatch-omni-collaborative-ai-powered-observability-for-your-applications/)) and the [What's New entry](https://aws.amazon.com/about-aws/whats-new/2026/09/amazon-cloudwatch-omni-ai/). Pricing, regional availability and some limits were not in the pages reviewed: check the CloudWatch pricing page and documentation. Details below may change.

## What it is

| Concept | Meaning |
|---|---|
| **Off-console experience** | Operators use a standalone web app (a dedicated URL per organization, SSO through IAM Identity Center, so Okta/Entra ID users need no AWS console access). Developers use an **IDE extension** for **VS Code and Kiro** (`AmazonWebServices.amazon-cloudwatch-omni`) |
| **Spaces** | A Space groups the applications a team owns plus their telemetry (logs, metrics, traces, alarms). Admins define Spaces per team and environment. A Space **points at existing CloudWatch data without moving it** |
| **Application-centric topology** | Services and dependencies are discovered from telemetry and AWS Config resource discovery; the topology updates as services deploy |
| **Dynamic views, SLO-driven alarms** | You declare targets (availability, latency budgets, error thresholds); Omni adjusts alarms as the system changes; live SLO/health views replace static dashboards |
| **Investigation sessions** | Opened with topology, correlated signals (for example recent deployments) and an initial analysis; **AWS DevOps Agent** joins, correlates signals, traces root-cause paths through the dependency graph and keeps history; sessions are shareable; natural-language questions over telemetry |
| **Connectors** | Bring telemetry from other environments into the same Spaces and investigations (AWS's materials describe multi-cloud, including Azure workloads) |
| **OpenTelemetry in** | Telemetry already sent to CloudWatch appears with no reconfiguration; other OTel workloads send to an OTLP endpoint |

## Agent observability, evaluation and experimentation

| Feature | Detail |
|---|---|
| **Trace Explorer** | Hierarchical timeline of LLM calls, tool invocations and reasoning steps with inputs, outputs, token usage and latency per span; **compare mode** (two traces side by side) |
| **Ask Assistant** | An agent that analyzes traces and answers questions about agent behavior |
| **Session Explorer** | Multi-turn conversation histories |
| **Agent Topology** | Sub-agents, tools and connections visualized |
| **Evaluators** | 17 built-in (for example coherence, helpfulness, faithfulness, routing correctness, correctness, retrieval quality, tool selection), plus third-party integrations (AutoEval, DeepEval) |
| **Playground, Experiments** | Side-by-side prompt/model comparison; compare agent variants |
| **Golden datasets, regression detection** | Build datasets from traces; detect regressions: the [offline-scoring loop](../scoring/offline-scoring.md) built in |
| **Prompt management** | Versioned prompt configurations with rollback |
| **Frameworks** | Strands, LangChain, LangGraph, CrewAI, OpenAI Agents SDK, Vercel AI SDK; native for Bedrock AgentCore; agents may run on Lambda, ECS, EKS or other clouds. Instrumentation via **OpenInference** and **ADOT** |
| **Developer onboarding** | "Auto-instrument with Kiro", sample project, local-first data store; **cloud login optional** to send telemetry to CloudWatch; assistants such as Kiro, Claude Code and Codex integrate |

The IDE extension is free and works without an AWS account for local development; sending/storing telemetry in CloudWatch is billed per CloudWatch pricing.

## How Omni maps to this handbook

| Handbook concept | In Omni |
|---|---|
| [Telemetry model & OTel](../fundamentals/telemetry-model.md) | OTLP ingest; OpenInference/ADOT instrumentation; `gen_ai` spans |
| [Online scoring](../scoring/online-scoring.md) | Built-in evaluators on traces; regression detection |
| [Offline scoring](../scoring/offline-scoring.md) | Experiments, golden datasets from traces, Playground |
| [SLOs & alerting](../metrics/slos-alerting.md) | Declared targets with automatic alarm tuning |
| [Runbooks](../operations/runbooks.md) | Investigation sessions with DevOps Agent; shared history |
| Change events | Correlated recent deployments inside investigations |

## Adopting Omni (practical path)

1. **Keep OTel at the edge.** Instrument with OpenTelemetry (ADOT or OpenInference) and route via your Collector, so Omni is a destination, not a dependency ([implementation guide](implementation-guide.md)).
2. **Existing CloudWatch customers:** use "Try CloudWatch Omni" in the CloudWatch console; existing telemetry, alarms, dashboards and APIs keep working unchanged.
3. **Define Spaces** that mirror team ownership (one Space per product team × environment) and align naming with your tagging standard (`app`, `team`, `env`, `tenant`).
4. **Send agent telemetry** with `gen_ai.*` spans and stable `service.name` per agent; verify the agent appears in Trace Explorer and Agent Topology.
5. **Turn on evaluators** for a sampled slice; calibrate against human labels before alerting on them ([Designing scorers](../scoring/designing-scorers.md)).
6. **Declare SLOs** (availability, latency, plus your own quality metric) and review the auto-tuned alarms.
7. **Governance:** decide who may see content (redaction at the Collector), which accounts feed which Spaces, retention, and whether DevOps Agent investigation access matches your change-management policy.
8. **Multi-cloud:** pilot connectors with one non-AWS workload; compare against a neutral plane (Grafana/warehouse) before standardizing.

## Where Omni fits and where it does not

| Good fit | Think twice |
|---|---|
| AWS-centred estates with Bedrock/AgentCore agents; teams that want AI-assisted triage and built-in evaluation | Strict data-residency or air-gap requirements not covered by region availability |
| Org-wide, team-oriented views over many accounts and Regions | Heavy reliance on custom evaluation workflows or prompt registries you already run elsewhere |
| Developers who want observability inside the IDE loop | Need for open, queryable raw data for months-long FinOps analytics: still export to S3/Athena or a warehouse |
| Reducing time to first useful dashboard | Pricing at high span/log volume: model it with the [TCO sketch](../build-vs-buy/tco.md) before rollout |

!!! warning "Lock-in note"
    Transport is open (OTLP) but the AI-aware features depend on attribute conventions and CloudWatch storage. Keep your Collector and exporters portable, store prompts/datasets in your own repo, and export golden datasets so you can leave.
