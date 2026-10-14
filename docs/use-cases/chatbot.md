# Use case: Chatbot

**Service `support-chatbot`**: a customer-support assistant with multi-turn sessions across web, mobile and WhatsApp, intent routing, a guardrail that can refuse, escalation to humans, and streaming answers.
Code: [`use-cases/chatbot/`](https://github.com/akashtalole/ai-observability/tree/main/use-cases/chatbot) · Theory: [Monitoring chatbots](../monitoring/chatbots.md).

Chatbots are judged per **conversation**, not per request. The metrics here are the ones a support leader asks about: containment, escalation, abandonment, and cost per conversation, next to the engineering ones.

```bash
python use-cases/chatbot/app/chatbot_app.py --rps 0.6 --cycle 240
python use-cases/chatbot/app/chatbot_app.py --scenario over-refusal
python use-cases/chatbot/app/chatbot_app.py --console --duration 15
```

## Telemetry design

* One **trace per turn** (`chat.turn` → `chat <model>`), correlated into a conversation by `gen_ai.conversation.id`. A **session** (the conversation) is a *metric* (`chat.sessions`) with a final outcome, so you never need to stitch traces to compute containment.
* No message text is recorded: only message length, intent label, channel, turn index, context utilization and scores.
* Streaming stalls and truncations are explicit events, because they show up in user abandonment before they show up in error rates.

## Metrics

| OTel name | Prometheus name | Key labels | Answers |
|---|---|---|---|
| `chat.sessions` | `chat_sessions_total` | `outcome` (resolved/escalated/abandoned), `intent`, `channel` | **Containment**, escalation, abandonment |
| `chat.session.turns` | `chat_session_turns_*` | `outcome` | Turns to resolution |
| `chat.turns` | `chat_turns_total` | `status`, `intent`, `channel` | Turn volume, error ratio |
| `chat.turn.duration` | `chat_turn_duration_seconds_*` | `intent` | Turn latency |
| `chat.ttft` | `chat_ttft_seconds_*` | `channel` | Perceived responsiveness |
| `chat.stream.stalls` | `chat_stream_stalls_total` |  | Mid-answer pauses |
| `chat.intents` | `chat_intents_total` | `intent`, `channel` | Intent mix, input drift |
| `chat.fallbacks` | `chat_fallbacks_total` |  | Unsupported intents |
| `chat.guardrail.events` | `chat_guardrail_events_total` | `category`, `action`, `intent` | Refusals, over-refusal |
| `chat.context.utilization` | `chat_context_utilization_*` |  | Context window pressure (0..1) |
| `chat.context.truncations` | `chat_context_truncations_total` |  | History loss |
| `chat.tokens`, `chat.cost.usd` | `chat_tokens_total`, `chat_cost_usd_total` | `direction`, `intent` | Cost per conversation |
| `chat.eval.score` | `chat_eval_score_*` | `metric` (goal_completion, policy_compliance) | Conversation-level quality |
| `chat.feedback` | `chat_feedback_total` | `rating`, `intent` | User signal |
| `chat.active_sessions` | `chat_active_sessions` |  | Concurrency |

## Dashboards

Folder **chatbot**:

| Dashboard | Use |
|---|---|
| **Chatbot: Conversations, Quality & Cost** | Containment/escalation/abandonment, Δ vs previous period, containment **by intent** (aggregates hide regressions), TTFT by channel, refusals, context utilization, cost per conversation. Variable: `intent` |
| **Chatbot: Trends** | Daily containment, week-over-week |

## Alerts

[`use-cases/chatbot/alerts/chatbot-alerts.yml`](https://github.com/akashtalole/ai-observability/blob/main/use-cases/chatbot/alerts/chatbot-alerts.yml)

| Alert | Signal |
|---|---|
| `ChatTTFTHigh` | TTFT p95 > 1.5 s |
| `ChatTurnErrors` | > 5 % of turns failing |
| `ChatContainmentDrop` | Containment < 60 % (healthy demo traffic ≈ 80 %) |
| `ChatEscalationSpike` | Escalation > 25 % (healthy ≈ 12 %) |
| `ChatOverRefusal` | Guardrail refusing > 8 % of turns |
| `ChatContextNearLimit` | Context utilization p95 > 30 % (demo window is small; use ~80 % in production) |
| `ChatGoalCompletionLow` | Judge goal-completion < 0.75 **and** ≥ 8 scored conversations |
| `ChatCostPerSessionSpike` | Cost/conversation > 1.5× its 30-minute median |

## Failure scenarios

--8<-- "use-cases/_generated/scenarios-chatbot.md"

## Query cookbook

```promql
# containment by intent
sum by (intent) (rate(chat_sessions_total{outcome="resolved"}[1h])) / sum by (intent) (rate(chat_sessions_total[1h]))

# cost per resolved conversation (not per conversation)
sum(increase(chat_cost_usd_total[1d])) / sum(increase(chat_sessions_total{outcome="resolved"}[1d]))

# over-refusal rate
sum(rate(chat_guardrail_events_total{action="refused"}[5m])) / sum(rate(chat_turns_total[5m]))

# fastest-growing intents (input drift)
topk(3, sum by (intent) (rate(chat_intents_total[1d])) / sum by (intent) (rate(chat_intents_total[1d] offset 7d)))
```

```traceql
{ resource.service.name = "support-chatbot" && span.guardrail.refused = true }
{ resource.service.name = "support-chatbot" && span.stream.stalled = true }
{ resource.service.name = "support-chatbot" && name = "chat.turn" && span.context.truncated = true }
```

## Taking it to production

* Emit `chat.sessions` from your session manager on close/timeout, with the final outcome.
* Define **resolution** carefully (explicit confirmation, no re-contact within N days, judge score): it is the KPI everything else supports.
* Add a conversation-level judge on a stratified sample; calibrate against human review.
* For regulated data, tokenize user IDs, redact content before any storage, and keep content out of telemetry (see [Security & privacy](../architecture/security-privacy.md)).
* See [Adapting to your app](adapting.md).
