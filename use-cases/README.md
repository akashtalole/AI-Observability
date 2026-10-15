# Use cases: implementations on the open-source stack

Runnable reference implementations (OpenTelemetry · Prometheus · Grafana · Loki · Tempo). Full documentation:
**[docs/use-cases](../docs/use-cases/index.md)** (also on the MkDocs site).

```
use-cases/
  requirements.txt        opentelemetry-sdk + OTLP exporter
  common/telemetry.py     shared OTel bootstrap (traces + metrics + logs)
  stack/                  docker-compose, Collector, Prometheus, Tempo, Loki, Grafana provisioning
  rag/                    app/ dashboards/ alerts/        service: support-rag
  multi-agent/            app/ dashboards/ alerts/        service: research-agents
  chatbot/                app/ dashboards/ alerts/        service: support-chatbot
  omni-style/             dashboards/                     CloudWatch-Omni-style views on the same data
```

## Quick start

```bash
pip install -r use-cases/requirements.txt
docker compose -f use-cases/stack/docker-compose.yml up -d        # Grafana http://localhost:3000

python use-cases/rag/app/rag_app.py           --rps 3   --cycle 240 &
python use-cases/multi-agent/app/agent_app.py --rps 0.7 --cycle 240 &
python use-cases/chatbot/app/chatbot_app.py   --rps 0.6 --cycle 240 &
```

`--cycle N` alternates a healthy phase and a failure scenario every N seconds; `--scenario NAME` pins one; `--console` prints
telemetry without a stack. Dashboards live in Grafana folders `rag`, `multi-agent`, `chatbot`, `platform`.

## Maintenance

| Task | Command |
|---|---|
| Regenerate dashboards after editing `scripts/gen_dashboards.py` / `gen_omni_dashboards.py` | `python scripts/gen_dashboards.py && python scripts/gen_omni_dashboards.py` |
| Validate alert rules | `promtool check rules use-cases/*/alerts/*.yml use-cases/stack/prometheus/rules/*.yml` |
| Validate Collector config | `otelcol-contrib validate --config use-cases/stack/otel-collector.yaml` |
| Run every dashboard query against a live stack | `python scripts/verify_dashboards.py --grafana http://localhost:3000` |
