#!/usr/bin/env python3
"""Candle by candle: where could the rule have fired, and in which of those candles did the original post?

For every 15m candle between the first and last original signal (plus margin) it lists the coins whose
high (or low) went beyond the 20-candle 2 sd band while the previous close was inside, and whose band width
percentile (prior 200) is at or below --maxpct. Candles in which the original posted are marked with their
posted coins (*). Shows how many candles had eligible coins but no post at all. Standard library only.
"""
import argparse, csv, datetime as dt, glob, os, statistics as st
from bb_discriminate import load, width


def eligible(c, i, maxpct):
    cl = [x[4] for x in c]
    w = cl[i - 20:i]
    m, sd = st.mean(w), st.pstdev(w)
    if sd == 0:
        return None
    wp = cl[i - 21:i - 1]
    zp = (cl[i - 1] - st.mean(wp)) / (st.pstdev(wp) or 1e-12)
    if abs(zp) > 2:
        return None
    up, lo = m + 2 * sd, m - 2 * sd
    side = "long" if c[i][2] > up else "short" if c[i][3] < lo else None
    if not side:
        return None
    cur = width(w)
    hist = [width(cl[k - 20:k]) for k in range(max(20, i - 200), i)]
    pct = 100 * sum(1 for x in hist if x <= cur) / len(hist)
    return (side, pct) if pct <= maxpct else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--signals", default="signals_bb.csv")
    ap.add_argument("--maxpct", type=float, default=45)
    ap.add_argument("--margin", type=int, default=4, help="candles to show before the first and after the last signal")
    a = ap.parse_args()
    coins = {os.path.basename(p)[:-4]: load(p) for p in sorted(glob.glob(os.path.join(a.data, "*.csv")))}
    posted = {}
    with open(a.signals) as f:
        for r in csv.DictReader(f):
            t = int(dt.datetime.strptime(r["time_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            posted.setdefault(t - t % 900000, {})[r["symbol"][:-4]] = r["direction"]
    t0, t1 = min(posted) - a.margin * 900000, max(posted) + a.margin * 900000
    rows, with_post, without = [], [], []
    ref = next(iter(coins.values()))
    for i, cd in enumerate(ref):
        if not t0 <= cd[0] <= t1:
            continue
        ts = cd[0]
        el = {}
        for sym, c in coins.items():
            j = next((k for k in range(len(c)) if c[k][0] == ts), None)
            if j is None or j < 230:
                continue
            e = eligible(c, j, a.maxpct)
            if e:
                el[sym[:-4]] = e[0]
        p = posted.get(ts)
        (with_post if p else without).append(len(el))
        if el or p:
            names = " ".join(("*" if p and p.get(s) == d else "") + s + ("-" if d == "short" else "+") for s, d in sorted(el.items()))
            miss = [s for s in (p or {}) if s not in el]
            rows.append((ts, len(el), names, miss, bool(p)))
    print("time (UTC)        eligible  coins (+ long, - short, * the original posted it)")
    for ts, n, names, miss, hasp in rows:
        tm = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).strftime("%m-%d %H:%M")
        print(f"{'POST ' if hasp else '     '}{tm}  {n:3d}  {names}" + (f"   [posted but not eligible: {' '.join(miss)}]" if miss else ""))
    print(f"\ncandles with a post: {len(with_post)}, mean eligible {st.mean(with_post) if with_post else 0:.1f}")
    print(f"candles without a post: {len(without)}, mean eligible {st.mean(without) if without else 0:.1f}, "
          f"of which {sum(1 for n in without if n)} had at least one eligible coin")


if __name__ == "__main__":
    main()
