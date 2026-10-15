# Omni-style Grafana dashboards

Grafana dashboards that mirror the surfaces of **Amazon CloudWatch Omni's** agent observability (Space health, fleet overview, Trace Explorer with compare mode, Session Explorer, Agent Topology, Evaluators), running on the open-source stack in [`../stack`](../stack) and the demo apps in [`../rag`](../rag), [`../multi-agent`](../multi-agent) and [`../chatbot`](../chatbot).

Documentation, panel-by-panel mapping and limitations: **[docs/use-cases/omni-style-dashboards.md](../../docs/use-cases/omni-style-dashboards.md)**.

```bash
python scripts/gen_omni_dashboards.py        # regenerate dashboards/*.json
docker compose -f use-cases/stack/docker-compose.yml up -d     # Grafana folder "omni-style"
python scripts/verify_dashboards.py          # runs every panel query against a live stack
```
