#!/usr/bin/env python3
"""Offline scoring gate: run a golden set against a baseline and a candidate, score both, compare, gate.

    python examples/scoring/offline_eval.py                       # exit 0 = pass, 1 = regression
    python examples/scoring/offline_eval.py --candidate degraded  # shows a failing gate

Stdlib only. The 'systems' below are stubs so the script runs anywhere; replace `run_system` with a call to
your app (same inputs, pinned config). The scorers are deliberately simple: deterministic checks plus a cheap
overlap proxy for groundedness. In real use, add an LLM judge as one more scorer (see docs/scoring).

What it demonstrates: paired comparison on the SAME items, bootstrap confidence intervals, per-slice
(intent) protection, hard safety checks, and cost/latency gates alongside quality.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).parent
ABSTAIN = "I don't have enough information to answer that."

# ------------------------------------------------------------------ system under test (stubs)
def run_system(variant: str, item: dict, rng: random.Random) -> dict:
    """Return {answer, context, latency_s, cost_usd}. Candidate variants differ in quality/cost/latency."""
    quality = {"baseline": 0.88, "candidate": 0.90, "degraded": 0.62}[variant]
    answerable = item["answerable"]
    if not answerable:
        abstain_p = {"baseline": 0.85, "candidate": 0.9, "degraded": 0.4}[variant]
        answer = ABSTAIN if rng.random() < abstain_p else "Here is an answer I made up."
        return {"answer": answer, "context": "", "latency_s": rng.gauss(1.4, 0.2), "cost_usd": 0.004}
    keep = [w for w in item["must_include"] if rng.random() < quality]
    fluff = "Based on the documentation, " + " and ".join(keep) if keep else "Please contact support."
    ctx = " ".join(item["must_include"]) + " documentation"        # what retrieval returned (stub)
    cits = " [source: kb-12]" if rng.random() < (0.95 if variant != "degraded" else 0.6) else ""
    lat = rng.gauss({"baseline": 3.0, "candidate": 3.2, "degraded": 3.1}[variant], 0.5)
    cost = rng.gauss({"baseline": 0.0082, "candidate": 0.0088, "degraded": 0.0081}[variant], 0.0008)
    return {"answer": fluff + cits, "context": ctx, "latency_s": max(0.3, lat), "cost_usd": max(0.0005, cost)}

# ------------------------------------------------------------------ scorers (each returns 0..1)
def s_required_facts(item, out):             # deterministic: reference-based recall of required facts
    req = item["must_include"]
    return 1.0 if not req else sum(w.lower() in out["answer"].lower() for w in req) / len(req)

def s_citation_present(item, out):           # deterministic: answerable questions must cite a source
    return 1.0 if (not item["answerable"] or "[source:" in out["answer"]) else 0.0

def s_grounded_proxy(item, out):             # cheap proxy: share of answer words found in context (NOT a real judge)
    if not item["answerable"]:
        return 1.0
    words = [w.strip(".,[]:").lower() for w in out["answer"].split() if len(w) > 4]
    ctx = out["context"].lower()
    return sum(w in ctx or w in {"based", "documentation", "source", "contact", "support", "please"} for w in words) / max(1, len(words))

def s_abstains_correctly(item, out):         # deterministic: unanswerable -> abstain; answerable -> not abstain
    abstained = out["answer"].startswith("I don't have")
    return float(abstained != item["answerable"])

SCORERS = {"required_facts": s_required_facts, "citation_present": s_citation_present,
           "grounded_proxy": s_grounded_proxy, "abstains_correctly": s_abstains_correctly}

# ------------------------------------------------------------------ evaluation
def evaluate(variant: str, items: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for it in items:
        out = run_system(variant, it, rng)
        rows.append({"id": it["id"], "intent": it["intent"], **{k: f(it, out) for k, f in SCORERS.items()},
                     "latency_s": out["latency_s"], "cost_usd": out["cost_usd"]})
    return rows

def paired_bootstrap(base: list[float], cand: list[float], n=2000, seed=7):
    """95% CI of mean(candidate - baseline) over the same items."""
    rng = random.Random(seed)
    diffs = [c - b for b, c in zip(base, cand)]
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return statistics.fmean(diffs), means[int(0.025 * n)], means[int(0.975 * n)]

# gate: metric -> (absolute floor, max allowed drop vs baseline, drop is significant only if CI upper < -drop?)
GATES = {"required_facts": (0.80, 0.03), "citation_present": (0.90, 0.05), "grounded_proxy": (0.80, 0.03), "abstains_correctly": (0.80, 0.05)}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="candidate", choices=["candidate", "degraded"])
    ap.add_argument("--golden", default=str(HERE / "golden.jsonl"))
    ap.add_argument("--repeats", type=int, default=20, help="re-run stochastic systems this many times per item")
    a = ap.parse_args()
    items = [json.loads(l) for l in open(a.golden) if l.strip()]
    items = items * a.repeats                                 # stochastic systems: repeat to reduce variance
    base, cand = evaluate("baseline", items, seed=1), evaluate(a.candidate, items, seed=2)
    failures = []
    print(f"{len(items)} scored runs ({len(items)//a.repeats} items x {a.repeats}); candidate={a.candidate}\n")
    print(f"{'metric':20s} {'baseline':>9s} {'candidate':>9s} {'delta':>8s}   95% CI of delta        gate")
    for m, (floor, max_drop) in GATES.items():
        b, c = [r[m] for r in base], [r[m] for r in cand]
        d, lo, hi = paired_bootstrap(b, c)
        cm = statistics.fmean(c)
        bad_floor = cm < floor
        bad_drop = hi < -max_drop                              # significantly worse by more than the allowed drop
        status = "FAIL" if (bad_floor or bad_drop) else "ok"
        if status == "FAIL":
            failures.append(f"{m}: candidate {cm:.3f} (floor {floor}); delta {d:+.3f} CI [{lo:+.3f},{hi:+.3f}]")
        print(f"{m:20s} {statistics.fmean(b):9.3f} {cm:9.3f} {d:+8.3f}   [{lo:+.3f}, {hi:+.3f}]   {status}")
    # slice protection: no intent may drop by more than 0.10 on required_facts
    for intent in sorted({r["intent"] for r in base}):
        b = statistics.fmean(r["required_facts"] for r in base if r["intent"] == intent)
        c = statistics.fmean(r["required_facts"] for r in cand if r["intent"] == intent)
        if c < b - 0.10:
            failures.append(f"slice {intent}: required_facts {b:.2f} -> {c:.2f}")
    # operational gates evaluated alongside quality
    lat_b, lat_c = statistics.quantiles([r["latency_s"] for r in base], n=20)[18], statistics.quantiles([r["latency_s"] for r in cand], n=20)[18]
    cost_b, cost_c = statistics.fmean(r["cost_usd"] for r in base), statistics.fmean(r["cost_usd"] for r in cand)
    print(f"\nlatency p95   {lat_b:.2f}s -> {lat_c:.2f}s   (gate: <= 1.10x)\ncost/request  ${cost_b:.4f} -> ${cost_c:.4f}   (gate: <= 1.15x)")
    if lat_c > 1.10 * lat_b: failures.append(f"latency p95 {lat_c:.2f}s > 1.10x baseline")
    if cost_c > 1.15 * cost_b: failures.append(f"cost {cost_c:.4f} > 1.15x baseline")
    print("\nGATE: " + ("PASS" if not failures else "FAIL\n  - " + "\n  - ".join(failures)))
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
