# Runbooks

Each alert should link to one of these. First move for any incident: **check the change-event overlay** (what changed in the last 24 h?).

## Latency regression

1. Confirm: TTFT vs total? p95 vs p50? Which tenants/features?
2. Stage breakdown: which stage's share grew (embed / retrieve / rerank / LLM / tools)?
3. Check provider status and regional latency; compare against another model/region if fallbacks exist.
4. Check `context_tokens` and output length: longer prompts and answers drive latency and cost.
5. Check vector DB saturation, index size/refresh, rerank service.
6. Mitigate: reduce top-k/context, enable caching, route to faster model, scale replicas, shed load for low-tier tenants.
7. Roll back the last change if correlated.

## Quality regression

1. Verify sample size and evaluator version (judge changes break trends).
2. Slice: which intent/tenant/index/prompt version? Compare to the 28-day baseline.
3. Inspect 10–20 lowest-score traces; classify: retrieval miss, ungrounded generation, prompt issue, format issue, data staleness.
4. Retrieval metrics: top-1 score, empty rate, doc freshness.
5. Check for provider-side model update (`response_model`, fingerprint) or embedding/index change.
6. Mitigate: roll back prompt/index/model; pin versions; adjust retrieval; add guardrail.
7. Add failing traces to the golden set.

## Cost spike

1. Break down by tenant, feature, model, prompt version, token direction.
2. Look for: retry storms, agent loops (steps/task), context bloat (`context_tokens`), model change, cache miss surge, abuse/bot traffic, eval-cost surge.
3. Apply guardrails: per-tenant rate limit/budget, max steps, max tokens, route to cheaper model.
4. Fix root cause; add a regression alert.

## Provider errors and rate limits

1. Check `error_type` split (429, 5xx, timeout, content-filter).
2. Verify quota/TPM headroom; request increase; spread across deployments/regions.
3. Ensure fallbacks work and are attributed (`fallback_used`, `response_model`).
4. Tune retries (exponential backoff + jitter, retry budget) to avoid amplifying the incident.

## Retrieval degradation

1. Empty-retrieval or low-score rate up? Which index/tenant?
2. Check ingestion pipeline (failed docs, lag), index version, embedding model parity between query and index.
3. Validate ACL filters (are legitimate docs excluded?).
4. Re-run retrieval golden set; compare recall@k with last good index.
5. Roll back index alias; fix ingestion; reindex.

## Agent runaway or loops

1. Confirm: steps-per-task p95, loop detections, terminations by reason (`max_steps`, `budget_exceeded`, `timeout`, `loop`), cost per task.
2. Open a few traces of terminated tasks (`span.loop.detected = true`): which tool and arguments repeat? Is the tool returning an error or an empty result the agent keeps retrying?
3. Check recent change events: prompt/tool-description edits, new tool, model switch, framework upgrade.
4. Mitigate: tighten hard limits (max steps, per-task USD budget, wall clock), add a loop breaker (same tool + args ≥ 3 → replan or stop), disable the offending tool, route to a different model.
5. Verify cost per *successful* task returns to baseline; add the failing trajectory to the regression suite.

## Tool dependency failing

1. Which tool (`agent_tool_calls_total{status="error"}` by `tool`)? Compare with the dependency's own health.
2. Check retries/replans: failures amplify cost through plan revisions.
3. Mitigate: circuit-break the tool, fall back to an alternate source, return a typed error the agent can reason about, cache stable results.

## Conversation quality or containment drop

1. Slice containment by intent and channel: one intent, or all?
2. Compare refusals (over-refusal), fallbacks (unsupported intents), goal-completion judge score, thumbs-down.
3. Check change events (prompt, model, retrieval/index, guardrail policy) and provider health.
4. Read 10-20 escalated or abandoned conversations (redacted) and classify the cause.
5. Mitigate: roll back prompt/model/guardrail policy; adjust thresholds; extend intent coverage; add failing cases to the golden set.

## Context window pressure

1. Context utilization p95, truncation events, tokens by turn index.
2. Mitigate: summarize or window history, cap retrieved context, compress tool outputs, move long-term state to memory.
3. Re-check cost per conversation and answer quality after the change.

## Safety / guardrail incident

1. Contain: tighten guardrail, disable affected feature/tool, block abusive tenant/user.
2. Collect evidence (traces, policy decisions) under access control.
3. Assess exposure (PII, cross-tenant) with security/privacy; follow breach procedure.
4. Fix; add test cases to red-team suite; post-incident review.

## Telemetry pipeline failure

1. Check Collector metrics: refused/dropped spans, exporter failures, queue saturation.
2. Fail open for the app (never block requests); enable local buffering.
3. Backfill from logs/object store if available; annotate the gap on dashboards.

## Post-incident

Blameless review: timeline with change events, detection gap (could we have caught it earlier with a leading indicator?), new alert/dashboard/golden-set items, owner and due date.
