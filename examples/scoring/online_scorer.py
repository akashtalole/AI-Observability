#!/usr/bin/env python3
"""Online scoring worker: stratified sampling, async scoring off the request path, versioned score write-back,
and sample-size-aware rolling statistics.

    python examples/scoring/online_scorer.py --requests 600

Stdlib only. Requests are simulated; in production the producer is your trace stream (OTel span processor,
log tail, or message queue) and `write_score` records an OTel histogram (see use-cases/rag/app/rag_app.py) and/or
a row in a score table keyed by trace_id.

Demonstrates: cheap deterministic checks on 100% of traffic, an expensive judge on a stratified sample + all
flagged requests, judge versioning, a bounded queue that sheds load instead of blocking, and Wilson/normal CIs so a
dip on thin data is not mistaken for a regression.
"""
from __future__ import annotations

import argparse
import math
import queue
import random
import statistics
import threading
import time
from collections import defaultdict

JUDGE_VERSION = "judge-v3"
SAMPLE_RATES = {"high-risk": 0.30, "standard": 0.05}        # stratified by risk tier
ALWAYS = {"thumbs_down", "guardrail_hit", "empty_retrieval", "slow", "costly"}   # flagged -> always judge


def cheap_checks(req: dict) -> dict:
    """Deterministic, ~free, run on 100% of traffic."""
    return {"has_citation": float(req["has_citation"]), "schema_valid": float(req["schema_valid"]),
            "length_ok": float(20 <= req["answer_len"] <= 2500)}


def should_judge(req: dict, rng: random.Random) -> tuple[bool, str]:
    flagged = ALWAYS & set(req["flags"])
    if flagged:
        return True, "flagged:" + sorted(flagged)[0]
    return (rng.random() < SAMPLE_RATES[req["tier"]], "sampled")


def judge(req: dict, rng: random.Random) -> dict:
    """Stand-in for an LLM judge (groundedness, relevance). Replace with a pinned model + versioned rubric."""
    time.sleep(0.002)
    g = min(1, max(0, rng.gauss(0.88 if "empty_retrieval" not in req["flags"] else 0.45, 0.08)))
    return {"groundedness": g, "answer_relevance": min(1, max(0, rng.gauss(0.9, 0.06)))}


def mean_ci(xs: list[float]) -> tuple[float, float]:
    """mean and 95% half-width (normal approx.)."""
    if len(xs) < 2:
        return (xs[0] if xs else float("nan")), float("nan")
    return statistics.fmean(xs), 1.96 * statistics.stdev(xs) / math.sqrt(len(xs))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=600)
    ap.add_argument("--queue-size", type=int, default=50)
    a = ap.parse_args()
    rng = random.Random(3)
    q: queue.Queue = queue.Queue(maxsize=a.queue_size)
    scores: dict[str, list[tuple[str, float]]] = defaultdict(list)   # metric -> [(stratum, score)]
    cheap_all = defaultdict(list)
    stats = {"seen": 0, "judged": 0, "shed": 0}
    lock, stop = threading.Lock(), threading.Event()

    def worker():
        wrng = random.Random(99)
        while not stop.is_set() or not q.empty():
            try:
                req, why = q.get(timeout=0.1)
            except queue.Empty:
                continue
            res = judge(req, wrng)
            with lock:                                            # write_score(trace_id, metric, value, judge_version, stratum)
                for m, v in res.items():
                    scores[m].append((why.split(":")[0] + "/" + req["tier"], v))
                stats["judged"] += 1

    t = threading.Thread(target=worker); t.start()
    for i in range(a.requests):                                  # --- request path: never blocks on the judge
        flags = [f for f, p in (("thumbs_down", .03), ("guardrail_hit", .01), ("empty_retrieval", .04), ("slow", .03)) if rng.random() < p]
        req = {"id": f"t{i}", "tier": "high-risk" if rng.random() < 0.2 else "standard", "flags": flags,
               "has_citation": rng.random() < 0.96, "schema_valid": rng.random() < 0.995, "answer_len": int(rng.gauss(400, 150))}
        for k, v in cheap_checks(req).items():
            cheap_all[k].append(v)                                # 100% coverage
        stats["seen"] += 1
        ok, why = should_judge(req, rng)
        if ok:
            try:
                q.put_nowait((req, why))
            except queue.Full:                                    # shed load; track it - never block or fail the user request
                stats["shed"] += 1
    stop.set(); t.join()

    print(f"requests={stats['seen']}  judged={stats['judged']} ({stats['judged']/stats['seen']:.1%})  shed={stats['shed']}  judge={JUDGE_VERSION}\n")
    print("cheap checks (100% coverage):")
    for k, v in cheap_all.items():
        m, ci = mean_ci(v); print(f"  {k:14s} {m:.3f} +/- {ci:.3f}  (n={len(v)})")
    print("\njudge scores (sampled + flagged) - always read the score with its n:")
    for m, rows in scores.items():
        xs = [s for _, s in rows]; mean, ci = mean_ci(xs)
        print(f"  {m:17s} {mean:.3f} +/- {ci:.3f}  (n={len(xs)})")
        by = defaultdict(list)
        for stratum, s in rows: by[stratum].append(s)
        for stratum, v in sorted(by.items()):
            mm, cc = mean_ci(v); print(f"      {stratum:22s} {mm:.3f} +/- {cc:.3f}  (n={len(v)})")
    print("\nNote: flagged traces are over-represented in the judged set, so the pooled mean is biased low; "
          "report the random-sample slice (sampled/*) as the unbiased estimate and the flagged slice as a triage queue.")


if __name__ == "__main__":
    main()
