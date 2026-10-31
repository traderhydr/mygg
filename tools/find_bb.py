#!/usr/bin/env python3
"""Find when a Bollinger-breakout signal could have been posted, from its price alone.

  python3 find_bb.py ENAUSDT long 0.19612 [--data data] [--since "2026-10-30 00:00"]

ENTRY is entry 1 as published (top of a long zone, bottom of a short zone). The live price M is recovered from it.
For every 15m candle whose range contains M it prints how far M sat outside the band of the previous n closes
(z-score, signed so a breakout in the signal's direction is positive) for several n, and marks the candles where
the breakout is strongest. Several signals from one batch narrow the candidates further. Standard library only.
"""
import argparse, csv, datetime as dt, statistics as st

ZONE = 0.0015
PERIODS = (10, 14, 20, 30, 50)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("direction", choices=["long", "short"])
    ap.add_argument("entry", type=float)
    ap.add_argument("--data", default="data")
    ap.add_argument("--since")
    ap.add_argument("--min-z", type=float, default=1.5, help="only list candles where some n reaches this z")
    a = ap.parse_args()
    side = 1 if a.direction == "long" else -1
    m = a.entry / (1 + side * ZONE)
    since = int(dt.datetime.strptime(a.since, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000) if a.since else 0
    c = [(int(r["t"]), float(r["h"]), float(r["l"]), float(r["c"])) for r in csv.DictReader(open(f"{a.data}/{a.symbol}.csv"))]
    print(f"{a.symbol} {a.direction}: live price M = {m:.6g}. Candles containing M with a breakout z >= {a.min_z}:")
    print("time (UTC)        " + "".join(f"{'z' + str(n):>7s}" for n in PERIODS) + "   candle range")
    shown = 0
    for i in range(max(PERIODS), len(c)):
        t, hi, lo, cl = c[i]
        if t < since or not (lo <= m <= hi):
            continue
        zs = []
        for n in PERIODS:
            w = [x[3] for x in c[i - n:i]]
            sd = st.pstdev(w)
            zs.append(side * (m - st.mean(w)) / sd if sd else 0.0)
        if max(zs) < a.min_z:
            continue
        shown += 1
        print(f"{dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc):%m-%d %H:%M}        " +
              "".join(f"{z:7.2f}" for z in zs) + f"   {lo:.6g} - {hi:.6g}")
    if not shown:
        print("  none: lower --min-z, widen --since, or check the symbol and entry")


if __name__ == "__main__":
    main()
