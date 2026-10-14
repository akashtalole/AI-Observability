-- Wide per-request fact table for RAG / chat apps (ClickHouse).
-- One row per user turn. Long retention (13-24 months); content is NOT stored here.

CREATE TABLE IF NOT EXISTS ai_request_facts
(
    ts                    DateTime64(3, 'UTC'),
    trace_id              String,
    conversation_id       String,
    app                   LowCardinality(String),
    feature               LowCardinality(String),
    intent                LowCardinality(String),
    tenant_id             LowCardinality(String),
    environment           LowCardinality(String),
    region                LowCardinality(String),

    -- change attribution
    release_id            LowCardinality(String),
    prompt_id             LowCardinality(String),
    prompt_version        LowCardinality(String),
    model                 LowCardinality(String),
    response_model        LowCardinality(String),
    provider              LowCardinality(String),
    embedding_model       LowCardinality(String),
    index_id              LowCardinality(String),
    index_version         LowCardinality(String),

    -- latency (ms)
    latency_total_ms      Float32,
    ttft_ms               Float32,
    latency_embed_ms      Float32,
    latency_retrieve_ms   Float32,
    latency_rerank_ms     Float32,
    latency_llm_ms        Float32,
    latency_guardrail_ms  Float32,

    -- tokens and cost
    input_tokens          UInt32,
    output_tokens         UInt32,
    cached_tokens         UInt32,
    context_tokens        UInt32,
    cost_usd_llm          Float64,
    cost_usd_embed        Float64,
    cost_usd_rerank       Float64,
    cost_usd_total        Float64,

    -- retrieval
    retrieved_count       UInt16,
    top1_score            Float32,
    cache_hit             UInt8,

    -- outcome
    status                LowCardinality(String),   -- ok | error | blocked | timeout
    error_type            LowCardinality(String),
    fallback_used         UInt8,
    retry_count           UInt8,

    -- quality (written back asynchronously; NaN = not evaluated)
    eval_groundedness     Float32 DEFAULT nan,
    eval_relevance        Float32 DEFAULT nan,
    eval_context_prec     Float32 DEFAULT nan,
    eval_version          LowCardinality(String),
    feedback_rating       Int8 DEFAULT 0              -- -1 down, 0 none, 1 up
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (app, environment, toStartOfHour(ts), tenant_id, trace_id)
TTL toDateTime(ts) + INTERVAL 18 MONTH;

-- Hourly rollup with mergeable quantile states: query any range from months of data cheaply.
CREATE TABLE IF NOT EXISTS ai_hourly_rollup
(
    hour                  DateTime('UTC'),
    app                   LowCardinality(String),
    environment           LowCardinality(String),
    tenant_id             LowCardinality(String),
    model                 LowCardinality(String),
    prompt_version        LowCardinality(String),
    index_version         LowCardinality(String),

    requests              SimpleAggregateFunction(sum, UInt64),
    errors                SimpleAggregateFunction(sum, UInt64),
    input_tokens          SimpleAggregateFunction(sum, UInt64),
    output_tokens         SimpleAggregateFunction(sum, UInt64),
    cost_usd              SimpleAggregateFunction(sum, Float64),
    latency_q             AggregateFunction(quantilesTDigest(0.5, 0.95, 0.99), Float32),
    ttft_q                AggregateFunction(quantilesTDigest(0.5, 0.95, 0.99), Float32),
    retrieve_q            AggregateFunction(quantilesTDigest(0.5, 0.95, 0.99), Float32),
    groundedness_sum      SimpleAggregateFunction(sum, Float64),
    groundedness_n        SimpleAggregateFunction(sum, UInt64),
    relevance_sum         SimpleAggregateFunction(sum, Float64),
    relevance_n           SimpleAggregateFunction(sum, UInt64),
    thumbs_up             SimpleAggregateFunction(sum, UInt64),
    thumbs_down           SimpleAggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (app, environment, tenant_id, model, prompt_version, index_version, hour);

CREATE MATERIALIZED VIEW IF NOT EXISTS ai_hourly_rollup_mv TO ai_hourly_rollup AS
SELECT
    toStartOfHour(ts)                                         AS hour,
    app, environment, tenant_id, model, prompt_version, index_version,
    count()                                                   AS requests,
    countIf(status != 'ok')                                   AS errors,
    sum(input_tokens)                                         AS input_tokens,
    sum(output_tokens)                                        AS output_tokens,
    sum(cost_usd_total)                                       AS cost_usd,
    quantilesTDigestState(0.5, 0.95, 0.99)(latency_total_ms)  AS latency_q,
    quantilesTDigestState(0.5, 0.95, 0.99)(ttft_ms)           AS ttft_q,
    quantilesTDigestState(0.5, 0.95, 0.99)(latency_retrieve_ms) AS retrieve_q,
    sumIf(eval_groundedness, NOT isNaN(eval_groundedness))    AS groundedness_sum,
    countIf(NOT isNaN(eval_groundedness))                     AS groundedness_n,
    sumIf(eval_relevance, NOT isNaN(eval_relevance))          AS relevance_sum,
    countIf(NOT isNaN(eval_relevance))                        AS relevance_n,
    countIf(feedback_rating = 1)                              AS thumbs_up,
    countIf(feedback_rating = -1)                             AS thumbs_down
FROM ai_request_facts
GROUP BY hour, app, environment, tenant_id, model, prompt_version, index_version;

-- Change events (deploys, prompt/model/index changes) overlaid on every chart.
CREATE TABLE IF NOT EXISTS ai_change_events
(
    ts          DateTime64(3, 'UTC'),
    app         LowCardinality(String),
    kind        LowCardinality(String),   -- deploy | prompt | model | index | embedding | config | incident
    ref         String,                   -- version / commit / ticket
    description String,
    actor       String
)
ENGINE = MergeTree
ORDER BY (app, ts);

-- NOTE: quality scores arrive after the request. Insert a corrected row via an
-- evaluation-results table joined at query time, or use ReplacingMergeTree keyed by
-- trace_id if you prefer write-back into the fact table. The simplest robust pattern is:
CREATE TABLE IF NOT EXISTS ai_eval_scores
(
    ts            DateTime64(3, 'UTC'),
    trace_id      String,
    app           LowCardinality(String),
    metric        LowCardinality(String),   -- groundedness | relevance | context_precision ...
    score         Float32,
    eval_version  LowCardinality(String),
    judge_model   LowCardinality(String),
    eval_cost_usd Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (app, metric, ts)
TTL toDateTime(ts) + INTERVAL 18 MONTH;
