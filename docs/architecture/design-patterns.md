# Design patterns for AI observability

## Instrumentation patterns

### 1. Gateway metering
Route all model calls through an AI gateway that stamps `tenant`, `feature`, `model`, `tokens`, `cost` on every call. Gives complete cost coverage even for un-instrumented apps. *Trade-off:* extra hop (~ms) and a shared failure domain — deploy redundantly.

### 2. OTel-first, vendor-second
Instrument with OpenTelemetry; export to a Collector; fan out to one or more backends. *Benefit:* swap vendors without touching app code.

### 3. Semantic wrapper (decorator) layer
Wrap `retrieve()`, `rerank()`, `generate()`, `call_tool()` in your own thin library that emits spans with the `app.*`/`rag.*` namespace. One library, used by every team, enforces consistent attributes and redaction.

### 4. Trace-linked evaluation (score write-back)
Evaluators consume sampled traces and write scores *back to the same `trace_id`*. Dashboards then slice quality by any trace attribute (tenant, prompt version, index version).

### 5. Shadow / canary evaluation
Send a copy of a sample of traffic to a candidate model/prompt/index; compare scores, latency and cost against production before promotion. Pair with feature flags and automatic rollback on SLO breach.

### 6. Golden-set regression gate
Curated Q&A set with expected facts/sources runs in CI and nightly in production-like config. A drop beyond threshold blocks release and pages the owner.

### 7. Feedback loop (data flywheel)
User thumbs/edits, escalations, and low-score traces are queued for review, triaged, then promoted into the golden set. Closes the loop between production and offline evaluation.

## Data patterns

### 8. Wide event per request
Persist one denormalized row per request/turn (50–150 columns) with latency per stage, tokens, cost, config versions, eval scores and user outcome. Cheap to aggregate for any time range; the backbone of trend analysis. See [Storage](storage-and-retention.md).

### 9. Tiered retention
Full detail short, aggregates long, raw content only where policy allows. See [Storage](storage-and-retention.md).

### 10. Content by reference
Store prompt/response bodies in a governed, access-controlled store; keep only IDs, hashes, lengths and redacted snippets in the general telemetry path.

### 11. Change events as first-class data
Deploys, prompt versions, model switches, index rebuilds, embedding changes, feature-flag flips, provider incidents — all written as events so dashboards overlay them on every chart.

## Reliability patterns

### 12. Telemetry must not break the app
Async batching, bounded queues, drop-on-overflow, timeouts; never block the request on export. Measure telemetry loss itself (dropped spans).

### 13. Budget guardrails
Per-tenant/feature token and cost budgets enforced at the gateway, with burn-rate alerts (e.g. 2% budget in 1 hour) and circuit breakers for runaway agents (max steps, max tokens, max wall-clock).

### 14. Provider fallback with attribution
Fallback chains (primary → secondary model) must record *which* model served the response; otherwise quality and cost shifts are invisible.

## Anti-patterns

| Anti-pattern | Why it hurts |
|---|---|
| Logging full prompts everywhere "just in case" | PII/secret exposure, huge storage bills, compliance risk |
| Judging 100% of traffic with a frontier model | Evaluation cost rivals product cost; sample and tier judges |
| Only averages | Long-tailed latency and cost hide in p95/p99 and top-1% tenants |
| No version tags | Cannot attribute a regression to a prompt/model/index change |
| Treating thumbs-up as ground truth | Sparse and biased; combine with automated and human evals |
| Separate silo per team | Inconsistent attributes make enterprise rollups impossible |
| Alert on every score dip | Alert fatigue; alert on SLO burn and statistically significant shifts |
