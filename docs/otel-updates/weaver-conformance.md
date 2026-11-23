# Weaver & conformance

[OpenTelemetry Weaver](https://github.com/open-telemetry/weaver) (tested here with **v0.28.0**) is the tool that makes semantic conventions
*executable*: you describe telemetry in a registry, and Weaver checks, documents, diffs and validates real telemetry against it.

## What Weaver does

| Command | Use |
|---|---|
| `weaver registry check -r <registry>` | Lint a registry and its policies; the CI gate for **your** conventions |
| `weaver registry generate` | Render docs, code, constants or dashboards from the registry with templates |
| `weaver registry diff` | Report breaking changes between two registry versions (schema evolution) |
| `weaver registry stats` | Counts by signal and stability |
| `weaver registry live-check` | Receive **real telemetry** (OTLP, file or stdin) and score it against the registry |
| `weaver registry infer` | Build a draft registry from observed telemetry (a starting point, not a result) |
| `weaver registry emit` | Emit sample telemetry from a registry, to test pipelines |
| `weaver registry package`, `weaver registry mcp` | Package a registry; expose it to AI tools over MCP |

Registries use the `definition/2` format (pass `--v2`); a registry can depend on others, so yours imports the official ones and declares only your own additions.

## Live-check in detail

Live-check ingests telemetry, resolves each sample to a signal in the registry and produces **findings** at three levels:
`violation` (wrong or undeclared), `improvement` (should change, e.g. not stable, recommended attribute missing) and `information`.

Things you must configure, learned the hard way:

1. **Spans need matchers.** A span name is free-form, so nothing says which span definition it follows. Without a `[[live-check.matchers]]` entry
   every attribute is reported as "does not exist in the registry". Match on a signature, such as `gen_ai.operation.name`.
2. **Include dependency signals** with `--include-unreferenced`, or matchers cannot name `gen_ai.client.inference`.
3. **Use `--config <weaver.toml>`** (the flag is `--config`, not `-c`) to load matchers and `finding_filters`.
4. **Custom rules in Rego** (`live_check_advice` package) add checks the registry cannot express: span-name formats, per-operation required attributes.
   The conformance project ships a ready set for GenAI; reuse it rather than writing your own.
5. **Stop the receiver** with an inactivity timeout or `POST localhost:4320/stop`, then read `live_check.json`.

## The conformance project

[`semantic-conventions-conformance`](https://github.com/open-telemetry/semantic-conventions-conformance) runs *scenario programs* in many languages
and libraries (GenAI, HTTP, database, browser) against a Weaver live-check and publishes the results. For GenAI it ships a mock LLM server, Rego policies
(span-name format, required attributes per operation, content checks) and a `conformance.yaml` per tool. The `semantic-conventions-genai` repository itself carries
Python reference implementations and a compliance matrix.

Use it to **choose and pin instrumentation libraries**: look up the library and version, check which operations and attributes it actually emits, and only then
standardise on it. Add a scenario if your internal wrapper is not covered.

## Results for the demo apps

`conformance/` in this repo contains a registry that imports `semantic-conventions-genai` v0.1.0 and adds the demo's own attributes, a
`weaver.toml` with matchers, and `run.sh`, which starts live-check, runs the three apps for 20 seconds and prints a summary.

```bash
# needs the Weaver binary (v0.28.x) on PATH or passed as the first argument
conformance/run.sh /path/to/weaver
```

| Finding class | Before | After fixing |
|---|---|---|
| Span `gen_ai.provider.name` required but missing (embeddings) | present | **fixed** (attribute added) |
| `execute_tool` spans with kind `client` (convention: `internal`) | present | **fixed** (`SpanKind.INTERNAL`) |
| Unknown span attributes (`app.*`, `rag.*`, `tool.*`) | many | **declared** in `conformance/registry` (`app.common`) |
| Embedding step span kind `internal` (convention: `client`) | present | open (small change in `timed_stage`) |
| Root spans with kind `server` carrying `gen_ai.operation.name=invoke_agent` | present | **kept on purpose**; the Omni-style dashboards key on server-side root spans |
| Resource `deployment.environment` | present | open; rename to `deployment.environment.name` together with the dashboards' `deployment_environment` label |
| `gen_ai.main_agent` entity required attribute `gen_ai.main_agent.id` missing | present | open; set when you adopt the entity |
| **Metric attributes without a namespace** (`model`, `agent`, `tenant`, `status`, …) | thousands | **open by design**: renaming changes every Prometheus label, dashboard and alert |
| App-specific metrics (`rag.*`, `agent.*`, `chat.*`) not in any registry | present | open; declare them in your own registry if you want them checked |

!!! note "How to read the numbers"
    Finding counts scale with how many samples a run produces, so compare *classes* of finding across runs, not totals. The unmatched metric
    findings are the most valuable result: they show exactly what a move to namespaced attributes (`app.model`, `app.tenant.id`, …) and to the
    standard `gen_ai.*` metrics would change. The [adoption playbook](adoption-playbook.md) sequences that migration.

## Put it in CI

```yaml
- name: Weaver conformance
  run: |
    curl -sSL https://github.com/open-telemetry/weaver/releases/download/v0.28.0/weaver-x86_64-unknown-linux-gnu.tar.xz | tar -xJ
    pip install -r use-cases/requirements.txt
    conformance/run.sh ./weaver-x86_64-unknown-linux-gnu/weaver
```

Start by *reporting* findings; once the baseline is clean, fail the build on new `violation` findings (use `finding_filters` for accepted exceptions,
and keep each exception documented).
