#!/usr/bin/env python3
"""Run every panel query of the provisioned dashboards through Grafana's query API and report errors / empty panels.

    python scripts/verify_dashboards.py --grafana http://localhost:3000 --range 10m
Needs a running stack with the demo apps sending data (see use-cases/README.md). Exit code 1 if any query errors.
Stdlib only.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request

SUBS = {"$tenant": ".*", "$task_type": ".*", "$intent": ".*", "$service": ".+", "$min_dur": "0s", "$outcome": "&& duration >= 0s"}


def call(url: str, body: dict | None = None, auth: str | None = None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def flatten(panels):
    for p in panels:
        yield p
        yield from flatten(p.get("panels", []))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grafana", default="http://localhost:3000")
    ap.add_argument("--auth", default=None, help="user:password (omit when anonymous access is enabled)")
    ap.add_argument("--range", default="10m")
    ap.add_argument("--uid", action="append", help="limit to dashboard uid(s)")
    a = ap.parse_args()
    dashboards = [d["uid"] for d in call(f"{a.grafana}/api/search?type=dash-db", auth=a.auth)]
    bad = empty = total = 0
    for uid in dashboards:
        if a.uid and uid not in a.uid:
            continue
        dash = call(f"{a.grafana}/api/dashboards/uid/{uid}", auth=a.auth)["dashboard"]
        print(f"\n== {dash['title']} ({uid})")
        for p in flatten(dash["panels"]):
            for t in p.get("targets", []):
                ds = t["datasource"]
                q = {"refId": t["refId"], "datasource": ds, "intervalMs": 15000, "maxDataPoints": 500}
                if ds["type"] == "prometheus":
                    e = t["expr"]
                    for k, v in SUBS.items():
                        e = e.replace(k, v)
                    q.update(expr=e, instant=t.get("instant", False), range=t.get("range", True), legendFormat=t.get("legendFormat", ""))
                elif ds["type"] == "loki":
                    e = t["expr"]
                    for k, v in SUBS.items():
                        e = e.replace(k, v)
                    e = e.replace('trace_id="$traceId"', 'trace_id=~".+"')
                    q.update(expr=e, queryType="range", maxLines=5)
                elif ds["type"] == "tempo":
                    # The Tempo plugin runs TraceQL search in the browser, so check it through the datasource proxy.
                    total += 1
                    try:
                        query = t["query"]
                        for k, v in SUBS.items():
                            query = query.replace(k, v)
                        base = f"{a.grafana}/api/datasources/proxy/uid/{ds['uid']}"
                        if query.strip() in ("$traceId", "$traceB", "$trace_id"):      # trace-by-ID panel: use a recent real trace
                            found = call(f"{base}/api/search?" + urllib.parse.urlencode({"q": '{ resource.service.name != "" }', "limit": 1}), auth=a.auth).get("traces", [])
                            if not found:
                                empty += 1; print(f"  empty  {p['title']} (no traces yet)"); continue
                            call(f"{base}/api/traces/{found[0]['traceID']}", auth=a.auth)
                            print(f"  ok     {p['title']} (trace by ID resolved)"); continue
                        if "$session" in query:
                            sid = ""
                            r = call(f"{base}/api/search?" + urllib.parse.urlencode({"q": '{ span.gen_ai.conversation.id != "" } | select(span.gen_ai.conversation.id)', "limit": 1}), auth=a.auth)
                            for tr in r.get("traces", []):
                                for ss in tr.get("spanSets", []) or [tr.get("spanSet", {})]:
                                    for sp in ss.get("spans", []):
                                        for at in sp.get("attributes", []):
                                            if at["key"] == "gen_ai.conversation.id":
                                                sid = at["value"].get("stringValue", "")
                            query = query.replace("$session", sid)
                        res = call(f"{base}/api/search?" + urllib.parse.urlencode({"q": query, "limit": 5}), auth=a.auth)
                        n = len(res.get("traces", []))
                        if n == 0:
                            empty += 1; print(f"  empty  {p['title']} (TraceQL valid, no matching traces)")
                        else:
                            print(f"  ok     {p['title']} ({n} trace(s))")
                    except Exception as exc:  # noqa: BLE001
                        bad += 1; print(f"  ERROR  {p['title']}: {exc}")
                    continue
                else:
                    continue
                total += 1
                try:
                    res = call(f"{a.grafana}/api/ds/query", {"queries": [q], "from": f"now-{a.range}", "to": "now"}, a.auth)
                    r = res["results"][t["refId"]]
                    if r.get("error"):
                        bad += 1; print(f"  ERROR  {p['title']}: {r['error'][:200]}")
                        continue
                    rows = sum((len(f["data"]["values"][0]) if f["data"]["values"] else 0) for f in r.get("frames", []))
                    if rows == 0:
                        empty += 1; print(f"  empty  {p['title']}")
                    else:
                        print(f"  ok     {p['title']} ({len(r['frames'])} frame(s))")
                except Exception as exc:  # noqa: BLE001
                    bad += 1; print(f"  ERROR  {p['title']}: {exc}")
    print(f"\n{total} queries: {total - bad - empty} ok, {empty} empty, {bad} errors")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
