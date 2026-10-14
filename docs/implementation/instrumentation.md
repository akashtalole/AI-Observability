# Instrumentation guide

## Approaches

| Approach | Effort | Fidelity | Notes |
|---|---|---|---|
| **Auto-instrumentation** (OpenLLMetry, OpenInference, OpenLIT, vendor SDKs) | Low | Provider/framework calls | Good start; misses business context |
| **Manual spans** with OTel API | Medium | High | Needed for retrieval stages, versions, cost |
| **Gateway metering** | Low | Model calls only | Complete coverage, no semantics |
| **Framework callbacks** (LangChain/LlamaIndex/…) | Low | Framework steps | Often bridged to OTel |

**Recommended:** auto-instrument model + vector DB clients, add a thin manual layer for stage spans and `app.*`/`rag.*` attributes, meter at the gateway.

## Steps

1. **Pick conventions.** `gen_ai.*` for model calls; your own `app.*`/`rag.*` for the rest ([Telemetry model](../fundamentals/telemetry-model.md)).
2. **Create a shared wrapper library** (`ai_telemetry`) exposing context managers/decorators: `retrieval_span`, `llm_span`, `tool_span`, `record_cost`, `record_feedback`.
3. **Propagate context** across services, queues and MCP/tool calls (`traceparent`; carry `conversation_id` as baggage or attribute).
4. **Stamp versions** at startup from config/CI: `release_id`, prompt IDs/versions, model, embedding model, index version.
5. **Compute cost** in the wrapper from a versioned price table (cached/reasoning tokens priced separately).
6. **Handle streaming**: record TTFT at first chunk, close the span on stream end or client abort; record `finish_reason`.
7. **Capture feedback** with the originating `trace_id` so thumbs/edits join to traces and scores.
8. **Gate content capture** by flag + sampling + redaction.
9. **Test**: unit-test the wrapper with an in-memory exporter; assert required attributes exist; seed PII fixtures to verify redaction.

## Required attribute contract (enforce in CI)

```yaml
root_span: [app.tenant.id, app.feature, app.environment, app.release.id, cost.usd.total]
retrieve:  [rag.index.version, rag.embedding.model, rag.retrieval.top_k, rag.retrieval.count, rag.retrieval.top1_score]
llm:       [gen_ai.request.model, gen_ai.response.model, gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, app.prompt.id, app.prompt.version]
tool:      [gen_ai.tool.name, tool.status]
```

## Python example (runnable)

See [`examples/rag-otel/instrument.py`](https://github.com/akashtalole/ai-observability/blob/main/examples/rag-otel/instrument.py): stage spans, versions, token/cost metrics, TTFT histogram. Excerpt:

```python
with tracer.start_as_current_span("rag.request") as root:
    root.set_attribute("app.tenant.id", cfg.tenant)
    chunks = retrieve(query, cfg)            # rag.retrieve span: top_k, count, top1_score, doc_ids
    result = generate(query, chunks, cfg)    # chat <model> span: tokens, finish_reason, TTFT
    usd = (result.in_tok * p_in + result.out_tok * p_out) / 1_000_000
    root.set_attribute("cost.usd.total", usd)
    cost.add(usd, dims); ttft.record(result.ttft_s, dims)
```

## Linking evaluation and feedback

```python
# After the request: attach feedback to the original trace
with tracer.start_as_current_span("feedback", links=[trace.Link(original_span_context)]) as s:
    s.set_attribute("feedback.rating", -1)
    s.set_attribute("feedback.reason", "incorrect")
```

For evaluator write-back, insert `(trace_id, metric, score, eval_version, judge_model)` into your score table ([`ai_eval_scores`](https://github.com/akashtalole/ai-observability/blob/main/examples/sql/clickhouse_schema.sql)) or use your platform's score API.

## Common pitfalls

| Pitfall | Fix |
|---|---|
| Spans never closed on streaming/abort | Use `try/finally`; close on disconnect |
| Cost computed from character count | Use provider usage; fall back to tokenizer with flag `usage_estimated=true` |
| Metrics computed after sampling | Compute before sampler (spanmetrics) or in-app |
| Prompt text as attribute | Use IDs/versions; content via controlled event path |
| Different attribute names per team | Shared wrapper + contract test |
| Missing model version on fallbacks | Record `gen_ai.response.model` and `fallback_used` |
