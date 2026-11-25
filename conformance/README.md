# Conformance: Weaver live-check for the demo apps

Checks the three demo apps' real telemetry against the OpenTelemetry GenAI conventions (`semantic-conventions-genai` v0.1.0).

```
registry/manifest.yaml        imports the GenAI conventions; declares only the demo's own attributes
registry/app_attributes.yaml  app.*, rag.*, eval.*, cost.*, tool.*, guardrail.* and the app.common group
weaver.toml                   matchers (span -> GenAI signal), finding filters
run.sh                        starts weaver live-check, runs the apps for 20 s, prints a summary
summarize.py                  groups findings from live_check.json by level and message
```

```bash
# Weaver v0.28.x (https://github.com/open-telemetry/weaver/releases); needs git access to github.com for the dependency
pip install -r use-cases/requirements.txt
conformance/run.sh /path/to/weaver          # output in conformance/out (override with OUT=...)
python conformance/summarize.py conformance/out/live_check.json "kind_mismatch"   # optional filter
```

Notes and results: [docs/otel-updates/weaver-conformance.md](../docs/otel-updates/weaver-conformance.md). The attribute briefs in
`app_attributes.yaml` were inferred with `weaver registry infer` and are placeholders; write real ones before using this as your own registry.
