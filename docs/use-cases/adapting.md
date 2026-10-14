# Adapting the use cases to your app

The demo apps simulate model and vector DB calls so they run anywhere; the **telemetry contract** (span names, attributes, metric names, labels) is what you carry over.

## Checklist

1. **Keep the names.** Dashboards and alerts key on `service_name` and the metric names on each use-case page. Rename the service via `setup("your-service")`, then search/replace `service_name="support-rag"` in the rules and `gen_dashboards.py`.
2. **Instrument your real calls.** Replace the `time.sleep` stand-ins with client calls. Frameworks that already emit OTel (or OpenLLMetry / OpenLIT / OpenInference auto-instrumentation) can supply the `chat` / `embeddings` spans; keep the manual stage spans and `app.*` / `rag.*` attributes.
3. **Own the price table.** Cost = tokens × versioned price; record `app.price_table.version`.
4. **Wire change events.** Replace the "scenario change" log annotation with deploy / prompt / model / index events from CI/CD (a log line to Loki or a Prometheus annotation series).
5. **Decide your quality signals** (judge, rubric, sample rate) and write them as `*.eval.score{metric=…}` histograms.
6. **Tune thresholds from your own baselines.** The demo thresholds fit synthetic traffic; derive yours from 2-4 weeks of data, or use baseline-relative rules like `> 2× 30-minute median`.
7. **Lengthen windows.** Demo rules use 2-3 minute windows so scenarios fire quickly; use 5-15 minute windows and multi-window burn rates in production ([SLOs & alerting](../metrics/slos-alerting.md)).
8. **Move off the laptop stack.** See the hardening and long-range retention list on [the stack page](stack.md#scaling-and-hardening-checklist).

## Mapping to other frameworks

| You use… | Do this |
|---|---|
| LangChain / LangGraph, LlamaIndex, Semantic Kernel, AutoGen, CrewAI | Enable the framework's OTel/OpenInference/OpenLLMetry instrumentation; add a callback that records the metrics above |
| Provider SDK only (OpenAI, Anthropic, Bedrock, Vertex, Azure) | Use OpenLLMetry/OpenLIT/OpenInference instrumentors for `chat` spans; add your own stage spans |
| A gateway (LiteLLM, Kong, APIM, Envoy AI Gateway) | Take tokens/cost/latency/errors from its OTel metrics and join to app traces by `traceparent` |
| Java / Node / Go / .NET | Same OTel conventions; copy the metric and attribute names, not the Python |
| Existing Datadog / Dynatrace / New Relic | Keep the Collector; add that vendor's exporter next to (or instead of) Prometheus/Tempo/Loki |

## Swapping backends later

Because the apps speak only OTLP to the Collector, you can add or replace backends without touching application code: point `otlp/tempo` at another OTLP endpoint, change `prometheusremotewrite` to Mimir/Thanos/VictoriaMetrics/Grafana Cloud, add a ClickHouse or vendor exporter. That is the portability argument from the [build-vs-buy framework](../build-vs-buy/decision-framework.md) in practice.

## Extending

* New use case (voice, text-to-SQL, batch pipeline): copy a folder under `use-cases/`, add a dashboard function in `scripts/gen_dashboards.py`, add a rules file, and mount them in `stack/docker-compose.yml`.
* Verify before committing: `python scripts/verify_dashboards.py` runs every panel query through Grafana's API against a live stack and fails on errors.
