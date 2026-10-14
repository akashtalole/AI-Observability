#!/usr/bin/env python3
"""Simulated customer-support chatbot (multi-turn sessions) instrumented with OpenTelemetry.

    python use-cases/chatbot/app/chatbot_app.py --rps 0.5 --cycle 240      # against the stack
    python use-cases/chatbot/app/chatbot_app.py --console --duration 15    # print telemetry only

Scenarios: normal -> slow-model -> hallucinating -> over-refusal -> long-context -> outage

Conversation-level signals: containment (resolved without a human), escalation, abandonment, turns to resolution,
intent mix, fallback (unsupported intent), refusal vs over-refusal, context-window utilization, streaming stalls.
No message text is recorded - only lengths, intents, scores and IDs.
"""
from __future__ import annotations

import argparse
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

APP = "support-chatbot"
PRICES = {"chat-model": (0.60, 2.40)}
CONTEXT_WINDOW = 16000
INTENTS = {  # intent: (weight, base resolve probability)
    "billing": (25, 0.80), "shipping": (22, 0.88), "returns": (18, 0.78), "account": (14, 0.85),
    "tech-support": (13, 0.62), "smalltalk": (4, 0.97), "out-of-scope": (4, 0.0),
}
CHANNELS = ["web", "mobile", "whatsapp"]


@dataclass
class Scenario:
    name: str
    llm_mult: float = 1.0
    error_rate: float = 0.005
    quality_shift: float = 0.0     # shifts resolution + satisfaction
    refusal_rate: float = 0.01     # guardrail refusals (over-refusal when high)
    ctx_mult: float = 1.0
    stall_rate: float = 0.01
    description: str = ""


SCENARIOS = {s.name: s for s in [
    Scenario("normal", description="healthy baseline"),
    Scenario("slow-model", llm_mult=3.5, stall_rate=0.08, description="model latency + streaming stalls -> TTFT / abandonment"),
    Scenario("hallucinating", quality_shift=-0.40, description="quality regression -> escalations, thumbs-down, low groundedness"),
    Scenario("over-refusal", refusal_rate=0.22, description="guardrail too strict -> refusals, lower containment"),
    Scenario("long-context", ctx_mult=5.0, description="history bloat -> context utilization, cost per conversation"),
    Scenario("outage", error_rate=0.35, llm_mult=1.5, description="provider errors -> failed turns, abandonment"),
]}
CURRENT = {"s": SCENARIOS["normal"]}


class M:
    def __init__(self, meter):
        c, h = meter.create_counter, meter.create_histogram
        self.turns = c("chat.turns", description="Turns by status")
        self.turn_dur = h("chat.turn.duration", unit="s")
        self.ttft = h("chat.ttft", unit="s")
        self.tokens = c("chat.tokens")
        self.cost = c("chat.cost.usd")
        self.sessions = c("chat.sessions", description="Sessions by final outcome")
        self.session_turns = h("chat.session.turns", description="Turns per session")
        self.intents = c("chat.intents")
        self.fallback = c("chat.fallbacks", description="Unsupported-intent fallbacks")
        self.feedback = c("chat.feedback")
        self.guard = c("chat.guardrail.events")
        self.util = h("chat.context.utilization", description="Context window utilization (0..1)")
        self.truncations = c("chat.context.truncations")
        self.stalls = c("chat.stream.stalls")
        self.score = h("chat.eval.score", description="Conversation-level eval scores")
        self.active = meter.create_up_down_counter("chat.active_sessions")
        # Pre-create rare series at 0: Prometheus increase() cannot see a series' first increment.
        self.truncations.add(0, {"app": APP}); self.stalls.add(0, {"app": APP}); self.fallback.add(0, {"app": APP})


def jitter(b, s=0.3):
    return max(0.005, random.gauss(b, b * s))


def turn(t, m, session: dict, intent: str, n: int) -> str:
    """One user turn. Returns status: ok | refused | error | fallback."""
    sc = CURRENT["s"]
    t0 = time.perf_counter()
    in_ctx = int(random.gauss(500, 120) * sc.ctx_mult) + 350 * n * (sc.ctx_mult > 1) + 250 * n     # history grows per turn
    util = min(1.0, in_ctx / CONTEXT_WINDOW)
    status = "ok"
    with t.tracer.start_as_current_span("chat.turn", kind=SpanKind.SERVER, attributes={
            "gen_ai.conversation.id": session["id"], "app.turn.index": n, "app.intent": intent, "app.channel": session["channel"],
            "app.environment": "demo", "app.prompt.version": "v12", "app.release.id": "chat-2026.10.2",
            "app.user.message.length": random.randint(10, 300)}) as sp:
        m.intents.add(1, {"intent": intent, "channel": session["channel"]})
        m.util.record(util, {"app": APP})
        if util >= 0.95:
            m.truncations.add(1, {"app": APP}); sp.set_attribute("context.truncated", True)
        try:
            if random.random() < sc.refusal_rate:                       # guardrail refuses (policy or false positive)
                m.guard.add(1, {"category": "policy", "action": "refused", "intent": intent})
                t.log.warning("response refused by guardrail", extra={"intent": intent, "turn": n})
                sp.set_attribute("guardrail.refused", True)
                return "refused"
            if intent == "out-of-scope":
                m.fallback.add(1, {"app": APP}); sp.set_attribute("app.fallback", True)
                time.sleep(jitter(0.15))
                return "fallback"
            with t.tracer.start_as_current_span("chat chat-model", kind=SpanKind.CLIENT, attributes={
                    "gen_ai.operation.name": "chat", "gen_ai.request.model": "chat-model", "gen_ai.provider.name": "demo-provider"}) as ls:
                if random.random() < sc.error_rate:
                    time.sleep(jitter(0.3))
                    ls.set_status(Status(StatusCode.ERROR, "upstream_error")); ls.set_attribute("error.type", "upstream_error")
                    t.log.error("model call failed", extra={"intent": intent, "turn": n})
                    raise RuntimeError("upstream_error")
                out_tok = int(random.gauss(180, 50))
                ttft = jitter(0.45 * sc.llm_mult)
                time.sleep(ttft)
                if random.random() < sc.stall_rate:                     # stream pauses mid-answer
                    m.stalls.add(1, {"app": APP}); time.sleep(jitter(2.5)); sp.set_attribute("stream.stalled", True)
                time.sleep(out_tok / jitter(100 / min(sc.llm_mult, 2.5), 0.15))
                ls.set_attributes({"gen_ai.usage.input_tokens": in_ctx, "gen_ai.usage.output_tokens": out_tok,
                                   "gen_ai.response.model": "chat-model", "app.ttft_ms": round(ttft * 1000, 1)})
            usd = (in_ctx * PRICES["chat-model"][0] + out_tok * PRICES["chat-model"][1]) / 1e6
            session["cost"] += usd
            m.tokens.add(in_ctx, {"direction": "input", "intent": intent}); m.tokens.add(out_tok, {"direction": "output", "intent": intent})
            m.cost.add(usd, {"intent": intent})
            m.ttft.record(ttft, {"channel": session["channel"]})
            sp.set_attribute("cost.usd.total", usd)
            return "ok"
        except RuntimeError as exc:
            status = "error"
            sp.record_exception(exc); sp.set_status(Status(StatusCode.ERROR, str(exc)))
            return "error"
        finally:
            d = time.perf_counter() - t0
            m.turn_dur.record(d, {"intent": intent})
            m.turns.add(1, {"intent": intent, "status": status if status == "error" else "ok", "channel": session["channel"]})


