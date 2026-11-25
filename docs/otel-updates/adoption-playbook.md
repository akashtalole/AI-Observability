# Adoption playbook

Sequenced so each step is safe on its own. Do not change names and dashboards in the same release.

| Step | Do | Verify |
|---|---|---|
| 1. **Pin and inventory** | Record semconv core (v1.45.0), GenAI conventions (v0.1.0), Collector, SDK and Weaver versions. | One page in the repo listing each pin. |
| 2. **Measure** | Run `conformance/run.sh`, or point Weaver live-check at a staging Collector's OTLP fan-out. | A baseline `live_check.json` stored per release. |
| 3. **Fix spans** | Correct span kinds and required attributes (these do not change dashboards). | Span-class `violation` findings reach zero. |
| 4. **Content capture** | Set the capture variable your instrumentation actually reads; default `NO_CONTENT`; keep the Collector redaction processor. | Send a canary prompt; confirm it is absent or present as intended. |
| 5. **Dual-emit metrics** | Emit the standard `gen_ai.client.*` and `gen_ai.execute_tool.duration` metrics **alongside** your own for one release cycle. | Both series agree on rates and percentiles. |
| 6. **Migrate dashboards and alerts** | Switch queries to the standard metrics (or recording rules that alias them); update SLO rules. | `scripts/verify_dashboards.py` passes against the stack. |
| 7. **Namespace custom attributes** | Move un-namespaced metric attributes (`model`, `agent`, `tenant`) to `app.*` or the GenAI names, one metric family at a time. | Label cardinality unchanged; no panel goes empty. |
| 8. **Resource rename** | `deployment.environment` → `deployment.environment.name`; update Prometheus/Loki label usage. | Dashboards' environment variable still lists values. |
| 9. **Gate in CI** | Weaver `registry check` for your registry; live-check against a scenario run for new `violation` findings. | CI fails on a deliberately wrong attribute. |
| 10. **Re-check quarterly** | Re-read GenAI release notes; run `weaver registry diff` between pinned and latest. | Dated entry in the pins page. |

## Checklist

- [ ] Versions pinned and documented (semconv, GenAI conventions, Collector, SDK, Weaver)
- [ ] `OTEL_INSTRUMENTATION_GENAI_CAPTURE_CONTENT` and its older spelling checked against the instrumentation version in use
- [ ] Span kinds and required attributes conform for every operation you emit
- [ ] Standard GenAI metrics emitted (dual-emit window planned)
- [ ] Custom attributes namespaced and declared in your own registry
- [ ] `deployment.environment.name` rolled out with dashboard changes
- [ ] Weaver in CI (start report-only)
- [ ] Library choices backed by conformance results
