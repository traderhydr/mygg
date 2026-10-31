#!/usr/bin/env python3
"""What if the scanner published fewer signals? Compare volume limits on your own flip log.

  python3 whatif.py ../mygg_flips.csv [--data data] [--amount 5] [Cornix options as in evaluate.py]

Takes every logged flip (published or not), applies each policy in time order, simulates the signals that survive
(same simulation as evaluate.py) and prints one row per policy: signals per day, how many positions are open at
once at the peak and the margin that ties up, TP1 and stop-out rates, mean return, total account impact and the
largest drawdown. Policies: a per-coin cooldown (same coin and direction, or any direction), optionally across
both rules, and an optional global cap per hour. One signal per coin per candle always applies.
Not modelled: Cornix margin limits, funding, slippage. Standard library only; run from the tools folder.
"""
import argparse, bisect, calendar, csv, time
from collections import defaultdict
import evaluate as ev

BAR = 15 * 60 * 1000
# (label, cooldown in candles, scope, cap per hour or 0)
POLICIES = [
    ("current: 4 candles per coin+rule+direction", 4, "rule", 0),
    ("1h per coin+direction", 4, "dir", 0),
    ("2h per coin+direction", 8, "dir", 0),
    ("4h per coin+direction", 16, "dir", 0),
    ("8h per coin+direction", 32, "dir", 0),
    ("24h per coin+direction", 96, "dir", 0),
    ("4h per coin (any direction)", 16, "coin", 0),
    ("4h per coin+direction, max 6 an hour", 16, "dir", 6),
    ("4h per coin+direction, max 3 an hour", 16, "dir", 3),
]


def apply(flips, cooldown, scope, cap):
    last, in_candle, hour_count, out = {}, set(), defaultdict(int), []
    for f in flips:
        start = f["t"] - f["t"] % BAR
        if (f["sym"], start) in in_candle:
            continue
        key = {"rule": (f["sym"], f["rule"], f["side"]), "dir": (f["sym"], f["side"]), "coin": (f["sym"],)}[scope]
        if key in last and start - last[key] < cooldown * BAR:
            continue
        hour = f["t"] // 3600000
        if cap and hour_count[hour] >= cap:
            continue
        last[key] = start
        in_candle.add((f["sym"], start))
        hour_count[hour] += 1
        out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flips")
    ap.add_argument("--data", default="data")
    ap.add_argument("--amount", type=float, default=5.0)
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--entry-weights", default="65,15,10,10")
    ap.add_argument("--tp-weights", default="60,20,10,10")
    ap.add_argument("--trail", choices=["breakeven", "moving"], default="moving")
    a = ap.parse_args()
    ew = tuple(float(x) / 100 for x in a.entry_weights.split(","))
    tw = tuple(float(x) / 100 for x in a.tp_weights.split(","))

    flips, cache = [], {}
    for r in csv.DictReader(open(a.flips)):
        t = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
        flips.append(dict(t=t, sym=r["symbol"], rule=r["rule"], side=1 if r["direction"] == "long" else -1,
                          price=float(r["price"])))
    flips.sort(key=lambda x: x["t"])
    span_days = max(1.0, (flips[-1]["t"] - flips[0]["t"]) / 86400000)
    print(f"{len(flips)} logged flips over {span_days:.1f} days. Amount {a.amount:g}% per signal, entries {a.entry_weights}, "
          f"targets {a.tp_weights}, trail {a.trail}.\n")
    hdr = f"{'policy':42s} {'n':>5s} {'/day':>5s} {'peak open':>9s} {'peak margin':>11s} {'TP1%':>5s} {'stop%':>5s} {'mean ROE':>8s} {'impact':>8s} {'max DD':>7s}"
    print(hdr)

    sim_cache = {}

    def simulate(f):
        k = (f["sym"], f["t"], f["rule"], f["side"])
        if k in sim_cache:
            return sim_cache[k]
        c = cache.get(f["sym"])
        if c is None:
            try:
                c = cache[f["sym"]] = ev.load(f"{a.data}/{f['sym']}.csv")
            except FileNotFoundError:
                c = cache[f["sym"]] = False
        res = None
        if c:
            i0 = bisect.bisect_right([x[0] for x in c], f["t"]) - 1
            if 0 <= i0 < len(c) - 1:
                res = ev.simulate(c, i0, f["side"], f["price"], ev.LEV.get(f["rule"], 20), a.fee, ew, tw, a.trail)
        sim_cache[k] = res
        return res

    for label, cd, scope, cap in POLICIES:
        kept = apply(flips, cd, scope, cap)
        rows = [(f, simulate(f)) for f in kept]
        rows = [(f, r) for f, r in rows if r]
        if not rows:
            print(f"{label:42s}   no data")
            continue
        n = len(rows)
        impact = [a.amount * r["qty"] * r["roe"] for _, r in rows]
        cum = peak = mdd = 0.0
        for imp, (_, r) in sorted(zip(impact, rows), key=lambda z: z[1][1]["end"]):
            cum += imp
            peak = max(peak, cum)
            mdd = max(mdd, peak - cum)
        ev_list = sorted([(f["t"], 1, a.amount * r["qty"]) for f, r in rows] +
                         [(r["end"], -1, -a.amount * r["qty"]) for f, r in rows])
        open_n = peak_n = 0
        mg = peak_mg = 0.0
        for _, d, m in ev_list:
            open_n += d
            mg += m
            peak_n = max(peak_n, open_n)
            peak_mg = max(peak_mg, mg)
        tp1 = 100 * sum(1 for _, r in rows if r["tp1"]) / n
        stop = 100 * sum(1 for _, r in rows if r["reason"] == "stop") / n
        print(f"{label:42s} {n:5d} {n / span_days:5.0f} {peak_n:9d} {peak_mg:10.0f}% {tp1:5.1f} {stop:5.1f} "
              f"{100 * sum(r['roe'] for _, r in rows) / n:7.1f}% {sum(impact):7.1f}% {mdd:6.1f}%")


if __name__ == "__main__":
    main()
