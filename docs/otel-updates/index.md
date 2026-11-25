# OpenTelemetry updates (GenAI, agents, Weaver)

*Researched from primary sources (the repositories and release notes) in November 2026. Everything below is still **Development**
stability: pin versions and re-check before you rely on a name.*

## What changed, in one page

| # | Change | Why it matters | Action |
|---|---|---|---|
| 1 | **GenAI conventions moved to their own repo**: [`semantic-conventions-genai`](https://github.com/open-telemetry/semantic-conventions-genai) (first release **v0.1.0**, built on core semconv **v1.45.0**). They were removed from the main semconv repo in v1.42.0. | Version, pin and diff GenAI conventions separately from HTTP/DB/etc. | Pin both versions; update links ([details](genai-semconv.md)). |
| 2 | **Metrics restructured.** Per-operation duration histograms (`gen_ai.client.inference.duration`, `…embeddings.duration`, `gen_ai.execute_tool.duration`, `gen_ai.retrieval.duration`, …) and per-kind token metrics replace the single `gen_ai.client.token.usage`. | Dashboards and cost queries keyed on the old name stop matching. | Dual-emit during migration ([playbook](adoption-playbook.md)). |
| 3 | **Agentic conventions**: `invoke_agent`, `plan`, `execute_tool`, retrieval and memory operations, `gen_ai.invoke_agent.*` metrics, MCP and A2A conventions, the `gen_ai.evaluation.result` event. | A standard vocabulary for the agent loop, tools and evaluations. | Map your spans; see [agentic conventions](genai-semconv.md#agentic-conventions). |
| 4 | **Content capture is opt-in** via `OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT` (`NO_CONTENT` default, `SPAN_ONLY`, `EVENT_ONLY`, `SPAN_AND_EVENT`). | Privacy default; but see the variable-name trap below. | Set explicitly per environment. |
| 5 | **Weaver** (v0.28.x) is the tool to *define, check, document and live-validate* telemetry: `registry check`, `generate`, `diff`, `live-check`, `infer`. | Turns "we follow semconv" into a CI gate. | [Weaver & conformance](weaver-conformance.md); runnable in [`conformance/`](https://github.com/akashtalole/ai-observability/tree/main/conformance). |
| 6 | **Conformance repo** (`semantic-conventions-conformance`) runs scenario programs per language/library and validates their output with Weaver live-check. | The way to see which instrumentations really emit the conventions. | Use its results to choose libraries ([conformance](weaver-conformance.md#the-conformance-project)). |
| 7 | Core changes: resource `deployment.environment` → **`deployment.environment.name`**, spec entities and env-var context propagation, profiles in public alpha, declarative configuration stable, OBI 1.0. | Several touch every service, not just GenAI. | [Other changes](other-changes.md). |

!!! warning "Trap: two content-capture variable names"
    The specification defines `OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT`. At the time of research the Python
    `opentelemetry-util-genai` package still read `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`. Check the version of your instrumentation and
    set the variable it actually reads; verify with a test request that content is (or is not) captured.

## Pages

* [GenAI & agentic semantic conventions](genai-semconv.md): signal inventory, status, what changed.
* [Weaver & conformance](weaver-conformance.md): checking, live-check, matchers, policies, CI, and results against this repo's demo apps.
* [Other OpenTelemetry changes](other-changes.md): spec, Collector, SDK/instrumentation and non-GenAI semconv items.
* [Adoption playbook](adoption-playbook.md): sequenced migration steps and a checklist.
