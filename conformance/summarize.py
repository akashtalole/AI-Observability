import json, sys, collections
d = json.load(open(sys.argv[1]))
cnt = collections.Counter(); ex = {}
def walk(o, path=()):
    if isinstance(o, dict):
        r = o.get("live_check_result")
        if r:
            for a in r.get("all_advice", []):
                key = (a.get("level"), a.get("id"), a.get("signal_type"), a.get("message"))
                cnt[key] += 1
        for k, v in o.items(): walk(v, path + (k,))
    elif isinstance(o, list):
        for v in o: walk(v, path)
walk(d["samples"])
only = sys.argv[2] if len(sys.argv) > 2 else None
for (lvl, i, st, msg), n in cnt.most_common():
    if only and only not in (msg or "") and only not in (i or ""): continue
    print(f"{n:5d} {lvl:11s} {i:28s} {str(st):8s} {msg[:150]}")
