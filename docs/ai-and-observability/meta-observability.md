# Meta-observability: observing the AI that observes

Every AI feature you add to your observability stack (LLM judges, anomaly models, investigation agents, query assistants, summarizers) is an **AI application with production access**. It needs the same observability you apply to your product's AI, plus guardrails appropriate to its privileges.

## What to observe about observability AI

| Component | Latency | Quality | Cost | Safety |
|---|---|---|---|---|
| **LLM judges / scorers** | Queue age, judge p95 | Calibration vs humans (κ), anchor-set drift, score variance | Tokens per score, share of inference spend | Judge sees customer content: access logs |
| **Anomaly / forecast models** | Evaluation latency | Precision/recall vs labeled incidents, alert acceptance rate, false-alert rate | Compute | Alert storms from model bugs |
| **Query assistants (NL → PromQL/LogQL/SQL)** | Time to result | Query validity, result correctness on a golden set, repair loops | Warehouse/TSDB cost of generated queries | Blocked statements, row/time limits hit |
| **Investigation agents** | Time to first hypothesis, steps | Root-cause accuracy, **evidence validity**, false-confidence rate, human acceptance | Cost per investigation, runaway guard hits | Actions proposed/approved/denied, unauthorized tool attempts |
| **Summarizers** | Latency | Faithfulness to the incident record | Tokens | Leakage of sensitive details into channels |
| **Auto-remediation** | Time to act | Success rate, rollback rate, regressions introduced | n/a | Blast radius, approvals, kill-switch use |

## Reuse the same patterns

* **Trace every agent run** (`invoke_agent` → `chat` → `execute_tool`) with the [agent monitoring](../monitoring/agents.md) metrics: steps, loops, tool errors, budget terminations, approvals.
* **Score it** online and offline: [replayed-incident corpus](ai-for-observability.md#evaluating-an-ai-for-observability-tool-pilot-design) as the golden set, sampled live investigations graded by humans.
* **Alert on the assistant's health**: error rate, latency, spend, loop detections, injection detections, plus "assistant unavailable" so on-call falls back to manual runbooks.
* **Version everything**: model, prompt, tool definitions, runbook corpus; write change events so a change in assistant behavior can be explained.

## Avoid circularity

| Risk | Mitigation |
|---|---|
| **Same model family generates and judges** | Different family for judges; calibrate on human labels |
| **AI alerts on AI quality using an uncalibrated judge** | Gate alerting on calibration status; show n and intervals |
| **Assistant diagnoses an AI-app incident without AI context** | Feed it versions, retrieval health, eval scores, change events |
| **Telemetry the agent reads is shaped by the agent's own actions** | Mark agent-caused changes (`actor=ai-agent`) in change events |
| **Single provider for app model, judge and SRE agent** | An outage or silent model change hits all three at once; diversify or at least monitor correlation |
| **Observability outage hides the AI outage** | Independent health checks and synthetic canaries outside the same pipeline |

## Governance

* Register assistants in the **AI inventory** with owner, risk tier, data accessed, tools, and approval authority.
* Treat tool access like IAM: reviewed, time-bound, logged. Re-certify periodically.
* Keep a **kill switch** (disable actions; fall back to read-only; fall back to humans) tested in game days.
* Retain audit trails (questions, evidence, actions, approver) per your compliance requirements.
* Fold the assistants into your incident process: postmortems should note when AI helped, misled, or acted.

## A minimal meta-observability dashboard

| Panel | Why |
|---|---|
| Investigations per day, time to first hypothesis | Adoption and responsiveness |
| Human acceptance / edit rate; evidence-validity sample score | Is it trusted *and* right? |
| Root-cause accuracy on replay set (weekly re-run) | Regression detection after vendor/model updates |
| False-confidence rate | The most dangerous failure |
| Cost per investigation; runaway-guard hits | Budget |
| Actions proposed / approved / denied / rolled back | Safety |
| Judge calibration (κ) and anchor-set drift | Trustworthy quality metrics |
| Assistant availability and fallback usage | Resilience |

These are the same building blocks as the [use-case dashboards](../use-cases/multi-agent.md); an investigation agent is a multi-agent system and can be instrumented with the same contract.
