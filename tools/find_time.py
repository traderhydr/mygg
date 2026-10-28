#!/usr/bin/env python3
"""When could this signal have fired? Scan candles in a window for a live flip at the entry price.

For each 15m candle in the window whose low-high range contains the entry price, this puts the entry
price in as the forming candle's close and checks whether the chosen rule flipped in the posted
direction. Use it when a signal's posting time is uncertain or a rule misses at the stated time.

  python3 find_time.py SUIUSDT long 0.94001 "2026-10-28 06:00" "2026-10-28 10:00" --rule ema9/21
Rules: macd (12,26,9) or emaF/S (e.g. ema9/21). Run from this folder. Standard library only.
"""
import argparse, datetime as dt
from macd_check import load, macd, ema

ap = argparse.ArgumentParser()
ap.add_argument("symbol")
ap.add_argument("direction", choices=["long", "short"])
ap.add_argument("entry", type=float)
ap.add_argument("start")
ap.add_argument("end")
ap.add_argument("--rule", default="macd")
a = ap.parse_args()
ts = lambda s: int(dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
t0, t1 = ts(a.start), ts(a.end)
want = 1 if a.direction == "long" else -1
c = load(a.symbol)


def value(closes):
    if a.rule == "macd":
        return macd(closes)[2][-1]
    f, s = (int(x) for x in a.rule[3:].split("/"))
    ef, es = ema(closes, f)[-1], ema(closes, s)[-1]
    return ef - es


found = []
for i in range(60, len(c)):
    if not (t0 <= c[i][0] <= t1):
        continue
    t, _, hi, lo, _ = c[i]
    if not (lo <= a.entry <= hi):
        continue
    closed = [x[4] for x in c[:i]]
    d0, d1 = value(closed), value(closed + [a.entry])
    flip = 1 if d0 <= 0 < d1 else -1 if d0 >= 0 > d1 else 0
    found.append((t, flip == want, d0, d1))
print(f"{a.symbol} {a.direction} {a.entry} rule={a.rule}: candles in window whose range contains the entry price")
for t, ok, d0, d1 in found:
    print(f"  {dt.datetime.fromtimestamp(t/1000, dt.timezone.utc):%d %H:%M}  {'FLIP' if ok else '    '}  {d0/a.entry*1e4:+7.1f} -> {d1/a.entry*1e4:+7.1f} bp")
if not found:
    print("  none")
