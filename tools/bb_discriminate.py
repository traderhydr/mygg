#!/usr/bin/env python3
"""Which breakouts did the original pick? For each original signal time, list every coin in ./data that
broke out of its 20-candle 2 sd band in that candle (previous close inside), with features, and mark the
coins the original actually posted (*). Then compare the averages of picked and not-picked coins.
Features: z (close vs band of the prior 20 closes), width percentile (prior 200), RSI(14),
candle move %, and the move in ATR-like units (candle range / mean range of the last 20). Standard library only.
"""
import argparse, csv, datetime as dt, glob, os, statistics as st


def load(p):
    with open(p) as f:
        return [(int(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"])) for r in csv.DictReader(f)]


def width(w):
    m = sum(w) / len(w)
    return 4 * (sum((x - m) ** 2 for x in w) / len(w)) ** 0.5 / m


def rsi(cl, i, n=14):
    g = l = 0.0
    for k in range(1, n + 1):
        d = cl[k] - cl[k - 1]
        g, l = (g + max(d, 0), l + max(-d, 0))
    g, l = g / n, l / n
    for k in range(n + 1, i + 1):
        d = cl[k] - cl[k - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        l = (l * (n - 1) + max(-d, 0)) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def features(c, i):
    cl = [x[4] for x in c]
    w = cl[i - 20:i]
    m, sd = st.mean(w), st.pstdev(w)
    if sd == 0:
        return None
    z = (cl[i] - m) / sd
    zp = (cl[i - 1] - st.mean(cl[i - 21:i - 1])) / (st.pstdev(cl[i - 21:i - 1]) or 1e-12)
    if abs(z) <= 2 or abs(zp) > 2:
        return None
    cur = width(w)
    hist = [width(cl[k - 20:k]) for k in range(max(20, i - 200), i)]
    pct = 100 * sum(1 for x in hist if x <= cur) / len(hist)
    rng = [x[2] - x[3] for x in c[i - 20:i]]
    return dict(dir="long" if z > 0 else "short", z=z, pct=pct, rsi=rsi(cl, i),
                move=100 * (cl[i] / cl[i - 1] - 1), big=(c[i][2] - c[i][3]) / (st.mean(rng) or 1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--signals", default="signals_bb.csv")
    a = ap.parse_args()
    coins = {os.path.basename(p)[:-4]: load(p) for p in sorted(glob.glob(os.path.join(a.data, "*.csv")))}
    with open(a.signals) as f:
        sigs = list(csv.DictReader(f))
    times = sorted({s["time_utc"] for s in sigs})
    picked, other = [], []
    for tm in times:
        t = int(dt.datetime.strptime(tm, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        chosen = {s["symbol"]: s["direction"] for s in sigs if s["time_utc"] == tm}
        rows = []
        for sym, c in coins.items():
            idx = [k for k in range(len(c)) if c[k][0] <= t]
            if not idx or idx[-1] < 230:
                continue
            ft = features(c, idx[-1])
            if ft:
                rows.append((sym, ft))
        print(f"\n== {tm} UTC: {len(rows)} coins broke out; the original posted {len(chosen)} ({', '.join(chosen)})")
        print(f"   {'':1s}{'symbol':10s}{'dir':6s}{'z':>6s}{'width%':>8s}{'rsi':>6s}{'move%':>7s}{'range x':>9s}")
        for sym, ft in sorted(rows, key=lambda r: -abs(r[1]["z"])):
            star = "*" if chosen.get(sym) == ft["dir"] else " "
            (picked if star == "*" else other).append(ft)
            print(f"   {star}{sym:10s}{ft['dir']:6s}{ft['z']:6.2f}{ft['pct']:8.0f}{ft['rsi']:6.0f}{ft['move']:7.2f}{ft['big']:9.1f}")
        miss = [s for s, d in chosen.items() if s not in dict(rows) or dict(rows)[s]["dir"] != d]
        if miss:
            print(f"   original posted but no flip in this candle by our test: {', '.join(miss)}")
    print("\nAverages (picked vs not picked):")
    for name, g in (("picked", picked), ("not picked", other)):
        if g:
            print(f"  {name:11s} n={len(g):3d}  |z| {st.mean(abs(x['z']) for x in g):.2f}  width% {st.mean(x['pct'] for x in g):.0f}  "
                  f"rsi {st.mean(x['rsi'] for x in g):.0f}  |move|% {st.mean(abs(x['move']) for x in g):.2f}  range x {st.mean(x['big'] for x in g):.1f}")


if __name__ == "__main__":
    main()
