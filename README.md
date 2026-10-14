# Enterprise AI Observability Handbook

Guidance, reference architecture, design patterns, build-vs-buy analysis and a full tooling landscape for observing **enterprise AI applications** — RAG, agents, chatbots, copilots, voice and batch pipelines.

**North star:** full visibility into **latency, quality and cost** of the RAG app across *any time range*, so issues are caught early and trends can be tracked over months.

## Read it

* **Site (MkDocs + GitHub Pages):** `https://akashtalole.github.io/ai-observability/` (after the first deploy from `main`)
* **Locally:**
  ```bash
  pip install -r requirements.txt
  python scripts/build.py      # regenerate catalog + HTML artifacts
  mkdocs serve                 # http://127.0.0.1:8000
  ```

## Repository layout

```
docs/
  fundamentals/     why AI observability, vs APM, telemetry model + OpenTelemetry GenAI
  architecture/     reference architecture, design patterns, storage & retention, security
  build-vs-buy/     decision framework, cloud-agnostic, cloud-specific, open source, TCO
  landscape/        overview, 67-tool catalog (generated), comparison by need
  metrics/          metrics catalog, data to collect, SLOs & alerting, evaluation
  scoring/          online and offline scoring: datasets, scorers, judges, sampling, gates
  monitoring/       RAG, agents, chatbots, tools/MCP/text-to-SQL, voice/multimodal/batch, self-hosted
  rag/              latency + quality + cost playbook, dashboards & queries
  implementation/   instrumentation, collector pipeline, evals in CI
  operations/       maturity model, runbooks, checklists
  artifacts/        interactive HTML artifacts (see below)
use-cases/         runnable OSS implementations (OTel + Prometheus + Grafana + Loki + Tempo): RAG, multi-agent, chatbot
examples/           OTel instrumentation, Collector config, ClickHouse schema + queries, Prometheus alerts
data/tools.json     single source of truth for the tool catalog and explorer
scripts/build.py    generates catalog.md, landscape-explorer.html, handbook.html
scripts/gen_dashboards.py     generates the Grafana dashboards in use-cases/
scripts/verify_dashboards.py  runs every dashboard query against a live Grafana
```

## Use cases (open-source implementations)

`use-cases/` contains a docker-compose stack (OpenTelemetry Collector, Prometheus, Tempo, Loki, Grafana) and three instrumented demo apps with dashboards, alert rules and failure-scenario simulators: **RAG**, **multi-agent** and **chatbot**. See [use-cases/README.md](use-cases/README.md) and the docs site section *Use cases (OSS stack)*.

## HTML artifacts (`docs/artifacts/`, also deployed with the site)

| File | Purpose |
|---|---|
| `build-vs-buy-decision-tool.html` | Weighted scoring of SaaS / OSS / cloud-native / APM / hybrid |
| `landscape-explorer.html` | Search and filter all tools (generated) |
| `rag-dashboard-demo.html` | Latency / quality / cost dashboard, 1 h → 12 months (synthetic data) |
| `metrics-checklist.html` | Per-app-type collection checklist |
| `handbook.html` | Whole handbook as one printable file (generated) |

## Deploy

`.github/workflows/docs.yml` builds with `mkdocs build --strict` and deploys to GitHub Pages on push to `main`.
One-time setup: **Settings → Pages → Source: GitHub Actions**.

## Maintaining

* Add or edit tools in `data/tools.json`, then run `python scripts/build.py`.
* Vendor facts are dated ("snapshot October 2026"); re-verify licenses and ownership on a regular cadence.
* OpenTelemetry GenAI semantic conventions are still in *Development* — pin versions in your instrumentation.

## License

See [LICENSE](LICENSE).
