# Monitoring self-hosted & fine-tuned models

When you run inference yourself (vLLM, TGI, TensorRT-LLM, SGLang, Triton, KServe, Ollama at the edge), you own the serving-layer telemetry.

## Serving metrics

| Metric | Why it matters |
|---|---|
| **TTFT**, time per output token (TPOT), inter-token latency | User-perceived performance |
| Requests running / waiting (queue depth), queue time | Saturation; autoscaling signal |
| Throughput: tokens/s (prompt vs generation), requests/s | Capacity |
| **GPU utilization, memory, memory bandwidth**, power, temperature, ECC/XID errors (DCGM) | Hardware health |
| **KV-cache usage %**, preemptions/evictions, prefix-cache hit rate | Main cause of latency cliffs |
| Batch size distribution, speculative-decoding acceptance rate | Tuning |
| Model load time, cold starts, replica restarts | Reliability |
| Token length distributions (input/output), truncation/`length` finish rate | Right-sizing |
| Cost per 1M tokens (GPU-hour ÷ tokens/hour), GPU idle % | FinOps |

Most inference servers expose Prometheus metrics; scrape them and join with request traces by `deployment`/`model_version`.

## Model-quality governance

* Registry entry for each model/adapter with training data lineage, eval results, intended use.
* Evaluate **before and after** each fine-tune/quantization/runtime upgrade on the golden set; track regression in safety evals too.
* Canary new revisions; compare score distributions, not only means.
* Monitor **adapter/version mix** across replicas to detect partial rollouts.

## Capacity planning

Plot demand (tokens/s) vs capacity at SLO (max tokens/s while TTFT p95 within target). Alert on headroom < 20 %; autoscale on queue depth or KV-cache pressure rather than CPU/GPU utilization alone.
