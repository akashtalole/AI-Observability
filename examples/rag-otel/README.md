# RAG instrumentation example

```bash
pip install opentelemetry-sdk
python examples/rag-otel/instrument.py            # prints spans + metrics to the console
```

For production, replace the console exporters with OTLP exporters pointed at the Collector in
[`../otel-collector.yaml`](../otel-collector.yaml). Metric names match
[`../alerts/ai-slo-alerts.yml`](../alerts/ai-slo-alerts.yml); the fact-table schema is in
[`../sql/clickhouse_schema.sql`](../sql/clickhouse_schema.sql).
