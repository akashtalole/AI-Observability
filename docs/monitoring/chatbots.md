# Monitoring chatbots & copilots

!!! tip "Run it"
    A runnable chatbot implementation (containment, escalation, refusals, context utilization) is in [Use case: Chatbot](../use-cases/chatbot.md).

## Session-level view

Chatbots are multi-turn. Correlate turns via `conversation_id` and evaluate **conversations**, not only single turns.

| Area | Metrics |
|---|---|
| **Responsiveness** | TTFT p50/p95, total latency, streaming stall rate, time-between-chunks |
| **Resolution** | Containment/deflection rate, resolution rate (LLM-judged + survey), escalation-to-human rate, handoff context quality |
| **Conversation quality** | Turns to resolution, re-ask/rephrase rate, topic-switch rate, conversation-level coherence, tone/brand-voice adherence |
| **Satisfaction** | Thumbs, CSAT, NPS, regeneration rate, abandonment (user leaves mid-answer) |
| **Content** | Hallucination/groundedness (if RAG), refusal vs over-refusal, unsupported-intent rate (fallback) |
| **Safety** | Toxicity, jailbreak attempts, PII from users, policy escalation |
| **Memory / context** | Context-window utilization, truncation events, summarization drift |
| **Cost** | Cost per conversation, per resolved conversation, tokens by turn index (history growth) |
| **Adoption** | Active users, returning users, queries per session, feature/skill usage, channel mix |

## Copilots embedded in apps

* **Acceptance rate** of suggestions (accept/edit/reject), time-saved proxy, retention after use.
* Context-grounding quality (selected document/record passed correctly?).
* Latency budget is tighter (inline UX): track "suggestion shown within X ms" rate.
* Per-surface (Word, IDE, CRM) segmentation of all metrics.

## Intent and topic analytics

Cluster user queries (embeddings + topic labels) and track by cluster: volume, success, cost, latency. Emerging clusters with low success are the best backlog input; they also detect **input drift**.

## Conversation-level evals

| Eval | Method |
|---|---|
| Goal completion | Judge over the full transcript with rubric |
| Policy compliance across turns | Judge + deterministic checks |
| Consistency / contradiction | Claim extraction across turns |
| Escalation appropriateness | Compare escalation decision with labels |

## Privacy notes
Chat content is high-risk. Use tokenized user IDs, redact before storage, short content retention, and consent-aware analytics. See [Security & privacy](../architecture/security-privacy.md).
