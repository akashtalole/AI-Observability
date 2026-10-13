# Observability maturity model

| Level | Name | Characteristics | Typical gaps |
|---|---|---|---|
| **0** | Blind | Provider dashboard only; ad-hoc logs | No per-feature cost, no quality signal |
| **1** | Logged | Prompts/responses logged; basic latency/errors in APM | Content risk, no evaluation, no versions |
| **2** | Traced | OTel traces with stage spans; tokens and cost per request; dashboards | Quality still anecdotal |
| **3** | Evaluated | Online sampled evals, golden-set CI gate, feedback capture, SLOs & burn alerts | Trends not attributed to changes; manual triage |
| **4** | Governed | Versioned everything, change events on charts, tenant cost attribution, redaction & RBAC, risk-tiered depth, review queues | Limited automation |
| **5** | Adaptive | Auto-canary/rollback on SLO/eval, routing by quality-cost policy, data flywheel into golden sets/fine-tunes, FinOps forecasting | Continuous optimization |

## Roadmap sketch

| Phase | Weeks | Deliverables |
|---|---|---|
| 1. Foundation | 0–4 | OTel wrapper, Collector, token/cost/latency metrics, version stamping, basic dashboards |
| 2. Quality | 4–10 | Golden set v1, online evaluators on sample, feedback capture, quality dashboard, CI gate |
| 3. Trends | 8–14 | Wide fact table + rollups, change events, monthly report, cost attribution by tenant |
| 4. Governance | 10–18 | Redaction tests, RBAC/audit, retention policies, risk tiers, runbooks |
| 5. Optimization | 16+ | Canary/rollback automation, routing policies, flywheel |

## Self-assessment (score 0–2 each)

- [ ] Every request has a trace with retrieval/LLM/tool spans
- [ ] Token and cost per request are recorded and attributed to tenant/feature
- [ ] TTFT and per-stage latency are tracked with percentiles
- [ ] Prompt, model, index and embedding versions are on every request
- [ ] Automated quality score exists for ≥ 2 % of traffic + all flagged
- [ ] Golden set gates releases
- [ ] SLOs defined; burn-rate alerts live
- [ ] Change events appear on dashboards
- [ ] 12+ months of aggregate trend data are queryable
- [ ] Content capture is gated, redacted, and retention-limited
- [ ] Runbooks exist and were exercised
- [ ] Monthly trend review happens

Score 0–8: Level 1–2 · 9–16: Level 3 · 17–24: Level 4+.