def session(t, m, n: int) -> None:
    """A conversation. Its fate (resolved or not) is decided by intent difficulty and scenario quality; refusals and errors can end it early."""
    sc = CURRENT["s"]
    s = {"id": f"sess-{uuid.uuid4().hex[:8]}", "channel": random.choice(CHANNELS), "cost": 0.0}
    intent = random.choices(list(INTENTS), [v[0] for v in INTENTS.values()])[0]
    solvable = random.random() < max(0.0, INTENTS[intent][1] + sc.quality_shift)
    n_turns = random.randint(1, 4) if solvable else random.randint(2, 6)
    outcome, turns = None, 0
    m.active.add(1, {"app": APP})
    try:
        while turns < n_turns:
            turns += 1
            st = turn(t, m, s, intent, turns)
            if st == "error" and random.random() < 0.5:
                outcome = "abandoned"; break                       # user gives up after a failed turn
            if st == "fallback":
                outcome = "escalated"; break                       # unsupported intent -> human
            if st == "refused":
                solvable = solvable and random.random() > 0.5      # a refusal often ruins an otherwise solvable conversation
                if random.random() < 0.3:
                    outcome = "escalated"; break
            time.sleep(jitter(1.0))                                # user think time
        if outcome is None:
            outcome = "resolved" if solvable else ("escalated" if random.random() < 0.6 else "abandoned")
        if outcome == "escalated":
            t.log.info("escalated to human agent", extra={"intent": intent, "turns": turns})
        m.sessions.add(1, {"outcome": outcome, "intent": intent, "channel": s["channel"]})
        m.session_turns.record(turns, {"outcome": outcome})
        if random.random() < 0.15:
            up = outcome == "resolved" and random.random() < 0.92
            m.feedback.add(1, {"rating": "up" if up else "down", "intent": intent})
        if random.random() < 0.35:                                 # sampled conversation-level judge
            goal = 0.9 if outcome == "resolved" else 0.5
            m.score.record(min(1, max(0, random.gauss(goal + sc.quality_shift * 0.3, 0.07))), {"metric": "goal_completion"})
            m.score.record(min(1, max(0, random.gauss(0.93 - (0.15 if sc.refusal_rate > 0.1 else 0), 0.05))), {"metric": "policy_compliance"})
    finally:
        m.active.add(-1, {"app": APP})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rps", type=float, default=0.5, help="average new sessions per second")
    ap.add_argument("--duration", type=float, default=0)
    ap.add_argument("--scenario", choices=SCENARIOS, default="normal")
    ap.add_argument("--cycle", type=float, default=0)
    ap.add_argument("--console", action="store_true")
    a = ap.parse_args()
    t = setup(APP, console=a.console)
    m = M(t.meter)
    CURRENT["s"] = SCENARIOS[a.scenario]
    order = itertools.cycle([x for f in SCENARIOS.values() if f.name != "normal" for x in (SCENARIOS["normal"], f)])   # healthy phase between faults
    if a.cycle:
        CURRENT["s"] = next(order)
    print(f"[{APP}] scenario={CURRENT['s'].name} ({CURRENT['s'].description})", flush=True)
    pool = ThreadPoolExecutor(max_workers=96)
    start = last = time.time()
    n = 0
    try:
        while not a.duration or time.time() - start < a.duration:
            if a.cycle and time.time() - last >= a.cycle:
                CURRENT["s"] = next(order); last = time.time()
                t.log.warning(f"scenario change: {CURRENT['s'].name}", extra={"scenario": CURRENT["s"].name})
                print(f"[{APP}] scenario -> {CURRENT['s'].name}: {CURRENT['s'].description}", flush=True)
            n += 1
            pool.submit(session, t, m, n)
            time.sleep(random.expovariate(a.rps))
    except KeyboardInterrupt:
        pass
    finally:
        pool.shutdown(wait=True, cancel_futures=True); time.sleep(0.5); t.shutdown()


if __name__ == "__main__":
    main()
