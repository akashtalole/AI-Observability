#!/usr/bin/env python3
"""Generate the Grafana dashboards for the use cases (JSON is committed; edit this file, then re-run).

    python scripts/gen_dashboards.py

Writes:
  use-cases/rag/dashboards/{rag-overview,rag-trends}.json
  use-cases/multi-agent/dashboards/{agents-overview,agents-trends}.json
  use-cases/chatbot/dashboards/{chatbot-overview,chatbot-trends}.json
  use-cases/stack/grafana/dashboards/pipeline-health.json

Dashboards are time-range aware: KPI tiles use $__range (so "last 5m" and "last 12 months" both work, subject to
Prometheus retention) and compare with the previous period via `offset $__range`; time series use $__rate_interval.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "use-cases"
PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}
TEMPO = {"type": "tempo", "uid": "tempo"}
R = "$__rate_interval"


class Dash:
    def __init__(self, uid: str, title: str, tags: list[str], desc: str, svc: str, loki_ann: bool = True,
                 time_from: str = "now-6h", variables: list[dict] | None = None):
        self.uid, self.title, self.tags, self.desc, self.svc = uid, title, tags, desc, svc
        self.panels: list[dict] = []
        self._id = 0
        self.time_from = time_from
        self.variables = variables or []
        self.loki_ann = loki_ann

    def _next(self) -> int:
        self._id += 1
        return self._id

    def row(self, title: str, y: int) -> None:
        self.panels.append({"type": "row", "title": title, "id": self._next(), "collapsed": False,
                            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []})

    def stat(self, title, expr, unit, x, y, w=4, h=4, *, decimals=None, desc="", steps=None, instant=True, color_mode="value"):
        steps = steps or [{"color": "green", "value": None}]
        self.panels.append({
            "type": "stat", "title": title, "id": self._next(), "description": desc, "datasource": PROM,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{"refId": "A", "datasource": PROM, "expr": expr, "instant": instant, "range": not instant}],
            "fieldConfig": {"defaults": {"unit": unit, "decimals": decimals, "noValue": "no data",
                                         "thresholds": {"mode": "absolute", "steps": steps}}, "overrides": []},
            "options": {"colorMode": color_mode, "graphMode": "none" if instant else "area", "textMode": "auto",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
        })

    def ts(self, title, targets, unit, x, y, w=8, h=7, *, desc="", stack=False, min=None, max=None, thresholds=None, fill=10):
        tg = [{"refId": chr(65 + i), "datasource": PROM, "expr": e, "legendFormat": lg, "range": True}
              for i, (e, lg) in enumerate(targets)]
        defaults = {"unit": unit, "min": min, "max": max,
                    "custom": {"drawStyle": "line", "lineWidth": 1, "fillOpacity": fill, "showPoints": "never", "spanNulls": True,
                               "stacking": {"mode": "normal" if stack else "none", "group": "A"}}}
        if thresholds:
            defaults["thresholds"] = {"mode": "absolute", "steps": thresholds}
            defaults["custom"]["thresholdsStyle"] = {"mode": "dashed"}
        self.panels.append({
            "type": "timeseries", "title": title, "id": self._next(), "description": desc, "datasource": PROM,
            "gridPos": {"h": h, "w": w, "x": x, "y": y}, "targets": tg,
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}},
        })

    def logs(self, title, expr, x, y, w=12, h=9):
        self.panels.append({
            "type": "logs", "title": title, "id": self._next(), "datasource": LOKI,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "queryType": "range", "maxLines": 200}],
            "options": {"showTime": True, "wrapLogMessage": True, "enableLogDetails": True, "sortOrder": "Descending",
                        "dedupStrategy": "none", "prettifyLogMessage": False},
        })

    def traces(self, title, traceql, x, y, w=12, h=9, desc=""):
        self.panels.append({
            "type": "table", "title": title, "id": self._next(), "datasource": TEMPO, "description": desc,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{"refId": "A", "datasource": TEMPO, "queryType": "traceql", "query": traceql, "limit": 20, "tableType": "traces"}],
            "options": {"showHeader": True}, "fieldConfig": {"defaults": {}, "overrides": []},
        })

    def text(self, md: str, x, y, w=24, h=3):
        self.panels.append({"type": "text", "title": "", "id": self._next(), "gridPos": {"h": h, "w": w, "x": x, "y": y},
                            "options": {"mode": "markdown", "content": md}})

    def build(self) -> dict:
        ann = [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True,
                "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"}]
        if self.loki_ann:   # change events: in production emit deploy/prompt/model/index events from CI/CD into Loki (or Prometheus)
            ann.append({"name": "Change events", "enable": True, "iconColor": "orange", "datasource": LOKI,
                        "expr": f'{{service_name="{self.svc}"}} |= "scenario change"', "titleFormat": "change", "textFormat": "{{detected_level}}"})
        return {"uid": self.uid, "title": self.title, "tags": ["ai-observability"] + self.tags, "description": self.desc,
                "schemaVersion": 39, "version": 1, "editable": True, "graphTooltip": 1, "refresh": "30s",
                "time": {"from": self.time_from, "to": "now"}, "timezone": "browser",
                "annotations": {"list": ann}, "templating": {"list": self.variables}, "panels": self.panels,
                "links": [{"title": "Handbook", "type": "link", "url": "https://akashtalole.github.io/ai-observability/", "targetBlank": True}]}

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.build(), indent=1) + "\n", encoding="utf-8")


def var_query(name: str, label: str, metric: str, svc: str) -> dict:
    return {"name": name, "label": label, "type": "query", "datasource": PROM, "includeAll": True, "multi": True,
            "allValue": ".*", "current": {"selected": True, "text": "All", "value": "$__all"}, "refresh": 2,
            "query": {"query": f'label_values({metric}{{service_name="{svc}"}}, {label})', "refId": "v"}, "sort": 1}


def inc(metric: str, sel: str, off: bool = False) -> str:
    return f"increase({metric}{{{sel}}}[$__range]{' offset $__range' if off else ''})"


def q_hist(q: float, metric: str, sel: str, off: bool = False) -> str:
    return f"histogram_quantile({q}, sum by (le) ({inc(metric + '_bucket', sel, off)}))"


def ratio(num: str, den: str) -> str:
    return f"({num}) / ({den})"


def z(expr: str) -> str:
    """Counters that only exist after the first event (errors, loops...) should read 0, not "no data"."""
    return f"(({expr}) or vector(0))"


def delta(fn) -> str:
    return f"({fn(False)}) / ({fn(True)}) - 1"


GOOD_UP = [{"color": "red", "value": None}, {"color": "green", "value": 0}]
BAD_UP = [{"color": "green", "value": None}, {"color": "red", "value": 0.05}]


# ------------------------------------------------------------------------------------------------ RAG
def rag() -> None:
    svc = "support-rag"
    sel = f'service_name="{svc}",tenant=~"$tenant"'
    s0 = f'service_name="{svc}"'
    d = Dash("rag-overview", "RAG - Latency, Quality & Cost", ["rag", "use-case"],
             "Latency, quality and cost of the support-rag service. KPI tiles follow the selected time range and compare with the previous period.",
             svc, variables=[var_query("tenant", "tenant", "rag_requests_total", svc)])
    y = 0
    d.row("Selected range (vs previous period of the same length)", y); y += 1
    req = lambda off=False, extra="": inc("rag_requests_total", sel + extra, off)
    d.stat("Requests", f"sum({req()})", "short", 0, y, 3)
    d.stat("Error ratio", ratio(z(f"sum({req(extra=',status=\"error\"')})"), f"sum({req()})"), "percentunit", 3, y, 3, decimals=2,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 0.01}, {"color": "red", "value": 0.05}])
    d.stat("TTFT p95", q_hist(0.95, "rag_ttft_seconds", sel), "s", 6, y, 3, decimals=2,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 1.5}, {"color": "red", "value": 2}])
    d.stat("Latency p95", q_hist(0.95, "rag_request_duration_seconds", sel), "s", 9, y, 3, decimals=2,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 6}, {"color": "red", "value": 8}])
    cpr = lambda off=False: ratio(f"sum({inc('rag_cost_usd_total', sel, off)})", f"sum({req(off)})")
    d.stat("Cost / request", cpr(), "currencyUSD", 12, y, 3, decimals=4)
    d.stat("Spend", f"sum({inc('rag_cost_usd_total', sel)})", "currencyUSD", 15, y, 3, decimals=2)
    gnd = lambda off=False: ratio(f"sum({inc('rag_eval_score_sum', sel + ',metric=\"groundedness\"', off)})",
                                  f"sum({inc('rag_eval_score_count', sel + ',metric=\"groundedness\"', off)})")
    d.stat("Groundedness", gnd(), "none", 18, y, 3, decimals=3,
           steps=[{"color": "red", "value": None}, {"color": "orange", "value": 0.8}, {"color": "green", "value": 0.85}])
    d.stat("Retrieval unhealthy", ratio(z(f"sum({inc('rag_retrieval_empty_total', s0)})"), f"sum({inc('rag_requests_total', s0)})"), "percentunit", 21, y, 3, decimals=1,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 0.03}, {"color": "red", "value": 0.05}])
    y += 4
    d.stat("Δ Latency p95", delta(lambda o: q_hist(0.95, "rag_request_duration_seconds", sel, o)), "percentunit", 0, y, 6, 3,
           steps=BAD_UP, desc="vs previous period of equal length")
    d.stat("Δ Cost / request", delta(cpr), "percentunit", 6, y, 6, 3, steps=BAD_UP)
    d.stat("Δ Groundedness", delta(gnd), "percentunit", 12, y, 6, 3, steps=[{"color": "red", "value": None}, {"color": "green", "value": -0.02}])
    d.stat("Δ Requests", delta(lambda o: f"sum({req(o)})"), "percentunit", 18, y, 6, 3, steps=[{"color": "blue", "value": None}])
    y += 3

    d.row("Latency", y); y += 1
    d.ts("End-to-end latency p50 / p95 / p99", [
        (f"histogram_quantile({q}, sum by (le) (rate(rag_request_duration_seconds_bucket{{{sel}}}[{R}])))", f"p{int(q*100)}") for q in (0.5, 0.95, 0.99)],
        "s", 0, y, 8, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 8}], desc="SLO: p95 < 8s (dashed)")
    d.ts("TTFT p50 / p95 by model", [
        (f"histogram_quantile(0.95, sum by (le, model) (rate(rag_ttft_seconds_bucket{{{sel}}}[{R}])))", "p95 {{model}}"),
        (f"histogram_quantile(0.5, sum by (le, model) (rate(rag_ttft_seconds_bucket{{{sel}}}[{R}])))", "p50 {{model}}")],
        "s", 8, y, 8, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 2}], desc="SLO: p95 < 2s (dashed)")
    d.ts("Stage latency p95", [
        (f"histogram_quantile(0.95, sum by (le, stage) (rate(rag_stage_duration_seconds_bucket{{{s0}}}[{R}])))", "{{stage}}")],
        "s", 16, y, 8, desc="Where the time goes: embed / vector_search / rerank / guardrails / llm")
    y += 7
    d.ts("Time spent per stage (stacked)", [
        (f"sum by (stage) (rate(rag_stage_duration_seconds_sum{{{s0}}}[{R}]))", "{{stage}}")], "s", 0, y, 8, stack=True, fill=40,
        desc="Seconds of work per second; the share shows the dominant stage")
    d.ts("Request rate by status", [(f"sum by (status) (rate(rag_requests_total{{{sel}}}[{R}]))", "{{status}}")], "reqps", 8, y, 8, stack=True, fill=30)
    d.ts("Error ratio, retries & fallbacks", [
        (z(f'sum(rate(rag_requests_total{{{sel},status="error"}}[{R}]))') + f' / sum(rate(rag_requests_total{{{sel}}}[{R}]))', "error ratio"),
        (z(f"sum(rate(rag_llm_retries_total{{{s0}}}[{R}]))") + f" / sum(rate(rag_requests_total{{{s0}}}[{R}]))", "retries / request"),
        (z(f"sum(rate(rag_llm_fallbacks_total{{{s0}}}[{R}]))") + f" / sum(rate(rag_requests_total{{{s0}}}[{R}]))", "fallbacks / request")],
        "percentunit", 16, y, 8, min=0, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 0.005}], desc="Availability SLO 99.5% -> 0.5% budget (dashed)")
    y += 7

    d.row("Quality", y); y += 1
    d.ts("Online eval scores (mean)", [
        (f'sum by (metric) (rate(rag_eval_score_sum{{{sel}}}[{R}])) / sum by (metric) (rate(rag_eval_score_count{{{sel}}}[{R}]))', "{{metric}}")],
        "none", 0, y, 8, min=0, max=1, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 0.8}],
        desc="LLM-as-judge on a sampled slice of traffic, written back asynchronously. Check sample size before trusting a dip.")
    d.ts("Groundedness below 0.7 (share of scored answers)", [
        (f'1 - sum(rate(rag_eval_score_bucket{{{sel},metric="groundedness",le="0.7"}}[{R}])) / sum(rate(rag_eval_score_count{{{sel},metric="groundedness"}}[{R}]))', "ungrounded share")],
        "percentunit", 8, y, 8, min=0)
    d.ts("Scored samples per minute", [(f"sum by (metric) (rate(rag_eval_score_count{{{sel}}}[{R}])) * 60", "{{metric}}")], "short", 16, y, 8,
         desc="Quality charts are statistical: show n next to every score.")
    y += 7
    d.ts("Retrieval top-1 similarity (p10 / p50)", [
        (f"histogram_quantile(0.5, sum by (le) (rate(rag_retrieval_top1_score_bucket{{{s0}}}[{R}])))", "p50"),
        (f"histogram_quantile(0.1, sum by (le) (rate(rag_retrieval_top1_score_bucket{{{s0}}}[{R}])))", "p10")], "none", 0, y, 8, min=0, max=1)
    d.ts("Empty / low-score retrieval ratio", [
        (f"sum by (kind) (rate(rag_retrieval_empty_total{{{s0}}}[{R}])) / scalar(sum(rate(rag_requests_total{{{s0}}}[{R}])))", "{{kind}}")],
        "percentunit", 8, y, 8, min=0, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 0.05}])
    d.ts("Index freshness (age of newest document)", [(f"max(rag_index_age_seconds{{{s0}}})", "index age")], "s", 16, y, 8,
         thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 172800}], desc="Alert at 48h")
    y += 7
    d.ts("User feedback: thumbs-down ratio", [
        (f'sum(rate(rag_feedback_total{{{s0},rating="down"}}[{R}])) / sum(rate(rag_feedback_total{{{s0}}}[{R}]))', "thumbs down")], "percentunit", 0, y, 8, min=0)
    d.ts("Eval backlog age", [(f"max(rag_eval_queue_age_seconds{{{s0}}})", "oldest unevaluated trace")], "s", 8, y, 8,
         desc="If this grows, quality signals are stale.")
    d.ts("Guardrail events", [(f"sum by (category, action) (rate(rag_guardrail_events_total{{{s0}}}[{R}]))", "{{category}} / {{action}}")], "ops", 16, y, 8)
    y += 7

    d.row("Cost", y); y += 1
    d.ts("Cost per request by model", [
        (f"sum by (model) (rate(rag_cost_usd_total{{{sel}}}[{R}])) / scalar(sum(rate(rag_requests_total{{{sel}}}[{R}])))", "{{model}}"),
        (f"sum(rate(rag_cost_usd_total{{{sel}}}[{R}])) / sum(rate(rag_requests_total{{{sel}}}[{R}]))", "total")], "currencyUSD", 0, y, 8, min=0)
    d.ts("Spend per hour by tenant", [(f"sum by (tenant) (rate(rag_cost_usd_total{{{sel}}}[{R}])) * 3600", "{{tenant}}")], "currencyUSD", 8, y, 8, stack=True, fill=40)
    d.ts("Tokens per second (input vs output)", [(f"sum by (direction) (rate(rag_tokens_total{{{sel}}}[{R}]))", "{{direction}}")], "short", 16, y, 8, stack=True, fill=30)
    y += 7
    d.ts("Context tokens p50 / p95", [
        (f"histogram_quantile(0.5, sum by (le) (rate(rag_context_tokens_bucket{{{s0}}}[{R}])))", "p50"),
        (f"histogram_quantile(0.95, sum by (le) (rate(rag_context_tokens_bucket{{{s0}}}[{R}])))", "p95")], "short", 0, y, 8,
        desc="Context bloat drives both cost and latency")
    d.ts("Semantic cache hit ratio", [
        (f'sum(rate(rag_cache_lookups_total{{{s0},result="hit"}}[{R}])) / sum(rate(rag_cache_lookups_total{{{s0}}}[{R}]))', "hit ratio")], "percentunit", 8, y, 8, min=0, max=1)
    d.ts("Cost by feature", [(f"sum by (feature) (rate(rag_cost_usd_total{{{sel}}}[{R}])) * 3600", "{{feature}}")], "currencyUSD", 16, y, 8, stack=True, fill=40)
    y += 7

    d.row("Logs & traces (click a trace_id / trace row to pivot)", y); y += 1
    d.logs("Warnings & errors", f'{{service_name="{svc}"}} | detected_level=~"warn|error"', 0, y, 12)
    d.traces("Slow traces (> 6s)", f'{{ resource.service.name = "{svc}" && name = "rag.request" && duration > 6s }}', 12, y, 12,
             desc="TraceQL. Tail sampling keeps all slow, error and flagged traces.")
    y += 9
    d.traces("Error traces", f'{{ resource.service.name = "{svc}" && status = error }}', 0, y, 12)
    d.traces("Flagged by cheap checks (empty / low-score retrieval)", f'{{ resource.service.name = "{svc}" && span.eval.flagged = true }}', 12, y, 12)
    d.write(ROOT / "rag/dashboards/rag-overview.json")

    t = Dash("rag-trends", "RAG - Trends (weeks to months)", ["rag", "use-case", "trends"],
             "Month-over-month view built on recording rules. Set the time range to 30d / 90d / 6M. Prometheus keeps 90d by default; "
             "use Mimir/Thanos/VictoriaMetrics (or the ClickHouse rollups from the handbook) for 6-18 months.", svc, time_from="now-30d")
    t.text("**Long-range view.** Panels read daily recording rules (`rag:*:_1d`) so they stay fast over months. Retention is the limit: "
           "extend with Mimir/Thanos/VictoriaMetrics or serve this dashboard from the ClickHouse wide-fact rollups "
           "([storage guide](https://akashtalole.github.io/ai-observability/architecture/storage-and-retention/)). "
           "Overlay change events (deploys, prompt, model, index) to explain every shift.", 0, 0, 24, 3)
    t.ts("p95 latency (daily)", [("rag:latency_seconds:p95_1d", "p95")], "s", 0, 3, 8, min=0)
    t.ts("Cost per request (daily)", [("rag:cost_per_request_usd:ratio_1d", "USD / request")], "currencyUSD", 8, 3, 8, min=0)
    t.ts("Groundedness (daily mean)", [("rag:groundedness:mean_1d", "groundedness")], "none", 16, 3, 8, min=0, max=1)
    t.ts("Week-over-week change", [
        ("rag:latency_seconds:p95_1d / (rag:latency_seconds:p95_1d offset 7d) - 1", "p95 latency"),
        ("rag:cost_per_request_usd:ratio_1d / (rag:cost_per_request_usd:ratio_1d offset 7d) - 1", "cost / request"),
        ("rag:groundedness:mean_1d / (rag:groundedness:mean_1d offset 7d) - 1", "groundedness")], "percentunit", 0, 10, 12)
    t.ts("Daily request volume & spend", [
        (f'sum(increase(rag_requests_total{{{s0}}}[1d]))', "requests / day"), (f'sum(increase(rag_cost_usd_total{{{s0}}}[1d])) * 1000', "spend x1000 USD / day")],
        "short", 12, 10, 12)
    t.write(ROOT / "rag/dashboards/rag-trends.json")


# ------------------------------------------------------------------------------------------ multi-agent
def agents() -> None:
    svc = "research-agents"
    s0 = f'service_name="{svc}"'
    sel = f'{s0},task_type=~"$task_type"'
    d = Dash("agents-overview", "Multi-agent - Tasks, Trajectories & Cost", ["agents", "use-case"],
             "Task outcomes, steps, tool use, handoffs, loops, safety and cost for the research-agents system.", svc,
             variables=[var_query("task_type", "task_type", "agent_tasks_total", svc)])
    y = 0
    d.row("Selected range (vs previous period)", y); y += 1
    tasks = lambda off=False, extra="": f"sum({inc('agent_tasks_total', sel + extra, off)})"
    d.stat("Tasks", tasks(), "short", 0, y, 3)
    succ = lambda off=False: ratio(tasks(off, ',outcome="success"'), tasks(off))
    d.stat("Success rate", succ(), "percentunit", 3, y, 3, decimals=1,
           steps=[{"color": "red", "value": None}, {"color": "orange", "value": 0.7}, {"color": "green", "value": 0.85}])
    cpt = lambda off=False: ratio(f"sum({inc('agent_task_cost_sum', sel, off)})", f"sum({inc('agent_task_cost_count', sel, off)})")
    d.stat("Cost / task", cpt(), "currencyUSD", 6, y, 3, decimals=4)
    d.stat("Steps / task p95", q_hist(0.95, "agent_task_steps", sel), "none", 9, y, 3, decimals=0,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 15}, {"color": "red", "value": 22}])
    d.stat("Task duration p95", q_hist(0.95, "agent_task_duration_seconds", sel), "s", 12, y, 3, decimals=1,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 30}, {"color": "red", "value": 45}])
    terr = lambda off=False: ratio(z(f"sum({inc('agent_tool_calls_total', s0 + ',status=\"error\"', off)})"), f"sum({inc('agent_tool_calls_total', s0 + ',status!=\"denied\"', off)})")
    d.stat("Tool error ratio", terr(), "percentunit", 15, y, 3, decimals=1,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 0.05}, {"color": "red", "value": 0.15}])
    d.stat("Loops detected", z(f"sum({inc('agent_loops_detected_total', s0)})"), "short", 18, y, 3,
           steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}])
    d.stat("Injection missed", z(f'sum({inc("agent_guardrail_events_total", s0 + ",action=\"missed\"")})'), "short", 21, y, 3,
           steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}], desc="Indirect prompt injections that were not blocked")
    y += 4
    d.stat("Δ Success rate", delta(succ), "percentunit", 0, y, 6, 3, steps=[{"color": "red", "value": None}, {"color": "green", "value": -0.02}])
    d.stat("Δ Cost / task", delta(cpt), "percentunit", 6, y, 6, 3, steps=BAD_UP)
    d.stat("Δ Steps / task p95", delta(lambda o: q_hist(0.95, "agent_task_steps", sel, o)), "percentunit", 12, y, 6, 3, steps=BAD_UP)
    d.stat("Δ Tool error ratio", delta(terr), "percentunit", 18, y, 6, 3, steps=BAD_UP)
    y += 3

    d.row("Outcomes & efficiency", y); y += 1
    d.ts("Tasks by outcome", [(f"sum by (outcome) (rate(agent_tasks_total{{{sel}}}[{R}]))", "{{outcome}}")], "ops", 0, y, 8, stack=True, fill=30)
    d.ts("Task success rate", [(f'sum(rate(agent_tasks_total{{{sel},outcome="success"}}[{R}])) / sum(rate(agent_tasks_total{{{sel}}}[{R}]))', "success")],
         "percentunit", 8, y, 8, min=0, max=1, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 0.7}])
    d.ts("Abnormal terminations by reason", [(f"sum by (reason) (rate(agent_terminations_total{{{s0}}}[{R}]))", "{{reason}}")], "ops", 16, y, 8, stack=True, fill=30,
         desc="max_steps, budget_exceeded, timeout, loop: the guardrails that stop runaway agents")
    y += 7
    d.ts("Steps per task p50 / p95", [
        (f"histogram_quantile({q}, sum by (le) (rate(agent_task_steps_bucket{{{sel}}}[{R}])))", f"p{int(q*100)}") for q in (0.5, 0.95)],
        "none", 0, y, 8, min=0, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 25}], desc="Hard limit 25 steps")
    d.ts("Task duration p50 / p95", [
        (f"histogram_quantile({q}, sum by (le) (rate(agent_task_duration_seconds_bucket{{{sel}}}[{R}])))", f"p{int(q*100)}") for q in (0.5, 0.95)], "s", 8, y, 8, min=0)
    d.ts("Cost per task", [
        (f"sum(rate(agent_task_cost_sum{{{sel}}}[{R}])) / sum(rate(agent_task_cost_count{{{sel}}}[{R}]))", "mean"),
        (f"histogram_quantile(0.95, sum by (le) (rate(agent_task_cost_bucket{{{sel}}}[{R}])))", "p95")], "currencyUSD", 16, y, 8, min=0,
        desc="Cost per *successful* task is the number to manage; compare with success rate")
    y += 7

    d.row("Agents, tools & handoffs", y); y += 1
    d.ts("LLM calls by agent", [(f"sum by (agent) (rate(agent_llm_calls_total{{{s0}}}[{R}]))", "{{agent}}")], "ops", 0, y, 8, stack=True, fill=30)
    d.ts("Spend per hour by agent", [(f"sum by (agent) (rate(agent_cost_usd_total{{{s0}}}[{R}])) * 3600", "{{agent}}")], "currencyUSD", 8, y, 8, stack=True, fill=40)
    d.ts("Tokens per second", [(f"sum by (direction) (rate(agent_tokens_total{{{s0}}}[{R}]))", "{{direction}}")], "short", 16, y, 8, stack=True, fill=30)
    y += 7
    d.ts("Tool calls by tool and status", [(f"sum by (tool, status) (rate(agent_tool_calls_total{{{s0}}}[{R}]))", "{{tool}} {{status}}")], "ops", 0, y, 8)
    d.ts("Tool error ratio by tool", [
        (f'sum by (tool) (rate(agent_tool_calls_total{{{s0},status="error"}}[{R}])) / sum by (tool) (rate(agent_tool_calls_total{{{s0},status!="denied"}}[{R}]))', "{{tool}}")],
        "percentunit", 8, y, 8, min=0, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 0.15}])
    d.ts("Tool latency p95", [(f"histogram_quantile(0.95, sum by (le, tool) (rate(agent_tool_duration_seconds_bucket{{{s0}}}[{R}])))", "{{tool}}")], "s", 16, y, 8)
    y += 7
    d.ts("Handoffs (from -> to)", [(f"sum by (from, to) (rate(agent_handoffs_total{{{s0}}}[{R}]))", "{{from}} -> {{to}}")], "ops", 0, y, 8, stack=True, fill=30)
    d.ts("Plan revisions", [(f"sum by (cause) (rate(agent_plan_revisions_total{{{s0}}}[{R}]))", "{{cause}}")], "ops", 8, y, 8, stack=True, fill=30,
         desc="Reviewer rejections and tool-failure replans drive cost")
    d.ts("Active tasks", [(f"sum(agent_active_tasks{{{s0}}})", "in flight")], "none", 16, y, 8, min=0)
    y += 7

    d.row("Safety & governance", y); y += 1
    d.ts("Loop detections", [(f"sum by (tool) (rate(agent_loops_detected_total{{{s0}}}[{R}]))", "{{tool}}")], "ops", 0, y, 8, desc="Identical tool call + args repeated 3+ times")
    d.ts("Write-tool approvals", [(f"sum by (decision) (rate(agent_approvals_total{{{s0}}}[{R}]))", "{{decision}}")], "ops", 8, y, 8, stack=True, fill=30,
         desc="Human-in-the-loop decisions for side-effecting tools")
    d.ts("Indirect prompt injection", [(f"sum by (action) (rate(agent_guardrail_events_total{{{s0}}}[{R}]))", "{{action}}")], "ops", 16, y, 8, stack=True, fill=30,
         desc="blocked = detected; missed = reached the agent")
    y += 7

    d.row("Logs & traces", y); y += 1
    d.logs("Warnings & errors", f'{{service_name="{svc}"}} | detected_level=~"warn|error"', 0, y, 12)
    d.traces("Expensive / long tasks (> 30s)", f'{{ resource.service.name = "{svc}" && name = "invoke_agent supervisor" && duration > 30s }}', 12, y, 12,
             desc="Open a trace to see the full trajectory: invoke_agent -> chat -> execute_tool")
    y += 9
    d.traces("Failed or abandoned tasks", f'{{ resource.service.name = "{svc}" && span.app.task.outcome != "success" && name = "invoke_agent supervisor" }}', 0, y, 12)
    d.traces("Detected loops", f'{{ resource.service.name = "{svc}" && span.loop.detected = true }}', 12, y, 12)
    d.write(ROOT / "multi-agent/dashboards/agents-overview.json")

    t = Dash("agents-trends", "Multi-agent - Trends (weeks to months)", ["agents", "use-case", "trends"],
             "Long-range cost per task and success rate from daily recording rules.", svc, time_from="now-30d")
    t.ts("Success rate (daily)", [("agent:task_success_ratio:ratio_1d", "success")], "percentunit", 0, 0, 12, min=0, max=1)
    t.ts("Cost per task (daily)", [("agent:cost_per_task_usd:ratio_1d", "USD / task")], "currencyUSD", 12, 0, 12, min=0)
    t.ts("Week-over-week change", [
        ("agent:task_success_ratio:ratio_1d / (agent:task_success_ratio:ratio_1d offset 7d) - 1", "success rate"),
        ("agent:cost_per_task_usd:ratio_1d / (agent:cost_per_task_usd:ratio_1d offset 7d) - 1", "cost / task")], "percentunit", 0, 7, 24)
    t.write(ROOT / "multi-agent/dashboards/agents-trends.json")


# ------------------------------------------------------------------------------------------- chatbot
def chatbot() -> None:
    svc = "support-chatbot"
    s0 = f'service_name="{svc}"'
    sel = f'{s0},intent=~"$intent"'
    d = Dash("chatbot-overview", "Chatbot - Conversations, Quality & Cost", ["chatbot", "use-case"],
             "Conversation-level health of the support-chatbot: containment, escalation, TTFT, quality, refusals, context and cost.", svc,
             variables=[var_query("intent", "intent", "chat_intents_total", svc)])
    y = 0
    d.row("Selected range (vs previous period)", y); y += 1
    sess = lambda off=False, extra="": f"sum({inc('chat_sessions_total', sel + extra, off)})"
    d.stat("Conversations", sess(), "short", 0, y, 3)
    cont = lambda off=False: ratio(sess(off, ',outcome="resolved"'), sess(off))
    d.stat("Containment", cont(), "percentunit", 3, y, 3, decimals=1,
           steps=[{"color": "red", "value": None}, {"color": "orange", "value": 0.45}, {"color": "green", "value": 0.6}], desc="Resolved without a human")
    d.stat("Escalation", ratio(sess(extra=',outcome="escalated"'), sess()), "percentunit", 6, y, 3, decimals=1,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 0.3}, {"color": "red", "value": 0.4}])
    d.stat("Abandonment", ratio(sess(extra=',outcome="abandoned"'), sess()), "percentunit", 9, y, 3, decimals=1,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 0.15}, {"color": "red", "value": 0.3}])
    d.stat("TTFT p95", q_hist(0.95, "chat_ttft_seconds", s0), "s", 12, y, 3, decimals=2,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 1.0}, {"color": "red", "value": 1.5}])
    cps = lambda off=False: ratio(f"sum({inc('chat_cost_usd_total', sel, off)})", sess(off))
    d.stat("Cost / conversation", cps(), "currencyUSD", 15, y, 3, decimals=4)
    goal = lambda off=False: ratio(f"sum({inc('chat_eval_score_sum', s0 + ',metric=\"goal_completion\"', off)})", f"sum({inc('chat_eval_score_count', s0 + ',metric=\"goal_completion\"', off)})")
    d.stat("Goal completion (judge)", goal(), "none", 18, y, 3, decimals=2,
           steps=[{"color": "red", "value": None}, {"color": "orange", "value": 0.75}, {"color": "green", "value": 0.85}])
    d.stat("Turn error ratio", ratio(z(f"sum({inc('chat_turns_total', s0 + ',status=\"error\"')})"), f"sum({inc('chat_turns_total', s0)})"), "percentunit", 21, y, 3, decimals=2,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 0.01}, {"color": "red", "value": 0.05}])
    y += 4
    d.stat("Δ Containment", delta(cont), "percentunit", 0, y, 8, 3, steps=[{"color": "red", "value": None}, {"color": "green", "value": -0.02}])
    d.stat("Δ Cost / conversation", delta(cps), "percentunit", 8, y, 8, 3, steps=BAD_UP)
    d.stat("Δ Goal completion", delta(goal), "percentunit", 16, y, 8, 3, steps=[{"color": "red", "value": None}, {"color": "green", "value": -0.02}])
    y += 3

    d.row("Resolution & conversation quality", y); y += 1
    d.ts("Conversations by outcome", [(f"sum by (outcome) (rate(chat_sessions_total{{{sel}}}[{R}]))", "{{outcome}}")], "ops", 0, y, 8, stack=True, fill=30)
    d.ts("Containment / escalation / abandonment", [
        (f'sum(rate(chat_sessions_total{{{sel},outcome="{o}"}}[{R}])) / sum(rate(chat_sessions_total{{{sel}}}[{R}]))', o) for o in ("resolved", "escalated", "abandoned")],
        "percentunit", 8, y, 8, min=0, max=1)
    d.ts("Turns per conversation p50 / p95", [
        (f"histogram_quantile({q}, sum by (le) (rate(chat_session_turns_bucket{{{s0}}}[{R}])))", f"p{int(q*100)}") for q in (0.5, 0.95)], "none", 16, y, 8, min=0)
    y += 7
    d.ts("Conversation-level eval scores", [
        (f"sum by (metric) (rate(chat_eval_score_sum{{{s0}}}[{R}])) / sum by (metric) (rate(chat_eval_score_count{{{s0}}}[{R}]))", "{{metric}}")],
        "none", 0, y, 8, min=0, max=1, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 0.75}])
    d.ts("Thumbs-down ratio", [(f'sum(rate(chat_feedback_total{{{s0},rating="down"}}[{R}])) / sum(rate(chat_feedback_total{{{s0}}}[{R}]))', "thumbs down")], "percentunit", 8, y, 8, min=0)
    d.ts("Intent mix", [(f"sum by (intent) (rate(chat_intents_total{{{s0}}}[{R}]))", "{{intent}}")], "ops", 16, y, 8, stack=True, fill=30,
         desc="Watch for new/shifting intents: an input-drift early warning")
    y += 7
    d.ts("Containment by intent", [
        (f'sum by (intent) (rate(chat_sessions_total{{{s0},outcome="resolved"}}[{R}])) / sum by (intent) (rate(chat_sessions_total{{{s0}}}[{R}]))', "{{intent}}")],
        "percentunit", 0, y, 12, min=0, max=1, desc="Aggregate means hide regressions in important intents")
    d.ts("Unsupported-intent fallbacks", [(f"sum(rate(chat_fallbacks_total{{{s0}}}[{R}]))", "fallbacks/s")], "ops", 12, y, 12)
    y += 7

    d.row("Responsiveness & reliability", y); y += 1
    d.ts("TTFT p50 / p95 by channel", [
        (f"histogram_quantile(0.95, sum by (le, channel) (rate(chat_ttft_seconds_bucket{{{s0}}}[{R}])))", "p95 {{channel}}"),
        (f"histogram_quantile(0.5, sum by (le) (rate(chat_ttft_seconds_bucket{{{s0}}}[{R}])))", "p50 all")],
        "s", 0, y, 8, min=0, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 1.5}])
    d.ts("Turn duration p95 by intent", [(f"histogram_quantile(0.95, sum by (le, intent) (rate(chat_turn_duration_seconds_bucket{{{s0}}}[{R}])))", "{{intent}}")], "s", 8, y, 8, min=0)
    d.ts("Turn error ratio & streaming stalls", [
        (z(f'sum(rate(chat_turns_total{{{s0},status="error"}}[{R}]))') + f' / sum(rate(chat_turns_total{{{s0}}}[{R}]))', "turn errors"),
        (z(f"sum(rate(chat_stream_stalls_total{{{s0}}}[{R}]))") + f" / sum(rate(chat_turns_total{{{s0}}}[{R}]))", "stalls / turn")], "percentunit", 16, y, 8, min=0)
    y += 7

    d.row("Safety, context & cost", y); y += 1
    d.ts("Guardrail refusals / turn", [(f'sum by (intent) (rate(chat_guardrail_events_total{{{s0},action="refused"}}[{R}])) / scalar(sum(rate(chat_turns_total{{{s0}}}[{R}])))', "{{intent}}")],
         "percentunit", 0, y, 8, stack=True, fill=30, desc="High values = over-refusal (false positives) - hurts containment")
    d.ts("Context window utilization p50 / p95", [
        (f"histogram_quantile({q}, sum by (le) (rate(chat_context_utilization_bucket{{{s0}}}[{R}])))", f"p{int(q*100)}") for q in (0.5, 0.95)],
        "percentunit", 8, y, 8, min=0, max=1)
    d.ts("Truncation events", [(z(f"sum(rate(chat_context_truncations_total{{{s0}}}[{R}]))"), "truncations/s")], "ops", 16, y, 8)
    y += 7
    d.ts("Cost per conversation", [(f"sum(rate(chat_cost_usd_total{{{sel}}}[{R}])) / sum(rate(chat_sessions_total{{{sel}}}[{R}]))", "USD / conversation")], "currencyUSD", 0, y, 8, min=0)
    d.ts("Spend per hour by intent", [(f"sum by (intent) (rate(chat_cost_usd_total{{{s0}}}[{R}])) * 3600", "{{intent}}")], "currencyUSD", 8, y, 8, stack=True, fill=40)
    d.ts("Active conversations", [(f"sum(chat_active_sessions{{{s0}}})", "active")], "none", 16, y, 8, min=0)
    y += 7

    d.row("Logs & traces", y); y += 1
    d.logs("Warnings & errors", f'{{service_name="{svc}"}} | detected_level=~"warn|error"', 0, y, 12)
    d.traces("Slow turns (> 4s)", f'{{ resource.service.name = "{svc}" && name = "chat.turn" && duration > 4s }}', 12, y, 12)
    y += 9
    d.traces("Refused turns", f'{{ resource.service.name = "{svc}" && span.guardrail.refused = true }}', 0, y, 12)
    d.traces("Streaming stalls", f'{{ resource.service.name = "{svc}" && span.stream.stalled = true }}', 12, y, 12)
    d.write(ROOT / "chatbot/dashboards/chatbot-overview.json")

    t = Dash("chatbot-trends", "Chatbot - Trends (weeks to months)", ["chatbot", "use-case", "trends"],
             "Long-range containment from daily recording rules.", svc, time_from="now-30d")
    t.ts("Containment (daily)", [("chat:containment_ratio:ratio_1d", "containment")], "percentunit", 0, 0, 12, min=0, max=1)
    t.ts("Week-over-week containment change", [("chat:containment_ratio:ratio_1d / (chat:containment_ratio:ratio_1d offset 7d) - 1", "containment")], "percentunit", 12, 0, 12)
    t.write(ROOT / "chatbot/dashboards/chatbot-trends.json")


# --------------------------------------------------------------------------------------------- platform
def platform() -> None:
    d = Dash("pipeline-health", "Telemetry pipeline health (OTel Collector)", ["platform"],
             "Is telemetry itself healthy? Drops here silently bias every other dashboard.", "otel-collector", loki_ann=False, time_from="now-1h")
    d.ts("Spans accepted vs refused vs failed to export", [
        ("sum(rate(otelcol_receiver_accepted_spans[$__rate_interval]))", "accepted"),
        ("sum(rate(otelcol_receiver_refused_spans[$__rate_interval]))", "refused"),
        ("sum by (exporter) (rate(otelcol_exporter_send_failed_spans[$__rate_interval]))", "export failed {{exporter}}")], "ops", 0, 0, 8)
    d.ts("Metric points accepted vs failed", [
        ("sum(rate(otelcol_receiver_accepted_metric_points[$__rate_interval]))", "accepted"),
        ("sum by (exporter) (rate(otelcol_exporter_send_failed_metric_points[$__rate_interval]))", "export failed {{exporter}}")], "ops", 8, 0, 8)
    d.ts("Log records accepted vs failed", [
        ("sum(rate(otelcol_receiver_accepted_log_records[$__rate_interval]))", "accepted"),
        ("sum by (exporter) (rate(otelcol_exporter_send_failed_log_records[$__rate_interval]))", "export failed {{exporter}}")], "ops", 16, 0, 8)
    d.ts("Exporter queue fill", [("max by (exporter) (otelcol_exporter_queue_size / otelcol_exporter_queue_capacity)", "{{exporter}}")], "percentunit", 0, 7, 8, min=0, max=1)
    d.ts("Collector memory (RSS)", [("max(otelcol_process_memory_rss)", "rss")], "bytes", 8, 7, 8)
    d.ts("Tail-sampling: traces dropped vs kept (sampler decisions)", [
        ("sum by (sampled) (rate(otelcol_processor_tail_sampling_count_traces_sampled[$__rate_interval]))", "sampled={{sampled}}")], "ops", 16, 7, 8)
    d.write(ROOT / "stack/grafana/dashboards/pipeline-health.json")


if __name__ == "__main__":
    rag(); agents(); chatbot(); platform()
    print("dashboards written")
