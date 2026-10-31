#!/usr/bin/env python3
"""Candle-by-candle state of one rule, to see exactly when it crossed.

For each 15m candle in the window it prints open/high/low/close and the rule's value (in basis
points of price) at the previous close, at the candle's low, at its high and at its close, plus a
marker when the sign differs from the previous close. Rules: macd, emaF/S (e.g. ema9/21), or bbN/D (e.g. bb20/2: price minus the upper band of the previous N closes).

  python3 trace.py SUIUSDT "2026-10-28 07:00" "2026-10-28 08:30" --rule ema9/21
Run from this folder after template_backtest.py fetch. Standard library only.
"""
import argparse, datetime as dt
from macd_check import load, macd, ema

ap = argparse.ArgumentParser()
ap.add_argument("symbol")
ap.add_argument("start")
ap.add_argument("end")
ap.add_argument("--rule", default="macd")
a = ap.parse_args()
ts = lambda s: int(dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
t0, t1 = ts(a.start), ts(a.end)
c = load(a.symbol)


def value(closes):
    if a.rule == "macd":
        return macd(closes)[2][-1]
    if a.rule.startswith("bb"):
        import statistics as st
        n, d = a.rule[2:].split("/")
        n, d = int(n), float(d)
        w = closes[-n - 1:-1]
        return closes[-1] - (st.mean(w) + d * st.pstdev(w))
    f, s = (int(x) for x in a.rule[3:].split("/"))
    return ema(closes, f)[-1] - ema(closes, s)[-1]


print(f"{a.symbol} rule={a.rule}  (values in basis points of price)")
print("time   open      high      low       close     | prev-close   at low    at high   at close")
for i in range(60, len(c)):
    t, o, h, l, cl = c[i]
    if not (t0 <= t <= t1):
        continue
    closed = [x[4] for x in c[:i]]
    base = closed[-1]
    d_prev = value(closed)
    vals = [value(closed + [p]) for p in (l, h, cl)]
    bp = lambda v: v / cl * 1e4
    mark = ""
    if d_prev <= 0 < max(vals):
        mark = "  <- crosses up in this candle"
    elif d_prev >= 0 > min(vals):
        mark = "  <- crosses down in this candle"
    print(f"{dt.datetime.fromtimestamp(t/1000, dt.timezone.utc):%H:%M}  {o:<9.6g} {h:<9.6g} {l:<9.6g} {cl:<9.6g} | "
          f"{bp(d_prev):+9.1f}  {bp(vals[0]):+9.1f} {bp(vals[1]):+9.1f} {bp(vals[2]):+9.1f}{mark}")
