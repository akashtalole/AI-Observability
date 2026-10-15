#!/usr/bin/env python3
"""Generate Grafana dashboards modelled on the surfaces of Amazon CloudWatch Omni's agent observability.

    python scripts/gen_omni_dashboards.py

Omni surfaces (from AWS's public launch material) -> Grafana dashboards in use-cases/omni-style/dashboards/:

    Space / application health + SLOs      -> omni-space-health.json
    Fleet / agent overview                 -> omni-agent-overview.json
    Trace Explorer (+ compare mode)        -> omni-trace-explorer.json
    Session Explorer (multi-turn)          -> omni-session-explorer.json
    Agent Topology (agents, tools, links)  -> omni-agent-topology.json
    Evaluators / regression detection      -> omni-evaluations.json

They run on the open-source stack in use-cases/stack (Prometheus + Tempo + Loki) and read data the three demo apps
(support-rag, research-agents, support-chatbot) already emit. Span-derived panels use the Collector's `spanmetrics`
connector (traces_span_metrics_*), which gives uniform RED metrics for any app that follows the telemetry contract.
Not reproduced: Omni's AI assistants (Ask Assistant, DevOps Agent investigations), Playground and prompt management.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_dashboards import BAD_UP, LOKI, PROM, TEMPO, Dash, R, delta, inc, q_hist, ratio, z  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "use-cases" / "omni-style" / "dashboards"

# Span-derived metrics from the Collector's spanmetrics connector (all apps, uniform labels)
CALLS = "traces_span_metrics_calls_total"
DUR = "traces_span_metrics_duration_milliseconds_bucket"
ROOT = 'span_kind="SPAN_KIND_SERVER"'
ERR = 'status_code="STATUS_CODE_ERROR"'
SVC_ALL = '{__name__=~"traces_span_metrics_calls_total"}'


def zby(num: str, den: str) -> str:
    """Per-service zero fill: services with no errors still get a row/series (value 0)."""
    return f"(({num}) or ({den}) * 0)"


def svc_var() -> dict:
    return {"name": "service", "label": "service", "type": "query", "datasource": PROM, "includeAll": True, "multi": True,
            "allValue": ".+", "current": {"selected": True, "text": "All", "value": "$__all"}, "refresh": 2, "sort": 1,
            "query": {"query": f"label_values({CALLS}, service_name)", "refId": "v"}}


def textbox(name: str, label: str, default: str = "") -> dict:
    return {"name": name, "label": label, "type": "textbox", "query": default, "current": {"text": default, "value": default}}


def custom(name: str, label: str, options: str, default_text: str) -> dict:
    opts = [o.strip().split(" : ") for o in options.split(",")]
    return {"name": name, "label": label, "type": "custom", "query": options,
            "options": [{"text": t, "value": v, "selected": t == default_text} for t, v in opts],
            "current": next({"text": t, "value": v, "selected": True} for t, v in opts if t == default_text)}


class Omni(Dash):
    """Dash plus table / bar gauge / heatmap / trace panels used by the Omni-style views."""

    def table(self, title, targets, x, y, w=24, h=8, *, join=None, merge=False, rename=None, overrides=None, sort_by=None, desc="", matrix=None, hide=()):
        tg = [{"refId": chr(65 + i), "datasource": PROM, "expr": e, "format": "table", "instant": True, "range": False}
              for i, e in enumerate(targets)]
        tr = []
        if matrix:
            tr.append({"id": "groupingToMatrix", "options": matrix})
        elif merge:
            tr.append({"id": "merge", "options": {}})
        elif join:
            tr.append({"id": "joinByField", "options": {"byField": join, "mode": "outer"}})
        tr.append({"id": "organize", "options": {"excludeByName": {"Time": True, "Time 1": True, "Time 2": True, "Time 3": True,
                                                                  "Time 4": True, "Time 5": True, "Time 6": True, **{h: True for h in hide}},
                                                 "renameByName": rename or {}}})
        if sort_by:
            tr.append({"id": "sortBy", "options": {"fields": {}, "sort": [{"field": sort_by, "desc": True}]}})
        self.panels.append({"type": "table", "title": title, "id": self._next(), "description": desc, "datasource": PROM,
                            "gridPos": {"h": h, "w": w, "x": x, "y": y}, "targets": tg, "transformations": tr,
                            "fieldConfig": {"defaults": {"decimals": 0, "custom": {"align": "auto", "cellOptions": {"type": "auto"}}}, "overrides": overrides or []},
                            "options": {"showHeader": True, "cellHeight": "sm"}})

    def bargauge(self, title, expr, legend, unit, x, y, w=8, h=7, *, max=None, desc=""):
        self.panels.append({"type": "bargauge", "title": title, "id": self._next(), "description": desc, "datasource": PROM,
                            "gridPos": {"h": h, "w": w, "x": x, "y": y},
                            "targets": [{"refId": "A", "datasource": PROM, "expr": expr, "legendFormat": legend, "instant": True, "range": False}],
                            "fieldConfig": {"defaults": {"unit": unit, "min": 0, "max": max, "color": {"mode": "continuous-BlPu"},
                                                         "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}}, "overrides": []},
                            "options": {"displayMode": "gradient", "orientation": "horizontal", "showUnfilled": True,
                                        "reduceOptions": {"calcs": ["lastNotNull"], "values": False}}})

    def heatmap(self, title, expr, x, y, w=12, h=8, desc=""):
        self.panels.append({"type": "heatmap", "title": title, "id": self._next(), "description": desc, "datasource": PROM,
                            "gridPos": {"h": h, "w": w, "x": x, "y": y},
                            "targets": [{"refId": "A", "datasource": PROM, "expr": expr, "format": "heatmap", "legendFormat": "{{le}}", "range": True}],
                            "options": {"calculate": False, "cellGap": 1, "color": {"scheme": "Spectral", "mode": "scheme", "scale": "exponential", "reverse": False},
                                        "yAxis": {"axisPlacement": "left", "min": 0, "max": 1}, "legend": {"show": True},
                                        "tooltip": {"mode": "single", "yHistogram": False}, "rowsFrame": {"layout": "auto"}},
                            "fieldConfig": {"defaults": {"custom": {"scaleDistribution": {"type": "linear"}}}, "overrides": []}})

    def state_timeline(self, title, expr, legend, x, y, w=12, h=7, desc=""):
        self.panels.append({"type": "state-timeline", "title": title, "id": self._next(), "description": desc, "datasource": PROM,
                            "gridPos": {"h": h, "w": w, "x": x, "y": y},
                            "targets": [{"refId": "A", "datasource": PROM, "expr": expr, "legendFormat": legend, "range": True}],
                            "fieldConfig": {"defaults": {"mappings": [{"type": "value", "options": {"1": {"text": "firing", "color": "red", "index": 0}}}],
                                                         "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}]},
                                                         "custom": {"fillOpacity": 70}}, "overrides": []},
                            "options": {"mergeValues": True, "showValue": "never", "legend": {"showLegend": True}}})

    def tempo_table(self, title, traceql, x, y, w=24, h=9, *, table_type="traces", link_var=None, link_dash=None, desc="", limit=20):
        overrides = []
        if link_var and table_type == "traces":
            overrides.append({"matcher": {"id": "byName", "options": "traceID"},
                              "properties": [{"id": "links", "value": [{"title": "Open in Trace Explorer", "url": f"/d/{link_dash}?var-{link_var}=${{__value.raw}}&${{__url_time_range}}", "targetBlank": False}]}]})
        self.panels.append({"type": "table", "title": title, "id": self._next(), "datasource": TEMPO, "description": desc,
                            "gridPos": {"h": h, "w": w, "x": x, "y": y},
                            "targets": [{"refId": "A", "datasource": TEMPO, "queryType": "traceql", "query": traceql, "limit": limit, "tableType": table_type}],
                            "options": {"showHeader": True}, "fieldConfig": {"defaults": {}, "overrides": overrides}})

    def trace_view(self, title, trace_var, x, y, w=24, h=14, desc=""):
        self.panels.append({"type": "traces", "title": title, "id": self._next(), "datasource": TEMPO, "description": desc,
                            "gridPos": {"h": h, "w": w, "x": x, "y": y},
                            "targets": [{"refId": "A", "datasource": TEMPO, "queryType": "traceql", "query": f"${trace_var}"}]})

    def build(self) -> dict:
        d = super().build()
        d["links"] = [{"title": "Omni-style views", "type": "dashboards", "tags": ["omni-style"], "asDropdown": False,
                       "includeVars": True, "keepTime": True, "icon": "external link", "targetBlank": False}] + d.get("links", [])
        return d


def new(uid, title, desc, variables=None, time_from="now-1h"):
    return Omni(uid, title, ["omni-style"], desc, "", loki_ann=False, time_from=time_from, variables=[svc_var()] if variables is None else variables)


# ------------------------------------------------------------------------------------------------ overview
def overview() -> None:
    d = new("omni-agent-overview", "Omni-style · Agent fleet overview",
            "Fleet-level health across every instrumented application: requests, errors, latency, LLM/tool activity, tokens and cost.")
    sel = 'service_name=~"$service"'
    y = 0
    d.row("Fleet (selected range, vs previous period)", y); y += 1
    root = lambda off=False, extra="": f"sum({inc(CALLS, sel + ',' + ROOT + extra, off)})"
    d.stat("Requests", root(), "short", 0, y, 3)
    d.stat("Error rate", ratio(z(root(extra=',' + ERR)), root()), "percentunit", 3, y, 3, decimals=2,
           steps=[{"color": "green", "value": None}, {"color": "orange", "value": 0.01}, {"color": "red", "value": 0.05}])
    d.stat("Latency p95", f'histogram_quantile(0.95, sum by (le) ({inc(DUR, sel + "," + ROOT)})) / 1000', "s", 6, y, 3, decimals=2)
    d.stat("LLM calls", f'sum({inc(CALLS, sel + ",gen_ai_operation_name=\"chat\"")})', "short", 9, y, 3)
    d.stat("Tool calls", f'sum({inc(CALLS, sel + ",gen_ai_operation_name=\"execute_tool\"")})', "short", 12, y, 3)
    tok = lambda: "(" + " + ".join(f"(sum({inc(m, 'service_name=~\"$service\"')}) or vector(0))" for m in ("rag_tokens_total", "agent_tokens_total", "chat_tokens_total")) + ")"
    cost = lambda off=False: "(" + " + ".join(f"(sum({inc(m, 'service_name=~\"$service\"', off)}) or vector(0))" for m in ("rag_cost_usd_total", "agent_cost_usd_total", "chat_cost_usd_total")) + ")"
    d.stat("Tokens", tok(), "short", 15, y, 3)
    d.stat("Spend", cost(), "currencyUSD", 18, y, 3, decimals=2)
    d.stat("Δ Spend vs prev.", delta(cost), "percentunit", 21, y, 3, steps=BAD_UP)
    y += 4

    d.row("Applications and agents", y); y += 1
    q = lambda e: f"sum by (service_name) ({e})"
    d.table("Applications", [
        q(inc(CALLS, ROOT)), zby(q(inc(CALLS, ROOT + "," + ERR)), q(inc(CALLS, ROOT))), f'histogram_quantile(0.95, sum by (le, service_name) ({inc(DUR, ROOT)})) / 1000',
        q(inc(CALLS, 'gen_ai_operation_name="chat"')), q(inc(CALLS, 'gen_ai_operation_name="execute_tool"')),
    ], 0, y, 24, 6, join="service_name",
        rename={"Value #A": "Requests", "Value #B": "Errors", "Value #C": "p95 latency (s)", "Value #D": "LLM calls", "Value #E": "Tool calls", "service_name": "Application"},
        overrides=[{"matcher": {"id": "byName", "options": "p95 latency (s)"}, "properties": [{"id": "unit", "value": "s"}, {"id": "decimals", "value": 2}]},
                   {"matcher": {"id": "byName", "options": "Errors"}, "properties": [{"id": "custom.cellOptions", "value": {"type": "color-text"}},
                                                                                     {"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}}]}],
        sort_by="Requests", desc="One row per instrumented service (span-metrics based, uniform across apps)")
    y += 6
    d.table("Agents (multi-agent app)", [
        f"sum by (agent) ({inc('agent_llm_calls_total', '')})", f"sum by (agent) ({inc('agent_cost_usd_total', '')})",
        f"sum by (agent) ({inc('agent_tokens_total', '')})",
        f"sum by (agent) ({inc('agent_tool_calls_total', 'status=\"error\"')})", f"sum by (agent) ({inc('agent_tool_calls_total', '')})",
    ], 0, y, 24, 6, join="agent",
        rename={"Value #A": "LLM calls", "Value #B": "Cost (USD)", "Value #C": "Tokens", "Value #D": "Tool errors", "Value #E": "Tool calls", "agent": "Agent"},
        overrides=[{"matcher": {"id": "byName", "options": "Cost (USD)"}, "properties": [{"id": "unit", "value": "currencyUSD"}, {"id": "decimals", "value": 4}]}],
        sort_by="LLM calls", desc="Per-agent LLM activity, spend and tool health from the agent metrics")
    y += 6

    d.row("Traffic, latency, errors", y); y += 1
    d.ts("Requests by application", [(f"sum by (service_name) (rate({CALLS}{{{sel},{ROOT}}}[{R}]))", "{{service_name}}")], "reqps", 0, y, 8, stack=True, fill=30)
    d.ts("Latency p95 by application", [(f"histogram_quantile(0.95, sum by (le, service_name) (rate({DUR}{{{sel},{ROOT}}}[{R}]))) / 1000", "{{service_name}}")], "s", 8, y, 8, min=0)
    d.ts("Error rate by application", [(f"(sum by (service_name) (rate({CALLS}{{{sel},{ROOT},{ERR}}}[{R}])) or sum by (service_name) (rate({CALLS}{{{sel},{ROOT}}}[{R}])) * 0) / sum by (service_name) (rate({CALLS}{{{sel},{ROOT}}}[{R}]))", "{{service_name}}")],
         "percentunit", 16, y, 8, min=0)
    y += 7
    d.row("Models, tokens, cost", y); y += 1
    d.ts("LLM calls by model", [(f'sum by (gen_ai_request_model) (rate({CALLS}{{{sel},gen_ai_operation_name="chat"}}[{R}]))', "{{gen_ai_request_model}}")], "ops", 0, y, 8, stack=True, fill=30)
    d.ts("LLM latency p95 by model", [(f'histogram_quantile(0.95, sum by (le, gen_ai_request_model) (rate({DUR}{{{sel},gen_ai_operation_name="chat"}}[{R}]))) / 1000', "{{gen_ai_request_model}}")], "s", 8, y, 8, min=0)
    d.ts("Spend per hour by application", [
        (f'sum(rate(rag_cost_usd_total[{R}])) * 3600', "support-rag"), (f'sum(rate(agent_cost_usd_total[{R}])) * 3600', "research-agents"),
        (f'sum(rate(chat_cost_usd_total[{R}])) * 3600', "support-chatbot")], "currencyUSD", 16, y, 8, stack=True, fill=40)
    y += 7
    d.ts("Tokens per second", [
        (f'sum(rate(rag_tokens_total[{R}]))', "support-rag"), (f'sum(rate(agent_tokens_total[{R}]))', "research-agents"),
        (f'sum(rate(chat_tokens_total[{R}]))', "support-chatbot")], "short", 0, y, 12, stack=True, fill=30)
    d.ts("Tool call latency p95 by tool", [(f'histogram_quantile(0.95, sum by (le, gen_ai_tool_name) (rate({DUR}{{{sel},gen_ai_operation_name="execute_tool"}}[{R}]))) / 1000', "{{gen_ai_tool_name}}")], "s", 12, y, 12, min=0)
    d.write(OUT / "omni-agent-overview.json")


# --------------------------------------------------------------------------------------- trace explorer
def trace_explorer() -> None:
    d = new("omni-trace-explorer", "Omni-style · Trace Explorer",
            "Search traces, open one as a hierarchical timeline (LLM calls, tool invocations, reasoning steps) and compare two traces side by side.",
            variables=[svc_var(), custom("min_dur", "min duration", "any : 0s,> 1s : 1s,> 2s : 2s,> 5s : 5s,> 10s : 10s,> 30s : 30s", "any"),
                       custom("outcome", "status", "any : && duration >= 0s,errors : && status = error,ok : && status = ok", "any"),
                       textbox("traceId", "trace ID"), textbox("traceB", "compare with trace ID")])
    y = 0
    d.text("**How to use:** pick filters, then click a **traceID** in the results to load it below as a timeline. "
           "To compare, paste a second trace ID into *compare with trace ID* (top). Spans carry `gen_ai.*` attributes: model, tokens, tool, agent. "
           "Metrics → trace: click an exemplar on any latency panel.", 0, y, 24, 3); y += 3
    d.row("Search", y); y += 1
    d.tempo_table("Matching traces", '{ resource.service.name =~ "$service" && duration > $min_dur $outcome }', 0, y, 24, 9,
                  link_var="traceId", link_dash="omni-trace-explorer", desc="TraceQL search. The traceID column links into the timeline.")
    y += 9
    d.row("Selected trace (timeline)", y); y += 1
    d.trace_view("Trace timeline", "traceId", 0, y, 24, 16, desc="Hierarchy of spans for $traceId; set the traceId variable at the top")
    y += 16
    d.row("Compare mode", y); y += 1
    d.trace_view("Trace A", "traceId", 0, y, 12, 14)
    d.trace_view("Trace B", "traceB", 12, y, 12, 14)
    y += 14
    d.row("Operations (span metrics)", y); y += 1
    d.table("Slowest operations (p95)", [
        f'topk(15, histogram_quantile(0.95, sum by (le, service_name, span_name) ({inc(DUR, "service_name=~\"$service\"")}))) / 1000',
        f'sum by (service_name, span_name) ({inc(CALLS, "service_name=~\"$service\"")})'], 0, y, 12, 9,
        matrix=None, join=None,
        rename={"Value #A": "p95 (s)", "Value #B": "calls", "span_name": "Operation", "service_name": "Service"},
        overrides=[{"matcher": {"id": "byName", "options": "p95 (s)"}, "properties": [{"id": "unit", "value": "s"}, {"id": "decimals", "value": 2}]}],
        desc="Top operations by p95 latency across the selected services")
    d.ts("Span error rate by operation", [(f'sum by (span_name) (rate({CALLS}{{service_name=~"$service",{ERR}}}[{R}]))', "{{span_name}}")], "ops", 12, y, 12, 9, min=0)
    y += 9
    d.row("Logs for the selected trace", y); y += 1
    d.logs("Logs (trace_id = $traceId)", '{service_name=~"$service"} | trace_id="$traceId"', 0, y, 24, 8)
    d.write(OUT / "omni-trace-explorer.json")


# ----------------------------------------------------------------------------------- session explorer
def session_explorer() -> None:
    d = new("omni-session-explorer", "Omni-style · Session Explorer",
            "Multi-turn conversations: recent sessions, the turns of one session, and conversation-level health.",
            variables=[svc_var(), textbox("session", "session / conversation ID"), textbox("traceId", "trace ID")])
    y = 0
    d.text("Sessions are identified by `gen_ai.conversation.id`. Click a session in the table to see all of its turns; click a turn's trace to open the timeline.", 0, y, 24, 2); y += 2
    d.row("Conversation health (chatbot)", y); y += 1
    s = 'service_name="support-chatbot"'
    d.stat("Conversations", f"sum({inc('chat_sessions_total', s)})", "short", 0, y, 4)
    d.stat("Containment", ratio(f'sum({inc("chat_sessions_total", s + ",outcome=\"resolved\"")})', f"sum({inc('chat_sessions_total', s)})"), "percentunit", 4, y, 4, decimals=1,
           steps=[{"color": "red", "value": None}, {"color": "orange", "value": 0.6}, {"color": "green", "value": 0.75}])
    d.stat("Escalated", ratio(f'sum({inc("chat_sessions_total", s + ",outcome=\"escalated\"")})', f"sum({inc('chat_sessions_total', s)})"), "percentunit", 8, y, 4, decimals=1)
    d.stat("Abandoned", ratio(z(f'sum({inc("chat_sessions_total", s + ",outcome=\"abandoned\"")})'), f"sum({inc('chat_sessions_total', s)})"), "percentunit", 12, y, 4, decimals=1)
    d.stat("Turns / conversation p95", q_hist(0.95, "chat_session_turns", s), "none", 16, y, 4, decimals=0)
    d.stat("Cost / conversation", ratio(f"sum({inc('chat_cost_usd_total', s)})", f"sum({inc('chat_sessions_total', s)})"), "currencyUSD", 20, y, 4, decimals=4)
    y += 4
    d.ts("Conversations by outcome", [(f"sum by (outcome) (rate(chat_sessions_total{{{s}}}[{R}]))", "{{outcome}}")], "ops", 0, y, 8, stack=True, fill=30)
    d.ts("Turns per conversation p50 / p95", [(f"histogram_quantile({q}, sum by (le) (rate(chat_session_turns_bucket{{{s}}}[{R}])))", f"p{int(q*100)}") for q in (0.5, 0.95)], "none", 8, y, 8, min=0)
    d.ts("Active conversations", [(f"sum(chat_active_sessions{{{s}}})", "active")], "none", 16, y, 8, min=0)
    y += 7
    d.row("Browse sessions", y); y += 1
    d.tempo_table("Recent sessions (turn spans)", '{ span.gen_ai.conversation.id != "" && resource.service.name =~ "$service" } | select(span.gen_ai.conversation.id, span.app.intent, span.app.feature)',
                  0, y, 24, 9, table_type="spans", desc="Each row is a turn/request. Copy a conversation ID into the *session* variable.")
    y += 9
    d.row("Selected session", y); y += 1
    d.tempo_table("Turns of session $session", '{ span.gen_ai.conversation.id = "$session" } | select(span.app.intent, span.app.turn.index, span.cost.usd.total)',
                  0, y, 24, 8, table_type="spans")
    y += 8
    d.trace_view("Trace timeline for $traceId", "traceId", 0, y, 24, 14, desc="Set the traceId variable at the top (paste a traceID from the table)")
    d.write(OUT / "omni-session-explorer.json")


# -------------------------------------------------------------------------------------------- topology
def topology() -> None:
    d = new("omni-agent-topology", "Omni-style · Agent Topology",
            "Which agents hand off to which, which tools each agent uses, and how healthy each edge is.", variables=[], time_from="now-3h")
    s = 'service_name="research-agents"'
    y = 0
    d.text("Topology is shown as **matrices** (rows = caller, columns = callee/tool) and per-edge health, built from `agent_handoffs_total` and `agent_tool_calls_total`. "
           "A true node-link graph needs a node-graph data source; the matrices carry the same information.", 0, y, 24, 2); y += 2
    d.row("Handoffs and tool usage", y); y += 1
    d.table("Handoff matrix (from → to, calls)", [f"sum by (from, to) ({inc('agent_handoffs_total', s)})"], 0, y, 12, 8,
            matrix={"columnField": "to", "rowField": "from", "valueField": "Value", "emptyValue": "zero"},
            overrides=[{"matcher": {"id": "byRegexp", "options": "^(?!from).*"}, "properties": [{"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}},
                                                                                                {"id": "color", "value": {"mode": "continuous-BlPu"}}]}],
            desc="Darker = more handoffs")
    d.table("Tool usage matrix (agent × tool, calls)", [f"sum by (agent, tool) ({inc('agent_tool_calls_total', s)})"], 12, y, 12, 8,
            matrix={"columnField": "tool", "rowField": "agent", "valueField": "Value", "emptyValue": "zero"},
            overrides=[{"matcher": {"id": "byRegexp", "options": "^(?!agent).*"}, "properties": [{"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}},
                                                                                                 {"id": "color", "value": {"mode": "continuous-GrYlRd"}}]}])
    y += 8
    d.row("Edge health", y); y += 1
    d.table("Agent → tool edges: calls and error ratio", [
        f"sum by (agent, tool) ({inc('agent_tool_calls_total', s)})",
        f"sum by (agent, tool) ({inc('agent_tool_calls_total', s + ',status=\"error\"')}) / sum by (agent, tool) ({inc('agent_tool_calls_total', s)})",
    ], 0, y, 12, 9, merge=True,
        rename={"Value #A": "calls", "Value #B": "error ratio"},
        overrides=[{"matcher": {"id": "byName", "options": "error ratio"}, "properties": [{"id": "unit", "value": "percentunit"}, {"id": "decimals", "value": 1}, {"id": "custom.cellOptions", "value": {"type": "color-background"}},
                                                                                         {"id": "thresholds", "value": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 0.05}, {"color": "red", "value": 0.15}]}}]}],
        sort_by="calls")
    d.bargauge("Handoffs by edge", f'sum by (from, to) ({inc("agent_handoffs_total", s)})', "{{from}} → {{to}}", "short", 12, y, 12, 9)
    y += 9
    d.row("Per-agent activity", y); y += 1
    d.ts("LLM calls by agent", [(f"sum by (agent) (rate(agent_llm_calls_total{{{s}}}[{R}]))", "{{agent}}")], "ops", 0, y, 8, stack=True, fill=30)
    d.ts("LLM latency p95 by agent", [(f"histogram_quantile(0.95, sum by (le, agent) (rate(agent_llm_duration_seconds_bucket{{{s}}}[{R}])))", "{{agent}}")], "s", 8, y, 8, min=0)
    d.ts("Spend per hour by agent", [(f"sum by (agent) (rate(agent_cost_usd_total{{{s}}}[{R}])) * 3600", "{{agent}}")], "currencyUSD", 16, y, 8, stack=True, fill=40)
    y += 7
    d.ts("Tool error ratio by tool", [(z(f'sum by (tool) (rate(agent_tool_calls_total{{{s},status="error"}}[{R}]))') + f' / sum by (tool) (rate(agent_tool_calls_total{{{s},status!="denied"}}[{R}]))', "{{tool}}")],
         "percentunit", 0, y, 8, min=0)
    d.ts("Loop detections by tool", [(f"sum by (tool) (rate(agent_loops_detected_total{{{s}}}[{R}]))", "{{tool}}")], "ops", 8, y, 8, min=0)
    d.ts("Terminations by reason", [(f"sum by (reason) (rate(agent_terminations_total{{{s}}}[{R}]))", "{{reason}}")], "ops", 16, y, 8, stack=True, fill=30)
    y += 7
    d.tempo_table("Handoff-heavy or looping traces", '{ resource.service.name = "research-agents" && name = "invoke_agent supervisor" && span.app.task.steps > 15 }', 0, y, 24, 8,
                  link_var="traceId", link_dash="omni-trace-explorer")
    d.write(OUT / "omni-agent-topology.json")


# ------------------------------------------------------------------------------------------ evaluations
def evaluations() -> None:
    d = new("omni-evaluations", "Omni-style · Evaluations",
            "Evaluator scores over time: scorecards with change vs previous period, score distributions, pass rates, and low-scoring traces.",
            variables=[], time_from="now-3h")
    y = 0
    cards = [("Groundedness", "rag_eval_score", 'service_name="support-rag",metric="groundedness"'),
             ("Answer relevance", "rag_eval_score", 'service_name="support-rag",metric="answer_relevance"'),
             ("Context precision", "rag_eval_score", 'service_name="support-rag",metric="context_precision"'),
             ("Goal completion", "chat_eval_score", 'service_name="support-chatbot",metric="goal_completion"'),
             ("Policy compliance", "chat_eval_score", 'service_name="support-chatbot",metric="policy_compliance"')]
    d.row("Evaluator scorecards (mean over range · Δ vs previous period)", y); y += 1
    steps = [{"color": "red", "value": None}, {"color": "orange", "value": 0.75}, {"color": "green", "value": 0.85}]
    for i, (name, m, sel) in enumerate(cards):
        mean = lambda off=False, m=m, sel=sel: ratio(f"sum({inc(m + '_sum', sel, off)})", f"sum({inc(m + '_count', sel, off)})")
        d.stat(name, mean(), "none", i * 4, y, 4, 4, decimals=3, steps=steps)
        d.stat(f"Δ {name}", delta(mean), "percentunit", i * 4, y + 4, 4, 3, steps=[{"color": "red", "value": None}, {"color": "green", "value": -0.02}], decimals=1)
    d.stat("Scored samples", f"sum({inc('rag_eval_score_count', 'service_name=\"support-rag\"')}) + sum({inc('chat_eval_score_count', 'service_name=\"support-chatbot\"')})", "short", 20, y, 4, 4)
    y += 3
    y += 4
    d.row("Trends and distributions", y); y += 1
    d.ts("RAG evaluators (mean)", [(f'sum by (metric) (rate(rag_eval_score_sum{{service_name="support-rag"}}[{R}])) / sum by (metric) (rate(rag_eval_score_count{{service_name="support-rag"}}[{R}]))', "{{metric}}")],
         "none", 0, y, 8, min=0, max=1, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 0.8}])
    d.ts("Conversation evaluators (mean)", [(f'sum by (metric) (rate(chat_eval_score_sum{{service_name="support-chatbot"}}[{R}])) / sum by (metric) (rate(chat_eval_score_count{{service_name="support-chatbot"}}[{R}]))', "{{metric}}")],
         "none", 8, y, 8, min=0, max=1, thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 0.75}])
    d.ts("Scored samples per minute", [(f'sum by (metric) (rate(rag_eval_score_count[{R}])) * 60', "rag {{metric}}"), (f'sum by (metric) (rate(chat_eval_score_count[{R}])) * 60', "chat {{metric}}")],
         "short", 16, y, 8, desc="Quality charts are statistical: read every score with its sample size")
    y += 7
    d.heatmap("Groundedness distribution (RAG)", f'sum by (le) (increase(rag_eval_score_bucket{{service_name="support-rag",metric="groundedness"}}[$__interval]))', 0, y, 12, 8,
              desc="Each column is a time slice; colour = how many scored answers fell in the score bucket")
    d.heatmap("Goal completion distribution (chatbot)", f'sum by (le) (increase(chat_eval_score_bucket{{service_name="support-chatbot",metric="goal_completion"}}[$__interval]))', 12, y, 12, 8)
    y += 8
    d.row("Pass rates and regression detection", y); y += 1
    d.ts("Pass rate: share of scores ≥ 0.8", [
        (f'1 - sum by (metric) (rate(rag_eval_score_bucket{{service_name="support-rag",le="0.8"}}[{R}])) / sum by (metric) (rate(rag_eval_score_count{{service_name="support-rag"}}[{R}]))', "rag {{metric}}"),
        (f'1 - sum by (metric) (rate(chat_eval_score_bucket{{service_name="support-chatbot",le="0.8"}}[{R}])) / sum by (metric) (rate(chat_eval_score_count{{service_name="support-chatbot"}}[{R}]))', "chat {{metric}}")],
         "percentunit", 0, y, 12, min=0, max=1)
    d.ts("Groundedness: now vs one hour earlier (regression check)", [
        (f'sum(rate(rag_eval_score_sum{{service_name="support-rag",metric="groundedness"}}[10m])) / sum(rate(rag_eval_score_count{{service_name="support-rag",metric="groundedness"}}[10m]))', "now"),
        (f'sum(rate(rag_eval_score_sum{{service_name="support-rag",metric="groundedness"}}[10m] offset 1h)) / sum(rate(rag_eval_score_count{{service_name="support-rag",metric="groundedness"}}[10m] offset 1h))', "1 h earlier")],
         "none", 12, y, 12, min=0, max=1)
    y += 7
    d.row("Low-scoring and flagged traces", y); y += 1
    d.tempo_table("Flagged traces (empty/low retrieval, failed/abandoned tasks)", '{ span.eval.flagged = true }', 0, y, 12, 9, link_var="traceId", link_dash="omni-trace-explorer")
    d.tempo_table("Evaluation spans (judge runs linked to traces)", '{ name = "rag.evaluate" } | select(span.eval.groundedness, span.eval.answer_relevance, span.eval.context_precision)', 12, y, 12, 9, table_type="spans")
    y += 9
    d.text("**Experiments / offline evaluation.** Omni compares agent variants and builds golden datasets from traces. With this stack, run the offline gate "
           "([`examples/scoring/offline_eval.py`](https://github.com/akashtalole/ai-observability/blob/main/examples/scoring/offline_eval.py)) in CI and push its results as a metric "
           "such as `eval_offline_score{dataset,config,metric}` (Pushgateway or OTLP) to chart variants here.", 0, y, 24, 3)
    d.write(OUT / "omni-evaluations.json")


# --------------------------------------------------------------------------------------- space health
def space_health() -> None:
    d = new("omni-space-health", "Omni-style · Space health & SLOs",
            "A team's 'Space': every application it owns with SLO attainment, burn rate, error budget, active alerts, dependencies and change events.")
    y = 0
    d.row("SLOs per application (selected range)", y); y += 1
    sel = 'service_name=~"$service"'
    tot = f"sum by (service_name) ({inc(CALLS, sel + ',' + ROOT)})"
    err = zby(f"sum by (service_name) ({inc(CALLS, sel + ',' + ROOT + ',' + ERR)})", tot)
    avail = lambda: "1 - " + ratio(err, tot)
    d.table("Application SLO scorecard", [
        avail(),
        f'histogram_quantile(0.95, sum by (le, service_name) ({inc(DUR, sel + "," + ROOT)})) / 1000',
        f"sum by (service_name) ({inc(CALLS, sel + ',' + ROOT)})",
        "1 - (" + ratio(err, tot) + ") / 0.005",
    ], 0, y, 24, 6, join="service_name",
        rename={"Value #A": "Availability", "Value #B": "Latency p95 (s)", "Value #C": "Requests", "Value #D": "Error budget left (99.5% SLO)", "service_name": "Application"},
        overrides=[{"matcher": {"id": "byName", "options": "Availability"}, "properties": [{"id": "unit", "value": "percentunit"}, {"id": "decimals", "value": 2}, {"id": "custom.cellOptions", "value": {"type": "color-background"}},
                                                                                         {"id": "thresholds", "value": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "orange", "value": 0.99}, {"color": "green", "value": 0.995}]}}]},
                   {"matcher": {"id": "byName", "options": "Error budget left (99.5% SLO)"}, "properties": [{"id": "unit", "value": "percentunit"}, {"id": "custom.cellOptions", "value": {"type": "gauge", "mode": "gradient"}},
                                                                                                           {"id": "min", "value": 0}, {"id": "max", "value": 1}, {"id": "thresholds", "value": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "orange", "value": 0.25}, {"color": "green", "value": 0.5}]}}]},
                   {"matcher": {"id": "byName", "options": "Latency p95 (s)"}, "properties": [{"id": "unit", "value": "s"}, {"id": "decimals", "value": 2}]}],
        desc="Budget left = 1 - (error ratio / 0.5%) over the selected range; below 0 means the SLO is breached")
    y += 6
    d.ts("Error-budget burn rate by application", [(ratio(zby(f"sum by (service_name) (rate({CALLS}{{{sel},{ROOT},{ERR}}}[{R}]))", f"sum by (service_name) (rate({CALLS}{{{sel},{ROOT}}}[{R}]))"), f"sum by (service_name) (rate({CALLS}{{{sel},{ROOT}}}[{R}]))") + " / 0.005", "{{service_name}}")],
         "none", 0, y, 12, min=0, thresholds=[{"color": "transparent", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 14.4}],
         desc="1 = consuming budget exactly at the SLO rate; 14.4 = fast-burn page threshold")
    d.ts("Latency p95 by application vs 8 s target", [(f"histogram_quantile(0.95, sum by (le, service_name) (rate({DUR}{{{sel},{ROOT}}}[{R}]))) / 1000", "{{service_name}}")], "s", 12, y, 12, min=0,
         thresholds=[{"color": "transparent", "value": None}, {"color": "red", "value": 8}])
    y += 7
    d.row("Alerts and change events", y); y += 1
    d.table("Firing alerts", ['ALERTS{alertstate="firing"}'], 0, y, 12, 8,
            hide=("__name__", "alertstate", "Value", "job", "instance", "service_name"),
            rename={"alertname": "Alert", "severity": "Severity", "service": "Service"},
            desc="From the Prometheus rule groups in use-cases/*/alerts (instant)")
    d.state_timeline("Alert history", 'ALERTS{alertstate="firing"}', "{{alertname}}", 12, y, 12, 8)
    y += 8
    d.logs("Change events (scenario changes / deploys written as logs)", '{service_name=~"$service"} |= "scenario change"', 0, y, 12, 7)
    d.logs("Warnings and errors across the Space", '{service_name=~"$service"} | detected_level=~"warn|error"', 12, y, 12, 7)
    y += 7
    d.row("Dependencies", y); y += 1
    d.table("Models used by each application (calls)", [
        f'sum by (service_name, gen_ai_request_model) ({inc(CALLS, sel + ",gen_ai_operation_name=\"chat\"")})'], 0, y, 12, 7,
        rename={"service_name": "Application", "gen_ai_request_model": "Model", "Value": "calls"}, sort_by="calls",
        desc="Discovered from span attributes (the same idea as Omni's discovered topology)")
    d.table("Tools used by each application (calls)", [
        f'sum by (service_name, gen_ai_tool_name) ({inc(CALLS, sel + ",gen_ai_operation_name=\"execute_tool\"")})'], 12, y, 12, 7,
        rename={"service_name": "Application", "gen_ai_tool_name": "Tool", "Value": "calls"}, sort_by="calls")
    y += 7
    d.text("**Investigate:** [Agent fleet overview](/d/omni-agent-overview) · [Trace Explorer](/d/omni-trace-explorer) · [Session Explorer](/d/omni-session-explorer) · "
           "[Agent Topology](/d/omni-agent-topology) · [Evaluations](/d/omni-evaluations). Omni adds an AI investigation session (DevOps Agent) here; "
           "with this stack, follow the [runbooks](https://github.com/akashtalole/ai-observability/blob/main/docs/operations/runbooks.md) linked from each alert.", 0, y, 24, 3)
    d.write(OUT / "omni-space-health.json")


if __name__ == "__main__":
    space_health(); overview(); trace_explorer(); session_explorer(); topology(); evaluations()
    print("omni-style dashboards written to", OUT)
