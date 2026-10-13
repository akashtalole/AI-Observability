# TCO model

Compare options on a **3-year, 3× growth** horizon. Pricing models differ (per trace/event/span, per seat, per GB, flat), so normalize on your own volumes.

## Inputs

| Input | Symbol | Example |
|---|---|---|
| Requests per day | `R` | 2,000,000 |
| Spans per request | `S` | 15 |
| Avg bytes per span (no content) | `B` | 1 KB |
| Content bytes per request (if captured) | `Cb` | 20 KB |
| Content capture ratio | `p` | 10 % |
| Hot retention days | `Dh` | 14 |
| Warm retention months | `Mw` | 18 |
| Online eval sampling rate | `e` | 3 % |
| Cost per judge call | `J` | from your model price |
| Engineers/users with seats | `U` | 40 |

## Cost components

```text
Build / self-host monthly cost =
    compute(collector, UI/workers, ClickHouse/OpenSearch, TSDB)
  + storage(hot Dh, warm Mw, cold)  # R*S*B*Dh + R*row_bytes*Mw*30 + R*p*Cb*retention
  + network egress / cross-AZ
  + platform engineering FTE share
  + on-call & security/compliance overhead
  + evaluation compute (R*30*e*J)

SaaS monthly cost =
    platform fee/seats (U)
  + ingest/volume overage (events, spans, GB)
  + retention add-ons / export fees
  + evaluation (vendor-hosted judge usage or your own J)
  + integration & governance effort

Hidden costs (both) =
    migration/re-instrumentation if you leave
  + incident cost when observability is down
  + analyst time to answer cost/quality questions without SQL access
```

## Worked sketch (illustrative only — not vendor quotes)

| Item | Self-host OSS | SaaS (volume priced) | Cloud-native |
|---|---|---|---|
| Infra / ingestion | Compute + storage for ~30 M spans/day | Priced per span/event; scales linearly | Priced per GB ingested (+ retention) |
| People | 0.5–1.5 FTE | 0.1–0.3 FTE (integration, governance) | 0.2–0.5 FTE |
| Evaluation | Your judge calls | Your judge calls or bundled | Native evaluators (billed as model usage) |
| Exit cost | Low | Medium–high | Medium–high |
| Scaling behavior | Step-function (capacity) | Linear / tiered cliffs | Linear |

## Levers to cut observability cost (any option)

1. **Sample healthy traces**, keep 100 % of errors/slow/low-score (tail sampling).
2. **Compute metrics before sampling**; sample only the trace bodies.
3. **Content by reference**, truncated content, shorter hot retention.
4. **Tier judges**: heuristic checks on 100 %, small-model judge on sampled, frontier judge on flagged/golden sets.
5. **Drop low-value spans** (internal chunk-loop spans) — aggregate into attributes instead.
6. **Compress and downsample** warm data into rollups.

## Decision hint

If observability + eval cost projects above ~10 % of LLM inference spend, or the vendor price curve is superlinear in your growth, evaluate self-hosting the high-volume path (traces, facts) while keeping SaaS for the high-value collaboration features (prompt management, annotation, eval UI).
