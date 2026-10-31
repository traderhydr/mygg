#!/usr/bin/env bash
# Keeps the scanner running for a long unattended run: restarts it 30 s after any exit.
# Start:  nohup ./tools/run_scanner.sh > /dev/null 2>&1 &
# Extra scanner options can follow, e.g. ./tools/run_scanner.sh --cooldown 16 --cooldown-scope dir --max-per-hour 3
# Stop:   pkill -f run_scanner.sh; pkill -f "mygg scan"
cd "$(dirname "$0")/.." || exit 1
set -a; [ -f "$HOME/.mygg_env" ] && . "$HOME/.mygg_env"; set +a
while true; do
  python3 -m mygg scan --rules macd ema "$@" >> scan.out 2>&1
  echo "scanner exited $(date -u +%FT%TZ), restarting in 30s" >> scan.out
  sleep 30
done
