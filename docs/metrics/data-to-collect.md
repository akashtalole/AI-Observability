# Data to collect

A checklist of the fields to capture per request, per span, and per event — and what to **avoid** capturing.

## Per request (one wide fact row per user turn)

| Group | Fields |
|---|---|
| **Identity & context** | `trace_id`, `session_id`/`conversation_id`, `turn_index`, `timestamp`, `app`, `feature`, `intent` (classified), `tenant_id`, `user_id_hash`, `channel`, `locale`, `environment`, `region` |
| **Versions (change attribution)** | `release_id`, `git_sha`, `prompt_id`, `prompt_version`, `model`, `model_version`/`response_model`, `provider`, `embedding_model`, `index_id`, `index_version`, `reranker`, `guardrail_policy_version`, `feature_flags` |
| **Latency** | `latency_total_ms`, `ttft_ms`, `latency_embed_ms`, `latency_retrieve_ms`, `latency_rerank_ms`, `latency_prompt_build_ms`, `latency_llm_ms`, `latency_tools_ms`, `latency_guardrail_ms`, `queue_ms`, `tokens_per_sec` |
| **Tokens & cost** | `input_tokens`, `output_tokens`, `cached_tokens`, `reasoning_tokens`, `embedding_tokens`, `cost_usd_llm`, `cost_usd_embed`, `cost_usd_rerank`, `cost_usd_tools`, `cost_usd_total`, `price_table_version` |
| **Retrieval (RAG)** | `retrieval_top_k`, `retrieved_count`, `top1_score`, `mean_score`, `retrieved_doc_ids[]`, `cited_doc_ids[]`, `context_tokens`, `acl_filtered_count`, `cache_hit` (semantic/prompt), `query_rewrite` flag |
| **Agent** | `steps`, `tool_calls`, `tool_errors`, `loops_detected`, `max_depth`, `plan_revisions`, `handoffs`, `terminated_reason` |
| **Outcome & errors** | `status`, `error_type`, `finish_reason`, `retry_count`, `fallback_used`, `served_model`, `refusal` |
| **Quality (async write-back)** | `eval_groundedness`, `eval_answer_relevance`, `eval_context_precision`, `eval_task_success`, `eval_safety`, `eval_version`, `judge_model`, `eval_cost_usd` |
| **Safety** | `guardrail_input_verdict`, `guardrail_output_verdict`, `pii_detected`, `injection_score` |
| **User signal** | `feedback_rating`, `feedback_comment_ref`, `regenerated`, `escalated`, `copied`, `abandoned` |

## Per span (traces)

* Span name by operation (`rag.retrieve`, `rerank`, `chat gpt-…`, `execute_tool search_kb`).
* Standard `gen_ai.*` attributes, duration, status, error type/message (sanitized).
* Retrieval spans: query hash/length, top-k, filter summary, per-chunk `doc_id`, `score`, `rank`, `chunk_tokens` (not text by default).
* LLM spans: model, params, token usage, finish reason, TTFT; prompt template ID + version + variable *names*.
* Tool spans: tool name, arg schema validity, result size, status, side-effect class (read/write).

## Events and annotations

* Evaluation results and annotations (human review decisions).
* Guardrail decisions.
* **Change events**: deploy, prompt promoted, model switch, index rebuild, embedding model change, config/flag change, provider incident.
* Budget/SLO alerts fired and resolved.

## Content: capture rules

| Content | Default | When to capture | How |
|---|---|---|---|
| User question | Hash + length + intent label | Debug mode; sampled; flagged traces | Redacted, access-controlled store |
| Retrieved chunks | Doc IDs + scores | Debug/golden-set building | Store chunk **ID/version**; resolve text from source of truth on demand |
| Full prompt | Template ID/version + variable names | Flagged traces only | Redacted |
| Model answer | Length + hash + eval scores | Sampled + flagged | Redacted |
| Tool I/O | Schema + sizes + status | Failures | Redacted |

## Do **not** collect (or only with explicit approval)

* Raw secrets/credentials, API keys, auth tokens.
* Unredacted PII/PHI/PCI in prompts or answers.
* Biometric or special-category data from voice/images without a legal basis.
* Free-text user identifiers as metric labels.
* Entire documents when a chunk ID suffices.

## Metric labels vs. fact columns

| Put on metric labels (low cardinality) | Keep only in facts/traces (high cardinality) |
|---|---|
| app, feature, env, region, model, provider, prompt_version, index_version, status, error_type, tenant (bounded) | user, session, trace, doc IDs, query text, free-text feedback |
