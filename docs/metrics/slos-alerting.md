# SLOs & alerting

## Example SLO set for a RAG chatbot

| SLI | SLO (30-day window) | Measured from |
|---|---|---|
| Availability: non-error responses ÷ requests | 99.5 % | gateway/app metrics |
| TTFT p95 | ≤ 2.0 s | histogram |
| End-to-end latency p95 | ≤ 8 s | histogram |
| Groundedness (sampled, judge ≥ 0.8) | ≥ 95 % of sampled answers | eval scores |
| Answer relevance ≥ 0.8 | ≥ 92 % | eval scores |
| Safety: harmful-output rate | ≤ 0.1 % | guardrail + eval |
| Cost per resolved conversation | ≤ $0.12 (monthly avg) | cost facts |
| Index freshness: p95 doc age lag | ≤ 24 h | ingestion metrics |

!!! tip
    Quality SLOs are *statistical*: sampled, with confidence intervals. Alert on sustained shifts, not on a single bad batch.

## Alert design

| Alert type | Example | Method | Severity |
|---|---|---|---|
| **SLO burn-rate** | TTFT burning budget at 14× over 1 h *and* 6× over 6 h | multi-window burn rate | page |
| **Hard failure** | error rate > 5 % for 5 min; provider 429s spike | threshold | page |
| **Cost spike** | spend/hour > 3× 7-day same-hour median; tenant > 5× baseline | anomaly / ratio | ticket → page if budget breach |
| **Cost budget** | 80 % of monthly tenant budget by day 15 | forecast | ticket |
| **Quality regression** | rolling-24 h groundedness mean drops > 0.05 vs 28-day baseline (p < 0.01) | statistical test | ticket / page for regulated |
| **Retrieval health** | empty-retrieval rate > 2× baseline; top-1 score median drops | baseline band | ticket |
| **Agent runaway** | steps > N or tokens/task > 5× p95 | threshold | page (cost risk) |
| **Safety** | injection/PII detection rate jump; any critical policy breach | threshold + any-event | page |
| **Telemetry health** | span drop rate > 1 %; eval backlog > X min; ingestion lag | pipeline metrics | ticket |
| **Change correlation** | metric shift within 2 h of a change event | auto-annotation | info |

## Burn-rate formula

```text
burn_rate = (observed bad-event ratio) / (1 - SLO target)
page when burn_rate(1h) > 14.4 AND burn_rate(5m) > 14.4     # ~2 % of 30-day budget in 1h
page when burn_rate(6h) > 6   AND burn_rate(30m) > 6
ticket when burn_rate(3d) > 1
```

## Reducing noise

* Alert on **user-visible SLO impact** first; route diagnostic signals to dashboards.
* Require minimum sample size before quality alerts (e.g. ≥ 200 scored traces/window).
* Group by `app` + `change event` to avoid duplicate pages.
* Every alert links to: dashboard, example traces, last change events, runbook ([runbooks](../operations/runbooks.md)).

Prometheus rule examples: [`examples/alerts/ai-slo-alerts.yml`](https://github.com/akashtalole/ai-observability/blob/main/examples/alerts/ai-slo-alerts.yml).
