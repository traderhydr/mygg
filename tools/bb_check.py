#!/usr/bin/env python3
"""Is each signal a Bollinger Band breakout? ("15M | BB Breakout" in the original ENA signal.)

For each row of signals.csv (symbol,time_utc,direction,entry) it takes the n closed 15m candles
before the posting candle, builds the band, and measures where the entry price sat relative to it.
  z   = (entry - mean) / stdev of those n closes   (long needs z above the offset, short below -offset)
  bw  = band width (4 stdev / mean) as a percentile of the previous 200 candles; low = a "squeeze"
Reads ./data/<SYMBOL>.csv from template_backtest.py fetch. Standard library only.
"""
import argparse, csv, datetime as dt, statistics as st


def load(sym):
    with open(f"data/{sym}.csv") as f:
        return [(int(r["t"]), float(r["c"])) for r in csv.DictReader(f)]


def zscore(closes, price):
    m, s = st.mean(closes), st.pstdev(closes)
    return (price - m) / s if s else 0.0


def bw_pct(c, i, n):
    """Percentile of the current n-candle band width among the previous 200 widths."""
    def bw(k):
        w = [x[1] for x in c[k - n:k]]
        m = st.mean(w)
        return 4 * st.pstdev(w) / m
    cur = bw(i)
    hist = [bw(k) for k in range(max(n, i - 200), i)]
    return 100 * sum(1 for x in hist if x <= cur) / len(hist) if hist else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="signals.csv")
    ap.add_argument("--periods", type=int, nargs="+", default=[10, 14, 20, 30, 50, 100])
    ap.add_argument("--offset", type=float, default=2.0, help="band offset (stdev) for the chance table")
    a = ap.parse_args()

    cache = {}
    head = "".join(f"{'z' + str(n):>7s}" for n in a.periods)
    print(f"{'symbol':9s} {'time_utc':16s} {'side':5s}{head}   bw%(20)   (z is signed so that a breakout in the posted direction is positive)")
    sums = {n: [] for n in a.periods}
    with open(a.signals) as f:
        for row in csv.DictReader(f):
            sym = row["symbol"]
            c = cache.setdefault(sym, load(sym))
            t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                    .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            i = max(k for k in range(len(c)) if c[k][0] <= t)       # candle containing the post
            price = float(row["entry"]) if row.get("entry") else c[i][1]
            sign = 1 if row["direction"].strip().lower() == "long" else -1
            cols = ""
            for n in a.periods:
                if i < n:
                    cols += f"{'n/a':>7s}"
                    continue
                z = sign * zscore([x[1] for x in c[i - n:i]], price)
                sums[n].append(z)
                cols += f"{z:7.2f}"
            bw = f"{bw_pct(c, i, 20):6.0f}" if i >= 220 else "   n/a"
            print(f"{sym:9s} {row['time_utc']:16s} {row['direction']:5s}{cols}   {bw}")

    print(f"\nSigned z averaged over your signals: " + "  ".join(f"n={n}: {st.mean(v):.2f}" for n, v in sums.items() if v))

    print(f"\nChance level: share of all 15m candles (these coins) whose close is beyond the {a.offset} stdev band of the prior n closes")
    for n in a.periods:
        up = dn = tot = 0
        for c in cache.values():
            for i in range(n, len(c)):
                z = zscore([x[1] for x in c[i - n:i]], c[i][1])
                tot += 1
                up += z > a.offset
                dn += z < -a.offset
        if tot:
            print(f"  n={n:<4d} above {up/tot:5.1%}   below {dn/tot:5.1%}   ({tot} candles)")


if __name__ == "__main__":
    main()
