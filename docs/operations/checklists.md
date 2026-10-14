# Checklists

## Launch readiness (per AI application)

**Telemetry**

- [ ] Traces with stage spans; `traceparent` propagated through gateway/tools
- [ ] `gen_ai.*`, `app.*`, `rag.*` attributes per the contract
- [ ] Versions stamped: release, prompt, model, embedding, index
- [ ] Token + cost computed from owned price table
- [ ] TTFT and per-stage latency histograms

**Quality**

- [ ] Golden set (≥ 200 items incl. unanswerable/adversarial) and baseline recorded
- [ ] Online evaluators + sampling plan + judge calibration
- [ ] Feedback capture linked to `trace_id`

**Operations**

- [ ] SLOs and burn-rate alerts, cost budget alerts
- [ ] Dashboards: health, latency, quality, cost, change impact
- [ ] Runbooks linked from alerts; on-call owner defined
- [ ] Change events emitted from CI/CD and config systems

**Security & compliance**

- [ ] Data-flow diagram reviewed; content capture off by default
- [ ] Redaction tested; RBAC & audit enabled
- [ ] Retention TTLs configured; erasure path defined
- [ ] Risk tier assigned; model/app inventory entry created

## Tool selection (RFP / bake-off)

- [ ] OTLP ingest and export; GenAI semconv support
- [ ] Self-host / BYOC / region options
- [ ] Trace UX for RAG + agents (long, nested runs)
- [ ] Online evals, custom judges, datasets/experiments, CI integration
- [ ] Cost attribution with custom prices; budgets
- [ ] SQL/API access to raw data; retention ≥ 13 months or export
- [ ] SSO/SCIM, RBAC, audit logs, PII controls
- [ ] Pricing model modelled at 3× volume; exit plan
- [ ] Vendor stability: ownership, license, roadmap

## Monthly review

- [ ] SLO attainment and error-budget consumption
- [ ] Month-over-month: cost/request, p95 latency, quality by intent
- [ ] Top 10 regressions and their causes; change log correlation
- [ ] Cost by tenant/feature; forecast vs budget
- [ ] Golden set refresh from production failures
- [ ] Evaluator calibration check
- [ ] Alert noise review (pages per week, false positives)
- [ ] Retention/storage cost review
