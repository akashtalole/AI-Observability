#!/usr/bin/env python3
"""Simulated multi-agent system (supervisor + researcher + analyst + writer + reviewer) instrumented with OpenTelemetry.

    python use-cases/multi-agent/app/agent_app.py --rps 0.6 --cycle 240      # against the stack
    python use-cases/multi-agent/app/agent_app.py --console --duration 15    # print telemetry only

Scenarios (rotate with --cycle N, or pin with --scenario):
    normal -> tool-flaky -> runaway-loop -> cost-spike -> injection -> slow-tool

Trace shape (OTel GenAI agent conventions): one trace per task
    invoke_agent supervisor
      ├─ chat <model>                      (planning)
      ├─ invoke_agent researcher           (handoff)
      │    ├─ chat <model> / execute_tool search / execute_tool web_fetch ...
      ├─ invoke_agent analyst / writer / reviewer
      └─ ...
Telemetry carries IDs, counts, scores, tool names and versions - never prompts or tool payload text.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from telemetry import setup  # noqa: E402

from opentelemetry.trace import SpanKind, Status, StatusCode  # noqa: E402

APP = "research-agents"
PRICES = {"large-model": (3.00, 15.00), "small-model": (0.25, 1.25)}
MAX_STEPS, BUDGET_USD, TIMEOUT_S = 25, 0.15, 90
TASK_TYPES = ["market-brief", "data-analysis", "doc-summary"]
TOOLS = {  # name: (base latency s, side effect)
    "search": (0.35, "read"), "kb_lookup": (0.15, "read"), "web_fetch": (0.6, "read"),
    "run_code": (0.9, "exec"), "send_email": (0.3, "write"),
}


@dataclass
class Scenario:
    name: str
    tool_error: float = 0.03
    tool_lat_mult: float = 1.0
    loop_rate: float = 0.0        # probability a task enters a repeated-call loop
    ctx_mult: float = 1.0
    reject_rate: float = 0.12     # reviewer rejection -> revision cycle
    inject_rate: float = 0.0      # tool output carries indirect prompt injection
    description: str = ""


SCENARIOS = {s.name: s for s in [
    Scenario("normal", description="healthy baseline"),
    Scenario("tool-flaky", tool_error=0.35, description="search/fetch dependency failing -> tool error + retries + failed tasks"),
    Scenario("runaway-loop", loop_rate=0.45, description="agents repeat identical tool calls -> loop detector, cost per task"),
    Scenario("cost-spike", ctx_mult=4.0, reject_rate=0.4, description="context bloat + revision cycles -> budget exceeded"),
    Scenario("injection", inject_rate=0.25, description="tool outputs carry indirect prompt injection -> guardrail + approvals denied"),
    Scenario("slow-tool", tool_lat_mult=6.0, description="tool latency regression -> task duration / timeouts"),
]}
CURRENT = {"s": SCENARIOS["normal"]}


class M:
    def __init__(self, meter):
        c, h = meter.create_counter, meter.create_histogram
        self.tasks = c("agent.tasks", description="Tasks by outcome")
        self.task_dur = h("agent.task.duration", unit="s")
        self.task_steps = h("agent.task.steps", description="LLM + tool steps per task")
        self.task_cost = h("agent.task.cost", description="USD per task")
        self.cost = c("agent.cost.usd")
        self.llm_calls = c("agent.llm.calls")
        self.llm_dur = h("agent.llm.duration", unit="s")
        self.tokens = c("agent.tokens")
        self.tool_calls = c("agent.tool.calls")
        self.tool_dur = h("agent.tool.duration", unit="s")
        self.handoffs = c("agent.handoffs")
        self.loops = c("agent.loops.detected")
        self.terminated = c("agent.terminations", description="Abnormal task terminations by reason")
        self.approvals = c("agent.approvals", description="Human-approval decisions for write/destructive tools")
        self.guard = c("agent.guardrail.events")
        self.revisions = c("agent.plan.revisions")
        self.active = meter.create_up_down_counter("agent.active_tasks")
        # Pre-create rare series at 0: Prometheus increase() cannot see a series' first increment.
        for r in ("max_steps", "budget_exceeded", "timeout", "loop"):
            self.terminated.add(0, {"reason": r})
        for d in ("granted", "denied"):
            self.approvals.add(0, {"agent": "supervisor", "tool": "send_email", "decision": d})
        for a in ("blocked", "missed"):
            self.guard.add(0, {"agent": "researcher", "category": "indirect_injection", "action": a})


class Task:
    def __init__(self, ttype: str):
        self.type, self.steps, self.cost, self.tokens = ttype, 0, 0.0, 0
        self.start = time.time()
        self.seen: dict[str, int] = {}
        self.last_tool: tuple[str, str] | None = None


class Stop(Exception):
    def __init__(self, reason: str):
        super().__init__(reason); self.reason = reason


def jitter(b: float, s: float = 0.3) -> float:
    return max(0.005, random.gauss(b, b * s))


def check_limits(task: Task) -> None:
    if task.steps >= MAX_STEPS:
        raise Stop("max_steps")
    if task.cost >= BUDGET_USD:
        raise Stop("budget_exceeded")
    if time.time() - task.start > TIMEOUT_S:
        raise Stop("timeout")


def llm(t, m, task: Task, agent: str, purpose: str, model: str = "large-model") -> None:
    check_limits(task)
    sc = CURRENT["s"]
    in_tok = int(random.gauss(900, 200) * sc.ctx_mult * (1 + 0.12 * task.steps))   # context grows with every step
    out_tok = int(random.gauss(220, 60))
    with t.tracer.start_as_current_span(f"chat {model}", kind=SpanKind.CLIENT, attributes={
            "gen_ai.operation.name": "chat", "gen_ai.provider.name": "demo-provider", "gen_ai.request.model": model,
            "gen_ai.agent.name": agent, "app.step.purpose": purpose, "app.step.index": task.steps}) as sp:
        d = jitter(0.35 + out_tok / 140.0)
        time.sleep(d)
        sp.set_attributes({"gen_ai.usage.input_tokens": in_tok, "gen_ai.usage.output_tokens": out_tok,
                           "gen_ai.response.model": model, "gen_ai.response.finish_reasons": ["tool_calls" if purpose == "act" else "stop"]})
    usd = (in_tok * PRICES[model][0] + out_tok * PRICES[model][1]) / 1e6
    task.steps += 1; task.cost += usd; task.tokens += in_tok + out_tok
    a = {"agent": agent, "model": model}
    m.llm_calls.add(1, a); m.llm_dur.record(d, a); m.cost.add(usd, a)
    m.tokens.add(in_tok, {**a, "direction": "input"}); m.tokens.add(out_tok, {**a, "direction": "output"})


def tool(t, m, task: Task, agent: str, name: str, args_key: str) -> bool:
    """Execute a tool; returns True on success. Detects repeated identical calls (loops)."""
    check_limits(task)
    sc = CURRENT["s"]
    key = f"{name}:{hashlib.md5(args_key.encode()).hexdigest()[:6]}"          # hash of args, never the args themselves
    task.seen[key] = task.seen.get(key, 0) + 1
    base, effect = TOOLS[name]
    with t.tracer.start_as_current_span(f"execute_tool {name}", kind=SpanKind.CLIENT, attributes={
            "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name, "gen_ai.agent.name": agent,
            "tool.side_effect": effect, "tool.args_hash": key, "app.step.index": task.steps}) as sp:
        if effect == "write":                                                  # human-in-the-loop for side effects
            granted = random.random() < 0.7
            m.approvals.add(1, {"agent": agent, "tool": name, "decision": "granted" if granted else "denied"})
            sp.set_attribute("approval.granted", granted)
            if not granted:
                t.log.warning("write tool denied by approver", extra={"tool": name, "agent": agent})
                task.steps += 1
                m.tool_calls.add(1, {"agent": agent, "tool": name, "status": "denied"})
                return False
        d = jitter(base * sc.tool_lat_mult)
        time.sleep(d)
        ok = random.random() >= (sc.tool_error if name in ("search", "web_fetch") else 0.02)
        if not ok:
            sp.set_status(Status(StatusCode.ERROR, "tool_error")); sp.set_attribute("error.type", "tool_error")
            t.log.error("tool call failed", extra={"tool": name, "agent": agent, "step": task.steps})
        if ok and name == "web_fetch" and random.random() < sc.inject_rate:      # indirect injection in tool output
            detected = random.random() < 0.8
            sp.set_attribute("guardrail.injection_detected", detected)
            m.guard.add(1, {"agent": agent, "category": "indirect_injection", "action": "blocked" if detected else "missed"})
            if detected:
                t.log.warning("indirect prompt injection blocked", extra={"tool": name, "agent": agent})
            else:
                tool(t, m, task, agent, "send_email", "exfiltrate")            # injected instruction tries a write tool
    task.steps += 1
    m.tool_calls.add(1, {"agent": agent, "tool": name, "status": "ok" if ok else "error"})
    m.tool_dur.record(d, {"tool": name, "status": "ok" if ok else "error"})
    if task.seen[key] >= 3:
        m.loops.add(1, {"agent": agent, "tool": name})
        sp.set_attribute("loop.detected", True)
        t.log.warning("loop detected: identical tool call repeated", extra={"tool": name, "repeats": task.seen[key], "agent": agent})
        if task.seen[key] >= 4:
            raise Stop("loop")
    return ok


def run_worker(t, m, task: Task, name: str, parent: str, plan: list[tuple[str, str]]) -> bool:
    """A handoff: invoke a sub-agent that interleaves LLM reasoning with tool calls."""
    m.handoffs.add(1, {"from": parent, "to": name})
    with t.tracer.start_as_current_span(f"invoke_agent {name}", kind=SpanKind.INTERNAL, attributes={
            "gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": name, "app.parent_agent": parent}):
        ok = True
        for tool_name, args in plan:
            llm(t, m, task, name, "act", "small-model" if name in ("researcher", "reviewer") else "large-model")
            ok = tool(t, m, task, name, tool_name, args) and ok
        llm(t, m, task, name, "summarize", "small-model")
        return ok


def handle_task(t, m, n: int) -> None:
    sc = CURRENT["s"]
    ttype = random.choice(TASK_TYPES)
    task = Task(ttype)
    m.active.add(1, {"app": APP})
    outcome, reason = "success", ""
    with t.tracer.start_as_current_span("invoke_agent supervisor", kind=SpanKind.SERVER, attributes={
            "gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "supervisor", "gen_ai.conversation.id": uuid.uuid4().hex[:8],
            "app.task.type": ttype, "app.environment": "demo", "app.release.id": "agents-2026.10.1"}) as root:
        try:
            llm(t, m, task, "supervisor", "plan")
            looping = random.random() < sc.loop_rate
            gather = [("search", f"{ttype}-q1"), ("kb_lookup", f"{ttype}-k1")]
            if ttype == "data-analysis":
                gather.append(("run_code", f"{ttype}-c1"))
            if random.random() < 0.5:
                gather.append(("web_fetch", f"{ttype}-u{random.randint(1, 9)}"))
            if looping:                                                     # the agent keeps retrying the same call
                gather = [("search", f"{ttype}-same-query")] * 6
            ok = run_worker(t, m, task, "researcher", "supervisor", gather)
            if not ok:
                m.revisions.add(1, {"agent": "supervisor", "cause": "tool_failure"})
                llm(t, m, task, "supervisor", "replan")
                ok = run_worker(t, m, task, "researcher", "supervisor", [("search", f"{ttype}-q2")])
            if not ok:
                outcome, reason = "failed", "tool_failure"                 # research failed twice: give up instead of drafting from nothing
            else:
                if ttype == "data-analysis":
                    run_worker(t, m, task, "analyst", "supervisor", [("run_code", f"{ttype}-c2")])
                for rev in range(4):                                        # draft -> review -> (revise)
                    run_worker(t, m, task, "writer", "supervisor", [("kb_lookup", f"{ttype}-style-{rev}")])   # args differ per revision: not a loop
                    run_worker(t, m, task, "reviewer", "supervisor", [])
                    if random.random() >= sc.reject_rate:
                        break
                    m.revisions.add(1, {"agent": "reviewer", "cause": "rejected"})
                    if rev == 3:
                        outcome, reason = "failed", "review_rejected"
            if random.random() < 0.02:
                tool(t, m, task, "supervisor", "send_email", f"{ttype}-notify")
        except Stop as s:
            outcome, reason = "abandoned", s.reason
            m.terminated.add(1, {"reason": s.reason})
            t.log.warning("task terminated", extra={"reason": s.reason, "steps": task.steps, "cost_usd": round(task.cost, 4)})
        except Exception as exc:  # noqa: BLE001
            outcome, reason = "failed", "exception"
            root.record_exception(exc); root.set_status(Status(StatusCode.ERROR, str(exc)))
        finally:
            elapsed = time.time() - task.start
            root.set_attributes({"app.task.outcome": outcome, "app.task.steps": task.steps, "cost.usd.total": task.cost,
                                 "app.task.tokens": task.tokens, "app.task.termination_reason": reason})
            if outcome != "success":
                root.set_attribute("eval.flagged", True)
                if outcome == "abandoned":
                    root.set_status(Status(StatusCode.ERROR, reason))
            d = {"task_type": ttype}
            m.tasks.add(1, {**d, "outcome": outcome})
            m.task_dur.record(elapsed, {**d, "outcome": outcome})
            m.task_steps.record(task.steps, d)
            m.task_cost.record(task.cost, d)
            m.active.add(-1, {"app": APP})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rps", type=float, default=0.6, help="average tasks per second")
    ap.add_argument("--duration", type=float, default=0)
    ap.add_argument("--scenario", choices=SCENARIOS, default="normal")
    ap.add_argument("--cycle", type=float, default=0, help="rotate scenarios every N seconds")
    ap.add_argument("--console", action="store_true")
    a = ap.parse_args()

    t = setup(APP, console=a.console)
    m = M(t.meter)
    CURRENT["s"] = SCENARIOS[a.scenario]
    order = itertools.cycle([x for f in SCENARIOS.values() if f.name != "normal" for x in (SCENARIOS["normal"], f)])   # healthy phase between faults
    if a.cycle:
        CURRENT["s"] = next(order)
    print(f"[{APP}] scenario={CURRENT['s'].name} ({CURRENT['s'].description})", flush=True)
    pool = ThreadPoolExecutor(max_workers=48)
    start = last = time.time()
    n = 0
    try:
        while not a.duration or time.time() - start < a.duration:
            if a.cycle and time.time() - last >= a.cycle:
                CURRENT["s"] = next(order); last = time.time()
                t.log.warning(f"scenario change: {CURRENT['s'].name}", extra={"scenario": CURRENT["s"].name})
                print(f"[{APP}] scenario -> {CURRENT['s'].name}: {CURRENT['s'].description}", flush=True)
            n += 1
            pool.submit(handle_task, t, m, n)
            time.sleep(random.expovariate(a.rps))
    except KeyboardInterrupt:
        pass
    finally:
        pool.shutdown(wait=True, cancel_futures=True); time.sleep(0.5); t.shutdown()


if __name__ == "__main__":
    main()
