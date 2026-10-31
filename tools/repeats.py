#!/usr/bin/env python3
"""Repeated signals on the same coin in the same direction, and positions stacked on top of each other.

  python3 repeats.py ../mygg_flips.csv [--data data] [--window 4] [--amount 5]

Uses the published flips only. A signal is a "repeat" if the same coin and direction was published less than
--window hours earlier. Reports: how long the gaps between same-coin same-direction signals are, which coins repeat
most, how first signals and repeats perform (same simulation as evaluate.py), how often a repeat arrived while the
earlier position on that coin was still open (stacking), and the peak number of positions open at once with the
margin that would tie up at --amount percent each. Run from the tools folder after fetching candles.
"""
import argparse, bisect, calendar, csv, time
from collections import defaultdict
import evaluate as ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flips")
    ap.add_argument("--data", default="data")
    ap.add_argument("--window", type=float, default=4.0, help="hours that make a signal a repeat")
    ap.add_argument("--amount", type=float, default=5.0)
    ap.add_argument("--fee", type=float, default=0.0005)
    a = ap.parse_args()

    cache, sigs = {}, []
    for r in csv.DictReader(open(a.flips)):
        if r.get("published", "1") == "0":
            continue
        t = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
        sigs.append(dict(t=t, sym=r["symbol"], side=1 if r["direction"] == "long" else -1, dirn=r["direction"],
                         rule=r["rule"], price=float(r["price"])))
    sigs.sort(key=lambda x: x["t"])
    print(f"{len(sigs)} published signals")

    last, gaps = {}, defaultdict(list)
    for s in sigs:
        k = (s["sym"], s["side"])
        s["gap_h"] = (s["t"] - last[k]) / 3.6e6 if k in last else None
        s["repeat"] = s["gap_h"] is not None and s["gap_h"] < a.window
        if s["gap_h"] is not None:
            gaps[k].append(s["gap_h"])
        last[k] = s["t"]
    allgaps = [g for v in gaps.values() for g in v]
    print(f"\nGap since the previous published signal on the same coin and direction ({len(allgaps)} repeats of any age)")
    for lo, hi in ((0, 1), (1, 2), (2, 4), (4, 8), (8, 24), (24, 1e9)):
        n = sum(1 for g in allgaps if lo <= g < hi)
        print(f"  {lo:>3}-{'' if hi > 1e8 else hi:<3} h: {n:5d}  {'#' * min(60, n // max(1, len(allgaps) // 60))}")
    by = defaultdict(int)
    for s in sigs:
        if s["repeat"]:
            by[(s["sym"], s["dirn"])] += 1
    top = sorted(by.items(), key=lambda kv: -kv[1])[:10]
    print(f"\nSignals that repeat within {a.window:g} h: {sum(by.values())} of {len(sigs)} "
          f"({100 * sum(by.values()) / max(1, len(sigs)):.0f}%). Most repeated: " +
          ", ".join(f"{k[0]} {k[1]} x{v}" for k, v in top))

    # simulate every signal
    for s in sigs:
        c = cache.setdefault(s["sym"], None)
        if c is None:
            try:
                c = cache[s["sym"]] = ev.load(f"{a.data}/{s['sym']}.csv")
            except FileNotFoundError:
                c = cache[s["sym"]] = False
        if not c:
            s["res"] = None
            continue
        i0 = bisect.bisect_right([x[0] for x in c], s["t"]) - 1
        if i0 < 0 or i0 >= len(c) - 1:
            s["res"] = None
            continue
        s["res"] = ev.simulate(c, i0, s["side"], s["price"], ev.LEV.get(s["rule"], 20), a.fee)
    done = [s for s in sigs if s["res"]]

    print("\nFirst signals vs repeats (return on margin; account % at {:g}% per signal)".format(a.amount))
    print(f"  {'':8s} {'n':>5s} {'TP1%':>6s} {'stop%':>6s} {'open%':>6s} {'mean ROE':>9s} {'account %':>10s}")
    for name, flag in (("first", False), ("repeat", True)):
        v = [s for s in done if s["repeat"] == flag]
        if not v:
            continue
        n = len(v)
        pct = lambda f: 100 * sum(1 for x in v if f(x["res"])) / n
        imp = sum(a.amount * x["res"]["qty"] * x["res"]["roe"] for x in v)
        print(f"  {name:8s} {n:5d} {pct(lambda r: r['tp1']):6.1f} {pct(lambda r: r['reason'] == 'stop'):6.1f} "
              f"{pct(lambda r: r['reason'] == 'open'):6.1f} {100 * sum(x['res']['roe'] for x in v) / n:8.1f}% {imp:9.1f}%")

    # stacking: a repeat opened while the earlier same coin/direction position was still open
    ends, stacked, depth = defaultdict(list), 0, defaultdict(int)
    for s in done:
        k = (s["sym"], s["side"])
        d = sum(1 for e in ends[k] if e > s["t"])
        if d:
            stacked += 1
        depth[k] = max(depth[k], d + 1)
        ends[k].append(s["res"]["end"])
    print(f"\nStacking: {stacked} signals ({100 * stacked / max(1, len(done)):.0f}%) were opened while an earlier position on the same coin "
          f"and direction was still open. Deepest stacks: " +
          ", ".join(f"{k[0]} {'long' if k[1] > 0 else 'short'} x{v}" for k, v in sorted(depth.items(), key=lambda kv: -kv[1])[:6]))

    # peak simultaneous positions
    events = []
    for s in done:
        events.append((s["t"], 1, a.amount * s["res"]["qty"]))
        events.append((s["res"]["end"], -1, -a.amount * s["res"]["qty"]))
    events.sort()
    n = peak_n = 0
    m = peak_m = 0.0
    when = 0
    for t, d, mg in events:
        n += d
        m += mg
        if n > peak_n:
            peak_n, when = n, t
        peak_m = max(peak_m, m)
    print(f"\nPeak positions open at once: {peak_n} (at {time.strftime('%Y-%m-%d %H:%M', time.gmtime(when / 1000))} UTC); "
          f"peak margin tied up: {peak_m:.0f}% of the balance at {a.amount:g}% per signal")


if __name__ == "__main__":
    main()
