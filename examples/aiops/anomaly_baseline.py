#!/usr/bin/env python3
"""Statistics first: compare detectors on an hourly metric with daily/weekly seasonality and injected incidents.

    python examples/aiops/anomaly_baseline.py

Stdlib only. A cost-per-request (or latency, or quality) series has a daily and weekly rhythm. A static threshold either
pages every busy afternoon or misses real incidents. A seasonal baseline (same hour-of-week, previous weeks) plus a robust
spread estimate (MAD) and CUSUM catch level shifts and slow drift with far fewer false alarms: no model training, no LLM.
Use this as the baseline any 'AI for observability' feature has to beat.
"""
from __future__ import annotations

import math
import random
import statistics

H = 24 * 7 * 8                       # 8 weeks hourly
rng = random.Random(11)

def seasonal(t: int) -> float:
    hod, dow = t % 24, (t // 24) % 7
    day = 0.5 + 0.5 * math.sin((hod - 9) / 24 * 2 * math.pi + 1.2)       # busy afternoons
    week = 0.55 if dow >= 5 else 1.0
    return 100 * (0.6 + 0.5 * day) * (0.8 + 0.2 * week)

INCIDENTS = [  # (start_hour, kind, duration, magnitude)
    (24 * 7 * 5 + 30, "level_shift", 36, 0.20),     # +20% for 36 h (bad prompt / context bloat)
    (24 * 7 * 6 + 60, "spike", 4, 0.60),            # short +60% burst (retry storm)
    (24 * 7 * 7 + 10, "drift", 96, 0.30),           # slow ramp to +30% over 4 days (index drift)
]
series = [seasonal(t) * (1 + rng.gauss(0, 0.04)) for t in range(H)]
truth = set()
for start, kind, dur, mag in INCIDENTS:
    for i in range(dur):
        f = mag * (i / dur if kind == "drift" else 1.0)
        series[start + i] *= 1 + f
        truth.add(start + i)

def static(x, thr):                  # naive: fixed threshold
    return [v > thr for v in x]

def seasonal_mad(x, weeks=4, z_thr=5.0, k_consecutive=3):
    flags, run = [False] * len(x), 0
    resid = [0.0] * len(x)
    for t in range(24 * 7 * weeks, len(x)):
        base = statistics.median(x[t - 24 * 7 * w] for w in range(1, weeks + 1))
        resid[t] = (x[t] - base) / base
        window = resid[max(24 * 7 * weeks, t - 24 * 7): t] or [0.0]
        med = statistics.median(window)
        mad = statistics.median(abs(r - med) for r in window) * 1.4826 or 1e-6
        z = (resid[t] - med) / mad
        run = run + 1 if z > z_thr else 0
        flags[t] = run >= k_consecutive
    return flags

def cusum(x, weeks=4, k=1.0, h=12.0):
    flags, s = [False] * len(x), 0.0
    for t in range(24 * 7 * weeks, len(x)):
        base = statistics.median(x[t - 24 * 7 * w] for w in range(1, weeks + 1))
        r = (x[t] - base) / base
        s = max(0.0, s + (r / 0.05) - k)                  # 0.05 ~ normal noise scale; k = allowance, h = decision threshold
        flags[t] = s > h
    return flags

def evaluate(name, flags):
    start0 = 24 * 7 * 4
    alerts, fa = [], 0
    in_alert = False
    for t in range(start0, H):                            # group consecutive flags into alert events
        if flags[t] and not in_alert:
            alerts.append(t); in_alert = True
        elif not flags[t]:
            in_alert = False
    detected, delays = 0, []
    for start, kind, dur, mag in INCIDENTS:
        hit = [a for a in alerts if start <= a <= start + dur + 6]
        if hit:
            detected += 1; delays.append(hit[0] - start)
    for a in alerts:
        if not any(s <= a <= s + d + 6 for s, _, d, _ in INCIDENTS):
            fa += 1
    print(f"{name:22s} alerts={len(alerts):3d}  incidents detected={detected}/{len(INCIDENTS)}  false alerts={fa:3d}  "
          f"mean delay={statistics.fmean(delays) if delays else float('nan'):5.1f} h")

mean = statistics.fmean(series[:24 * 7 * 4])
print(f"{H} hourly points, {len(INCIDENTS)} injected incidents (level shift, spike, slow drift)\n")
evaluate("static threshold 1.3x", static(series, mean * 1.3))
evaluate("static threshold 1.6x", static(series, mean * 1.6))
evaluate("seasonal baseline + MAD", seasonal_mad(series))
evaluate("seasonal baseline + CUSUM", cusum(series))
print("\nReading the table: a low static threshold pages on every busy period (false alerts); a high one is quiet but late; "
      "seasonal MAD reacts fast to sharp spikes but misses slow shifts; seasonal CUSUM catches shifts and drift sooner than the "
      "high static threshold with no false alerts. The gains are real but modest, they depend on incident shape, and they need no "
      "training data. This is the baseline any ML/LLM 'AI for observability' feature must beat on YOUR incident history "
      "(try other seeds by changing random.Random(11)).")
