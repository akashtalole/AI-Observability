#!/usr/bin/env bash
# Runs the three demo apps against Weaver live-check and prints a finding summary.
#   conformance/run.sh [weaver-binary]      (default: weaver on PATH; tested with v0.28.0)
set -euo pipefail
cd "$(dirname "$0")/.."
WEAVER="${1:-weaver}"
OUT="${OUT:-conformance/out}"; mkdir -p "$OUT"
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 OTEL_EXPORTER_OTLP_PROTOCOL=grpc

"$WEAVER" registry live-check -r conformance/registry --v2 --include-unreferenced --config conformance/weaver.toml \
  --input-source otlp --inactivity-timeout 45 --format json --output "$OUT" > "$OUT/live-check.log" 2>&1 &
WPID=$!
sleep 8
kill -0 "$WPID" 2>/dev/null || { echo 'weaver exited early:'; cat "$OUT/live-check.log"; exit 1; }
APPS=()
python use-cases/rag/app/rag_app.py --duration 20 --rps 3 & APPS+=($!)
python use-cases/multi-agent/app/agent_app.py --duration 20 --rps 1 & APPS+=($!)
python use-cases/chatbot/app/chatbot_app.py --duration 20 --rps 1 & APPS+=($!)
wait "${APPS[@]}" || true
curl -s -X POST localhost:4320/stop >/dev/null || true
wait "$WPID" || true
python conformance/summarize.py "$OUT/live_check.json"
