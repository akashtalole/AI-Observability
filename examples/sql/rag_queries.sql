-- Queries behind the RAG dashboards (ClickHouse). Replace {range_start}/{range_end} with the dashboard time range.

-- 1) Latency percentiles over any range (merge rollup states; never average percentiles)
SELECT
    toStartOfDay(hour) AS day,
    quantilesTDigestMerge(0.5, 0.95, 0.99)(latency_q) AS lat_ms,
    quantilesTDigestMerge(0.5, 0.95, 0.99)(ttft_q)    AS ttft_ms
FROM ai_hourly_rollup
WHERE app = 'support-rag' AND environment = 'prod'
  AND hour >= {range_start:DateTime} AND hour < {range_end:DateTime}
GROUP BY day ORDER BY day;

-- 2) Cost per request and per 1k requests, by model and prompt version
SELECT
    model, prompt_version,
    sum(requests)                       AS requests,
    sum(cost_usd)                       AS cost_usd,
    sum(cost_usd) / sum(requests)       AS cost_per_request,
    sum(input_tokens) / sum(requests)   AS avg_in_tokens,
    sum(output_tokens) / sum(requests)  AS avg_out_tokens
FROM ai_hourly_rollup
WHERE app = 'support-rag' AND hour >= now() - INTERVAL 30 DAY
GROUP BY model, prompt_version
ORDER BY cost_usd DESC;

-- 3) Quality trend (weekly) with sample size, annotated by index_version
SELECT
    toMonday(hour)                                  AS week,
    index_version,
    sum(groundedness_sum) / sum(groundedness_n)     AS groundedness,
    sum(groundedness_n)                             AS scored_n,
    sum(relevance_sum) / sum(relevance_n)           AS relevance
FROM ai_hourly_rollup
WHERE app = 'support-rag' AND hour >= now() - INTERVAL 6 MONTH
GROUP BY week, index_version
HAVING scored_n >= 100
ORDER BY week;

-- 4) Where is the time going? Stage share of p95-slow requests (last 7 days)
SELECT
    avg(latency_embed_ms)     AS embed,
    avg(latency_retrieve_ms)  AS retrieve,
    avg(latency_rerank_ms)    AS rerank,
    avg(latency_llm_ms)       AS llm,
    avg(latency_guardrail_ms) AS guardrail
FROM ai_request_facts
WHERE app = 'support-rag' AND ts >= now() - INTERVAL 7 DAY
  AND latency_total_ms >= (
      SELECT quantile(0.95)(latency_total_ms) FROM ai_request_facts
      WHERE app = 'support-rag' AND ts >= now() - INTERVAL 7 DAY);

-- 5) Month-over-month: cost, p95 latency, groundedness
SELECT
    toStartOfMonth(hour)                                   AS month,
    sum(cost_usd)                                          AS cost_usd,
    sum(cost_usd) / sum(requests)                          AS cost_per_request,
    quantilesTDigestMerge(0.95)(latency_q)[1]              AS p95_latency_ms,
    sum(groundedness_sum) / sum(groundedness_n)            AS groundedness
FROM ai_hourly_rollup
WHERE app = 'support-rag' AND hour >= now() - INTERVAL 18 MONTH
GROUP BY month ORDER BY month;

-- 6) Top cost tenants and their share
SELECT tenant_id, sum(cost_usd) AS cost_usd,
       round(100 * cost_usd / sum(cost_usd) OVER (), 1) AS pct
FROM ai_hourly_rollup
WHERE app = 'support-rag' AND hour >= now() - INTERVAL 30 DAY
GROUP BY tenant_id ORDER BY cost_usd DESC LIMIT 20;

-- 7) Retrieval health: low-score and empty retrieval rate by day
SELECT toDate(ts) AS day,
       countIf(retrieved_count = 0) / count()        AS empty_rate,
       countIf(top1_score < 0.35) / count()          AS low_top1_rate,
       quantile(0.5)(top1_score)                     AS top1_median
FROM ai_request_facts
WHERE app = 'support-rag' AND ts >= now() - INTERVAL 90 DAY
GROUP BY day ORDER BY day;

-- 8) Regression check around a change event: 7 days before vs 7 days after
WITH e AS (SELECT ts FROM ai_change_events WHERE app = 'support-rag' AND kind = 'prompt' ORDER BY ts DESC LIMIT 1)
SELECT
    if(f.ts < (SELECT ts FROM e), 'before', 'after') AS period,
    count()                                    AS n,
    quantile(0.95)(f.latency_total_ms)         AS p95_ms,
    avg(f.cost_usd_total)                      AS avg_cost,
    avgIf(f.eval_groundedness, NOT isNaN(f.eval_groundedness)) AS groundedness
FROM ai_request_facts AS f
WHERE f.app = 'support-rag'
  AND f.ts BETWEEN (SELECT ts FROM e) - INTERVAL 7 DAY AND (SELECT ts FROM e) + INTERVAL 7 DAY
GROUP BY period;
