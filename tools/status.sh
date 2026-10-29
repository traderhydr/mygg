#!/usr/bin/env bash
# One-screen health check for the scanner. Read-only. Usage: ./tools/status.sh
cd "$(dirname "$0")/.." || exit 1
now=$(date +%s); today=$(date -u +%F)
echo "== processes (expect one run_scanner.sh and one mygg scan)"
pgrep -af "run_scanner.sh|mygg scan" || echo "NOT RUNNING"
echo "== last scan pass"
if [ -f mygg_heartbeat ]; then
  age=$((now - $(cat mygg_heartbeat)))
  echo "${age}s ago"
  [ "$age" -gt 120 ] && echo "WARNING: no scan pass for over 2 minutes"
else
  echo "no heartbeat file yet (restart the scanner so it runs the latest code)"
fi
if [ -f mygg_flips.csv ]; then
  echo "== flips today (UTC $today): $(grep -c "^$today" mygg_flips.csv) logged, $(grep "^$today" mygg_flips.csv | awk -F, '$8==1' | wc -l) published"
  echo "== last 5 flips"; tail -5 mygg_flips.csv
fi
echo "== problems in scan.out (last 5)"
grep -E "scan error|telegram send failed|exited" scan.out 2>/dev/null | tail -5
true
