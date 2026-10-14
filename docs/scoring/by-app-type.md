# Scoring by application type

For each type: what to score **offline** (with references), what to score **online** (reference-free), and the **cheap flags** that decide where to spend judge budget.

## RAG

| | Scorers |
|---|---|
| **Offline** | Retrieval: recall@k, MRR, nDCG against labeled relevant chunks; rerank lift. Answer: required-fact recall, correctness vs reference, citation precision/recall, **abstention accuracy** on unanswerable items. Faithfulness judge. Component-level scores localize failures (retrieval vs generation). |
| **Online** | Groundedness (claim verification), answer relevance, context relevance/precision (judge), citation validity (deterministic), user feedback. |
| **Cheap flags** | Empty/low top-1 retrieval, no citation, answer longer than context supports, index age, ACL-filtered-to-zero. |
| **Watch for** | Quality dips that follow reindex/chunking/embedding changes; staleness; cross-tenant leakage canaries. |

Live example: [RAG use case](../use-cases/rag.md) scores `groundedness`, `answer_relevance`, `context_precision` asynchronously and links scores to traces.

## Agents and multi-agent

| | Scorers |
|---|---|
| **Offline** | **Outcome**: programmatic end-state checks (file exists, ticket created, DB row correct). **Trajectory**: tool-selection accuracy, argument validity, step efficiency vs reference, loop/recovery behavior. **Safety**: unsafe-action rate, unauthorized tool attempts, injection-resistance suite. Replay recorded tool responses for determinism; run N repeats. |
| **Online** | Task success (programmatic where possible, else judge over the trace), cost per *successful* task, steps per task, tool error rate, approvals denied, injection detections. |
| **Cheap flags** | Max-step/budget/timeout terminations, repeated identical tool calls, write-tool use, new tool or description change. |
| **Watch for** | Success-rate drops hidden by retries; cost per success rising while cost per call is flat. |

Live example: [Multi-agent use case](../use-cases/multi-agent.md).

## Chatbots and copilots

| | Scorers |
|---|---|
| **Offline** | Scripted multi-turn scenarios with simulated users (goal, persona, constraints); goal completion; policy compliance across turns; consistency/contradiction; escalation appropriateness; refusal correctness (incl. over-refusal set). |
| **Online** | **Conversation-level** judge on a stratified sample of whole conversations; containment/escalation/abandonment; thumbs; acceptance rate (copilots); re-ask rate. |
| **Cheap flags** | Refusal, fallback (unsupported intent), long context/truncation, stream stall, repeated user rephrasing. |
| **Watch for** | Intent-specific regressions; judge cost scaling with conversation length (judge a summary or a window). |

Live example: [Chatbot use case](../use-cases/chatbot.md).

## Extraction, classification, summarization pipelines

| | Scorers |
|---|---|
| **Offline** | Field-level precision/recall/F1 vs labels; schema validity; exact/fuzzy match per field; for summaries: required-point coverage, faithfulness, length. |
| **Online** | Schema parse rate and repair rate (100 %), distribution drift of predicted labels, confidence calibration, a continuous labeled **canary slice**. |
| **Cheap flags** | Parse failures, low confidence, out-of-distribution input length/language. |

## Text-to-SQL / NL-to-query

| | Scorers |
|---|---|
| **Offline** | **Execution accuracy** (result set equals golden), valid SQL rate, schema-grounding (no unknown columns), cost of the query (rows scanned). |
| **Online** | SQL validity, read-only enforcement, query cost, user confirmation/edit rate, judge on a sample for semantic correctness. |
| **Cheap flags** | Parser/binder errors, full-table scans, blocked statements, repair loops. |

## Voice agents

| | Scorers |
|---|---|
| **Offline** | WER on a labeled audio set, intent accuracy, simulated-call task success, barge-in handling scripts. |
| **Online** | Turn latency, sampled ASR WER vs human transcript, dead-air/talk-over rates, call outcome. |

## Code assistants

| | Scorers |
|---|---|
| **Offline** | **Unit tests pass** (the best scorer there is), static analysis, security scan, compilation. |
| **Online** | Suggestion acceptance and retention (kept after N minutes), test-pass on accepted code where measurable, security-scan hits. |

## Minimum viable scoring program (any app)

1. Deterministic checks on 100 % of traffic and in CI.
2. A 200-item golden set + a regression set, gated in CI with paired CIs.
3. One reference-free judge criterion (groundedness or task success), sampled online, calibrated on 100 labeled items.
4. User feedback captured with `trace_id`.
5. Scores, versions and sample sizes on the same dashboard as latency and cost.
