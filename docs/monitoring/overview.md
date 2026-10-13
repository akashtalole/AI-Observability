# Monitoring by application type

Every AI app shares the latency/quality/cost core, but each pattern has its own failure modes and signature metrics.

| App type | Unique risks | Signature metrics | Page |
|---|---|---|---|
| **RAG / knowledge assistant** | Bad retrieval, stale index, ungrounded answers, ACL leaks | Groundedness, context precision/recall, top-1 score, index freshness | [RAG](rag.md) |
| **Agents / multi-agent** | Loops, wrong tools, runaway cost, unsafe actions | Task success, steps, tool accuracy, cost/task | [Agents](agents.md) |
| **Chatbots / copilots** | Multi-turn drift, tone, deflection failure, abandonment | TTFT, resolution rate, escalation, CSAT, conversation quality | [Chatbots](chatbots.md) |
| **Tools / MCP / text-to-SQL** | Wrong/unsafe calls, bad SQL, schema drift, injection | Tool success, SQL validity/exec accuracy, read/write ratio | [Tools & SQL](tools-mcp-sql.md) |
| **Voice, multimodal, batch** | ASR errors, interruptions, large payloads, throughput | WER, turn latency, barge-in, per-doc accuracy, job SLA | [Voice/batch](voice-multimodal-batch.md) |
| **Self-hosted / fine-tuned models** | GPU saturation, KV-cache pressure, regression after fine-tune | TTFT, TPOT, queue depth, GPU util, eval delta | [Self-hosted](self-hosted-models.md) |
| **Classification / extraction / summarization pipelines** | Silent accuracy drift, schema failures | Accuracy vs labels, parse rate, per-field F1 | [Voice/batch](voice-multimodal-batch.md) |
| **Code assistants** | Insecure/incorrect code, acceptance drop | Acceptance rate, test-pass rate, security-scan hits | [Agents](agents.md) |

## Universal baseline (every AI app)

1. Trace per request with stage spans and `gen_ai.*` attributes.
2. Token, cost, latency (incl. TTFT) per request, sliced by tenant/feature/model/version.
3. Error taxonomy (timeout, rate-limit, content-filter, parse, tool, retrieval).
4. At least one automated quality score on a sample + user feedback capture.
5. Guardrail/PII verdict logging.
6. Change events (model, prompt, index, config) on every chart.
7. SLOs with burn-rate alerts; weekly review of trends.

## Risk-tiering the depth of monitoring

| Tier | Example | Depth |
|---|---|---|
| T1 – Low risk, internal | Meeting summarizer | Baseline |
| T2 – Business-impacting | Employee HR/IT assistant, customer support bot | Baseline + online evals + feedback + cost budgets |
| T3 – High risk / regulated | Medical, legal, financial advice, autonomous actions | T2 + human review queues, 100 % guardrail logging, audit retention, red-team canaries, change approval |
