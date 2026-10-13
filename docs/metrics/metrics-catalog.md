# Metrics catalog

Organized by **what you want to know**. "Where" says the telemetry type: **M** metric, **T** trace/span attribute, **E** evaluation score, **F** wide-fact column.

## 1. Latency

| Metric | Definition | Where | Notes |
|---|---|---|---|
| End-to-end latency | request received → final byte | M, T, F | p50/p95/p99, by app/feature/tenant |
| **Time to first token (TTFT)** | request → first streamed token | M, T, F | Primary UX metric for chat |
| Time per output token / tokens per second | decode speed | M, T | Capacity and model health |
| Stage latency | embed, retrieve, rerank, prompt build, LLM, tool, guardrail | T, F | Where the time goes |
| Queue / wait time | gateway/model queueing | M | Saturation indicator |
| Tool call latency | per tool | M, T | Agent bottleneck |
| Agent steps & wall-clock | steps per task, total time | M, F | Loop detection |
| Cache hit latency delta | hit vs miss | M | Prompt/semantic cache value |

## 2. Cost

| Metric | Definition | Where |
|---|---|---|
| Input / output / cached / reasoning tokens | from provider usage | M, T, F |
| **Cost per request** | tokens × price table + retrieval + tool + infra | F |
| Cost per successful task / per resolved conversation | cost ÷ successes | F |
| Cost by tenant / feature / model / prompt version | attribution | F |
| Budget burn rate | spend ÷ budget over window | M |
| Embedding & reranking cost | tokens/calls | M, F |
| Vector DB & infra cost per 1k queries | allocated | F |
| Eval cost | judge tokens ÷ evaluated traces | F |
| Cache savings | avoided tokens × price | F |
| Retry / failed-call waste | tokens on errored/retried calls | M |

## 3. Quality

| Metric | Definition | Where | Applies to |
|---|---|---|---|
| **Groundedness / faithfulness** | answer claims supported by context | E | RAG |
| **Answer relevance** | answers the question | E | all |
| Context relevance / precision | retrieved chunks are relevant (ranked well) | E | RAG |
| Context recall | needed facts were retrieved | E (needs reference) | RAG |
| Citation accuracy | cited source supports claim | E | RAG |
| Task success / goal completion | user goal met | E, F | agents, chatbots |
| Correctness vs reference | match to golden answer | E | offline |
| Tool selection & argument accuracy | right tool, valid args | E | agents |
| Trajectory efficiency | steps vs optimal | E | agents |
| Format/schema validity | parse success | M | structured output |
| Refusal & over-refusal rate | policy refusals | M, E | all |
| Hallucination rate | ungrounded claims | E | all |
| Toxicity / bias / safety | classifier scores | E | all |
| Consistency | variance across paraphrases/runs | E | all |

## 4. User outcome

| Metric | Where |
|---|---|
| Thumbs up/down rate, ratings | M, F |
| Regeneration / edit / copy rate | M, F |
| Escalation to human, deflection rate | M, F |
| Abandonment, conversation length, re-asks | F |
| Time to resolution, CSAT/NPS (linked) | F |
| Adoption: DAU/WAU, queries per user | M |

## 5. Reliability and capacity

| Metric | Notes |
|---|---|
| Error rate by type (timeout, 429, 5xx, content filter, parse error) | Break down by provider/model |
| Availability/SLO attainment & error-budget burn | See [SLOs](slos-alerting.md) |
| Rate-limit/quota headroom (TPM/RPM) | Per deployment/region |
| Fallback / failover rate | Which model served |
| Retry rate | Hidden latency and cost |
| Concurrent requests, queue depth, GPU utilization (self-hosted) | See [self-hosted](../monitoring/self-hosted-models.md) |

## 6. Retrieval and data health (RAG)

| Metric | Notes |
|---|---|
| Retrieved count, similarity score distribution (min/mean/top1) | Low top-1 score ⇒ coverage gap |
| Empty/low-score retrieval rate | "I don't know" opportunities |
| Index freshness (age of newest/median doc), ingestion lag | Staleness |
| Chunk coverage / usage rate (retrieved ÷ used in answer) | Context waste |
| Context tokens per request | Cost and "lost in the middle" |
| Rerank lift (relevance after vs before) | Reranker value |
| Source distribution & tenant ACL filter hit rate | Security correctness |
| Embedding drift (query vs index distribution) | Retrain/reindex signal |

## 7. Safety, security, compliance

| Metric | Notes |
|---|---|
| Guardrail trigger rate by category and action | Input and output |
| Prompt-injection detections (direct, indirect via retrieval) | |
| PII detections pre/post redaction | |
| Policy violation incidents, time to remediate | |
| Unauthorized tool-call attempts (agents) | |

## 8. Drift and change indicators

* Input distribution drift (topic/intent mix, length, language).
* Output distribution drift (length, refusal rate, style).
* Score drift vs rolling baseline.
* **Change annotations**: model/provider version, prompt version, index/embedding version, config & flag changes, deploys.

## Dimensions (slice every metric by)

`app`, `feature/intent`, `tenant`, `environment`, `region`, `model`, `provider`, `prompt_version`, `index_version`, `embedding_model`, `release`, `user_segment`, `channel`, `language`. **Keep high-cardinality ones (user, session, trace) out of metric labels** — keep them in facts and traces.
