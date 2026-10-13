# Security, privacy & governance

AI telemetry contains the most sensitive data your company produces at scale: employee and customer questions, internal documents (via retrieval), and model outputs. Treat the observability platform as a **regulated data system**.

## Threats and controls

| Risk | Control |
|---|---|
| PII/PHI/PCI/secrets in prompts and responses | Redact **at the edge** (SDK or Collector `transform`/`redaction` processors, or Presidio-style detectors) before export; deny-list for known secret formats |
| Over-collection of content | Default to metadata only; content capture is opt-in per app, per tenant, per environment, time-boxed |
| Unauthorized access to traces | RBAC/ABAC mapped to tenant and data classification; audit access logs; break-glass workflow |
| Cross-tenant leakage in shared dashboards | Tenant-scoped views / row-level security; separate projects per business unit if needed |
| Vendor data residency & training use | Region pinning, DPA, "no training on customer data", BYOK; prefer self-hosting or Collector-redacted SaaS for regulated data |
| Retention beyond policy / right-to-erasure | TTLs per tier; deletion by `subject_id` pseudonym; content-by-reference makes erasure tractable |
| Prompt injection via retrieved docs, observed in traces | Track injection detections; treat trace content as untrusted when rendering (escape HTML/markdown, never auto-execute) |
| Telemetry as exfiltration path | Egress allow-lists for exporters; private endpoints |

## Data classification for AI telemetry

| Class | Examples | Default handling |
|---|---|---|
| **Operational metadata** | Latency, token counts, model, status, versions | Broad access, long retention |
| **Business context** | Tenant, feature, intent label, cost | Role-based access, long retention |
| **Derived scores** | Eval scores, guardrail verdicts | Broad access, long retention |
| **Content (redacted)** | Truncated/redacted prompt & answer | Restricted, short retention |
| **Content (raw)** | Full prompts, retrieved chunks | Highly restricted, minimal retention, encrypted, audited |

## Governance and compliance mapping

* **Model & app inventory:** every AI app registered with owner, risk tier, model(s), data sources — feeds dashboards and audits.
* **Regulatory alignment:** EU AI Act (logging/traceability for high-risk systems, post-market monitoring), NIST AI RMF (Measure/Manage functions), ISO/IEC 42001 (AI management system), SOC 2 / HIPAA / GDPR for data handling. Observability evidence (eval results, incident records, change history) is the raw material for these.
* **Audit trail:** immutable record of *who changed which prompt/model/index/guardrail and when*, linked to subsequent metric shifts.
* **Human oversight:** review queues for flagged traces with documented outcomes.

## Safety observability (what to detect and log)

* Guardrail verdicts per category (toxicity, PII, jailbreak, prompt injection, off-topic, policy) with action taken (block/redact/warn).
* Refusal rate and over-refusal (false positive) rate — both are quality signals.
* Groundedness failures on regulated content (medical, legal, financial).
* Red-team canary prompts run continuously against production config.
* Tool-use authorization decisions for agents (what was allowed/denied and why).

## Minimum viable control set

1. Metadata-only by default; content capture behind a flag.
2. Redaction in the Collector, tested with seeded PII fixtures in CI.
3. Tenant-aware RBAC and audit logging on the observability UI.
4. Retention TTLs enforced by storage policy, not by convention.
5. Documented data-flow diagram reviewed by security/privacy.
