# Dashboards & queries

Interactive mock-up: open the [RAG dashboard demo](../artifacts/index.md) (HTML artifact) and switch the time range from 1 hour to 12 months.

## Dashboard set

| # | Dashboard | Audience | Default range | Source |
|---|---|---|---|---|
| 1 | **Executive / product health** | Product, leadership | 30 d / 12 mo | Rollups |
| 2 | **Service health & SLOs** | SRE, on-call | 6 h – 7 d | Metrics TSDB |
| 3 | **Latency deep dive** | AI/platform engineers | 24 h – 30 d | Metrics + facts |
| 4 | **Retrieval & quality** | AI engineers | 7 d – 90 d | Facts + eval scores |
| 5 | **Cost & FinOps** | FinOps, owners | 30 d – 12 mo | Rollups + billing |
| 6 | **Change impact** | Release managers | around events | Facts + events |
| 7 | **Trace explorer / triage** | Everyone | live | Trace backend |

## Layout of the main RAG dashboard

```text
┌───────────────────────────────────────────────────────────────────────┐
│ [Range: 1h 6h 24h 7d 30d 90d 12m custom] [app] [env] [tenant] [model] │
├────────────┬────────────┬────────────┬────────────┬───────────────────┤
│ Requests   │ Error %    │ p95 TTFT   │ Groundedn. │ Cost / request    │  ← KPI tiles with Δ vs previous period
├────────────┴────────────┴────────────┴────────────┴───────────────────┤
│ Latency p50/p95/p99 over time  ▏▏▏ change-event markers ▏▏▏          │
├──────────────────────────────────┬────────────────────────────────────┤
│ Stage latency (stacked)          │ Cost over time by model            │
├──────────────────────────────────┼────────────────────────────────────┤
│ Quality scores (+ n, CI band)    │ Retrieval: top-1 score, empty rate │
├──────────────────────────────────┼────────────────────────────────────┤
│ Thumbs-down by intent            │ Top tenants by cost                │
├──────────────────────────────────┴────────────────────────────────────┤
│ Worst traces (slow / costly / low-score) → click-through to trace     │
└───────────────────────────────────────────────────────────────────────┘
```

## Range → data source mapping

| Selected range | Granularity | Source |
|---|---|---|
| ≤ 6 h | 15 s – 1 min | Prometheus/OTel metrics |
| 6 h – 14 d | 5 min – 1 h | Prometheus + hourly rollup |
| 14 d – 90 d | 1 h – 1 d | Hourly rollup table |
| 90 d – 18 mo | 1 d – 1 week | Daily rollup / monthly `GROUP BY` on hourly rollup |

In Grafana, use the `$__interval`/`$__range` variables to switch queries, or a ClickHouse query that derives the bucket from the range, e.g. `toStartOfInterval(hour, INTERVAL $__interval_s second)`.

## SQL (ClickHouse)

All eight queries are in [`examples/sql/rag_queries.sql`](https://github.com/akashtalole/ai-observability/blob/main/examples/sql/rag_queries.sql):

1. Latency percentiles over any range (merging t-digest states)
2. Cost per request by model & prompt version
3. Weekly quality trend with sample size per index version
4. Stage share of slow requests
5. Month-over-month cost / p95 / groundedness
6. Top tenants by cost
7. Retrieval health (empty & low-score rate)
8. Before/after comparison around a change event

## PromQL

```promql
# p95 TTFT per app (5m)
histogram_quantile(0.95, sum by (app, le) (rate(rag_ttft_seconds_bucket[5m])))

# Error ratio
sum(rate(rag_requests_total{status!="ok"}[5m])) / sum(rate(rag_requests_total[5m]))

# Spend per hour, by model
sum by (gen_ai_request_model) (increase(rag_cost_usd_total[1h]))

# Cost per request, 24h
sum(increase(rag_cost_usd_total[24h])) / sum(increase(rag_requests_total[24h]))

# Tokens in/out ratio (context bloat indicator)
sum(rate(rag_tokens_total{direction="input"}[1h])) / sum(rate(rag_tokens_total{direction="output"}[1h]))

# Week-over-week p95 latency change
histogram_quantile(0.95, sum by (le) (rate(rag_request_duration_seconds_bucket[1h])))
/ histogram_quantile(0.95, sum by (le) (rate(rag_request_duration_seconds_bucket[1h] offset 7d)))
```

!!! note
    Prometheus keeps raw resolution for weeks, not years. For 6–18-month views use long-term storage (Mimir/Thanos/VictoriaMetrics) with downsampling, **or** serve those panels from the ClickHouse rollups.

## Example KQL (Azure Log Analytics / App Insights)

```kusto
AppDependencies
| where Name startswith "chat"
| extend model = tostring(Properties["gen_ai.request.model"]),
         tin = toint(Properties["gen_ai.usage.input_tokens"]),
         tout = toint(Properties["gen_ai.usage.output_tokens"])
| summarize p95_ms = percentile(DurationMs, 95), requests = count(),
            in_tokens = sum(tin), out_tokens = sum(tout)
  by bin(TimeGenerated, 1d), model
| order by TimeGenerated asc
```

## Example CloudWatch Logs Insights (Bedrock invocation logs)

```text
fields @timestamp, modelId, input.inputTokenCount as tin, output.outputTokenCount as tout
| stats count() as requests, sum(tin) as in_tokens, sum(tout) as out_tokens by bin(1d), modelId
```
