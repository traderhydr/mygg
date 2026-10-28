#!/usr/bin/env python3
"""Which coins had a live MACD histogram flip at a given moment? Were they all signalled?

For a UTC time, takes each coin in ./data, treats the close of the 15m candle containing that time
as the live price (a few minutes late, so an approximation), and checks whether the MACD histogram
flipped sign on that forming candle. Compare the flippers with the coins that actually got a signal
to see how selective the signals are. Run from this folder. Standard library only.

  python3 scan_flips.py "2026-10-28 15:12" --signaled ARBUSDT WLDUSDT STRKUSDT PYTHUSDT
"""
import argparse, glob, os, datetime as dt
from macd_check import load, macd

ap = argparse.ArgumentParser()
ap.add_argument("time", help='UTC, e.g. "2026-10-28 15:12"')
ap.add_argument("--params", default="12,26,9")
ap.add_argument("--signaled", nargs="*", default=[])
ap.add_argument("--symbols", nargs="*", default=None)
a = ap.parse_args()
fa, sl, sg = (int(x) for x in a.params.split(","))
t = int(dt.datetime.strptime(a.time, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
syms = a.symbols or sorted(os.path.basename(p)[:-4] for p in glob.glob("data/*.csv"))

bull, bear, skipped = [], [], []
for s in syms:
    c = load(s)
    idx = [k for k in range(len(c)) if c[k][0] <= t]
    if not idx or t - c[idx[-1]][0] >= 900000 or idx[-1] < 60:
        skipped.append(s)
        continue
    i = idx[-1]
    closed = [x[4] for x in c[:i]]
    h0 = macd(closed, fa, sl, sg)[2][-1]
    h1 = macd(closed + [c[i][4]], fa, sl, sg)[2][-1]
    if h0 <= 0 < h1:
        bull.append(s)
    elif h0 >= 0 > h1:
        bear.append(s)

mark = lambda s: f"{s}{'*' if s in a.signaled else ''}"
print(f"MACD{a.params} live flip at {a.time} UTC ({len(syms) - len(skipped)} coins checked, * = was signalled)")
print("  bullish flips:", ", ".join(mark(s) for s in bull) or "none")
print("  bearish flips:", ", ".join(mark(s) for s in bear) or "none")
if skipped:
    print("  no data for that time:", ", ".join(skipped))
missed = [s for s in a.signaled if s not in bull + bear]
print("  signalled but no flip:", ", ".join(missed) or "none")
