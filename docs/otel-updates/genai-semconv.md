# GenAI & agentic semantic conventions

Source: [`open-telemetry/semantic-conventions-genai`](https://github.com/open-telemetry/semantic-conventions-genai), release
[v0.1.0](https://github.com/open-telemetry/semantic-conventions-genai/releases/tag/v0.1.0). Stability: **Development**. The registry declares a
dependency on core semconv v1.45.0 and uses Weaver's `definition/2` schema format.

!!! note "Why a separate repository"
    GenAI conventions change faster than HTTP, database or messaging conventions. A standalone repository lets them release on their own
    cadence. The v0.1.0 release notes measure changes against core semconv v1.41.0, the last release that still contained them.

## Signal inventory (v0.1.0)

**Spans** (17 definitions across GenAI, MCP and A2A):

| Operation | Span type | Kind | Name format |
|---|---|---|---|
| Model call | `gen_ai.client.inference` | client | `{operation} {request.model}` |
| Embeddings | `gen_ai.client.embeddings` | client | `{operation} {request.model}` |
| Agent invocation | `gen_ai.client.invoke_agent` (remote) / `gen_ai.invoke_agent.internal` (in-process) | client / internal | `invoke_agent {agent.name}` |
| Planning | `gen_ai.plan.internal` | internal | `plan {agent.name}` |
| Tool execution | `gen_ai.execute_tool` | internal | `execute_tool {tool.name}` |
| Retrieval | `gen_ai.retrieval` / `gen_ai.retrieval.client` | internal / client | `{operation}` or `{operation} {data_source.id}` |
| Memory, fetch response, create agent, realtime | `gen_ai.memory.client`, `gen_ai.fetch_response.client`, `gen_ai.create_agent.client`, `gen_ai.realtime_inference.client` | client | operation-specific |
| MCP / A2A | `mcp.client`, `mcp.server`, `a2a.client`, `a2a.server` | client / server | `{mcp.method.name} {target}` / `{a2a.method.name}` |

**Metrics** (all Development):

| Group | Metrics |
|---|---|
| Duration | `gen_ai.client.operation.duration`, `gen_ai.client.inference.duration`, `gen_ai.client.embeddings.duration`, `gen_ai.client.invoke_agent.duration`, `gen_ai.execute_tool.duration`, `gen_ai.retrieval.duration` |
| Streaming | `gen_ai.client.inference.time_to_first_chunk`, `gen_ai.client.inference.time_per_output_chunk` |
| Server side | `gen_ai.server.request.duration`, `gen_ai.server.time_to_first_token`, `gen_ai.server.time_per_output_token` |
| Agent | `gen_ai.invoke_agent.duration`, `gen_ai.invoke_agent.inference_calls`, `gen_ai.invoke_agent.tool_calls` |
| Tokens (counters) | `gen_ai.client.inference.usage.input_tokens`, `…usage.output_tokens`, `…usage.cache_read.input_tokens`, `…usage.cache_write.input_tokens`, `…usage.reasoning.output_tokens` |
| Tokens (per-operation histograms) | `gen_ai.client.inference.operation.input_tokens`, `…operation.output_tokens`, `gen_ai.client.embeddings.operation.input_tokens` |
| MCP | `mcp.client.operation.duration`, `mcp.server.operation.duration`, `mcp.client.session.duration`, `mcp.server.session.duration` |

**Events:** `gen_ai.client.inference.operation.details` (content), `gen_ai.evaluation.result`, per-operation `*.exception` events, realtime session
started/ended. **Entity:** `gen_ai.main_agent`.

## Agentic conventions

* **Agent loop.** An agent run is an `invoke_agent` span. Planning is a `plan` span, each model call an inference span, each tool call an
  `execute_tool` span, all as children, so trace shape mirrors the loop.
* **Agent metrics.** `gen_ai.invoke_agent.inference_calls` and `gen_ai.invoke_agent.tool_calls` histograms give "model calls / tool calls per run"
  without trace queries; the handbook's [loop-detection](../monitoring/agents.md) guidance maps directly onto them.
* **MCP and A2A.** Client and server spans plus operation and session durations let you see an agent-to-tool or agent-to-agent hop as a first-class span.
* **Evaluations.** The `gen_ai.evaluation.result` event carries a score for a response, which is the standard shape for the
  [online scoring](../scoring/online-scoring.md) results this handbook describes.
* **Conversation continuity.** `gen_ai.conversation.id` ties turns together; v0.1.0 also adds a conversation-compacted attribute for context compaction.

## Content capture

| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT` | Behaviour |
|---|---|
| `NO_CONTENT` (default) | No prompts or completions recorded |
| `SPAN_ONLY` | Content as span attributes |
| `EVENT_ONLY` | Content in the `operation.details` event |
| `SPAN_AND_EVENT` | Both |

Large or sensitive content can be stored externally and referenced with the `*_ref` attributes. See [Security, privacy & governance](../architecture/security-privacy.md);
redact in the Collector as a safety net ([pipeline](../implementation/collector-pipeline.md)).

## Where this repo's demos stand

The demo apps already use the stable-looking core (`gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.usage.*`, `gen_ai.agent.name`,
`gen_ai.conversation.id`). Gaps are listed with measured live-check findings in [Weaver & conformance](weaver-conformance.md#results-for-the-demo-apps).
