# Monitoring tools, MCP servers & text-to-SQL

## Tool / function calling

| Metric | Why |
|---|---|
| Tool selection accuracy (vs labels or judge) | Wrong tool = wrong answer |
| Argument validity / schema-conformance rate | Prompt or schema drift |
| Tool success/error/timeout rate, latency by tool | Dependency health |
| Calls per task, duplicate-call rate | Cost, loops |
| Result size (tokens injected back) | Context blow-up |
| Write/destructive-call rate, approval outcomes | Safety |
| Idempotency/retry anomalies | Side-effect duplication |

## MCP (Model Context Protocol) servers

MCP servers are *remote dependencies with their own trust boundary*.

* Trace client → MCP server calls as `execute_tool` spans; propagate `traceparent` where supported so server-side spans join the trace.
* Server-side: request rate, latency, error codes, auth failures, tool/resource/prompt usage, payload sizes.
* Inventory: which servers/tools are enabled per app; alert on **new or changed tool descriptions** (tool-poisoning / rug-pull risk).
* Security: log permission grants, user consent events, cross-server data flow; treat tool outputs as untrusted (indirect prompt injection).
* Version and pin MCP server versions; add them to change events.

## Text-to-SQL / NL-to-query

| Metric | Method |
|---|---|
| SQL validity (parses, binds) | deterministic |
| **Execution accuracy** (result matches golden query result) | offline golden set |
| Semantic correctness for live traffic | judge + user confirmation |
| Schema coverage / unknown-column rate | schema drift detection |
| Query cost & runtime (rows scanned, warehouse credits) | DB telemetry joined by trace ID |
| Safety: read-only enforcement, blocked statements, row-level security hits | policy logs |
| Result-size and PII exposure | post-query scan |
| Retry/repair loops per question | agent metrics |

Join warehouse query history (`query_id`) to the trace so you can attribute **warehouse spend to AI features**.

## Code-execution tools
Exit codes, runtime, memory, network egress attempts, sandbox policy violations, package install attempts.
