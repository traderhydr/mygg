#!/usr/bin/env python3
"""Do signals do better in some market sessions, or when many coins flip at once?

  python3 sessions.py ../mygg_flips.csv [--data data] [Cornix options as in evaluate.py]

Simulates every published signal (same simulation as evaluate.py) and groups the results by:
  session (UTC): Asia 00:00-08:00, London 08:00-13:30, New York 13:30-21:00, Late 21:00-24:00
  burst size: how many published signals appeared in the same 15-minute candle across all coins
For each group it prints the number of signals, TP1 rate, loss rate (stop-outs), mean return on margin, and a DAY-LEVEL
check: the mean of the daily averages, the share of days with a positive average, and a 90% interval from resampling
days. Signals from one market move are correlated, so the day, not the trade, is the unit that matters; a pattern is
only believable if it holds on most days. Needs several weeks of data to say much. Standard library only.
"""
import argparse, bisect, calendar, csv, random, statistics as st, time
from collections import defaultdict
import evaluate as ev

BAR = 15 * 60 * 1000
SESSIONS = (("Asia 00-08", 0, 480), ("London 08-13:30", 480, 810), ("New York 13:30-21", 810, 1260), ("Late 21-24", 1260, 1440))


def session(minute):
    for name, lo, hi in SESSIONS:
        if lo <= minute < hi:
            return name


def burst_bucket(n):
    return "1-3 together" if n <= 3 else "4-9 together" if n <= 9 else "10+ together"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flips")
    ap.add_argument("--data", default="data")
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--entry-weights", default="65,15,10,10")
    ap.add_argument("--tp-weights", default="60,20,10,10")
    ap.add_argument("--trail", choices=["breakeven", "moving"], default="moving")
    a = ap.parse_args()
    ew = tuple(float(x) / 100 for x in a.entry_weights.split(","))
    tw = tuple(float(x) / 100 for x in a.tp_weights.split(","))

    sigs, cache = [], {}
    for r in csv.DictReader(open(a.flips)):
        if r.get("published", "1") == "0":
            continue
        t = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
        sigs.append(dict(t=t, sym=r["symbol"], rule=r["rule"], side=1 if r["direction"] == "long" else -1,
                         price=float(r["price"])))
    per_candle = defaultdict(int)
    for s in sigs:
        per_candle[s["t"] - s["t"] % BAR] += 1
    rows = []
    for s in sigs:
        c = cache.get(s["sym"])
        if c is None:
            try:
                c = cache[s["sym"]] = ev.load(f"{a.data}/{s['sym']}.csv")
            except FileNotFoundError:
                c = cache[s["sym"]] = False
        if not c:
            continue
        i0 = bisect.bisect_right([x[0] for x in c], s["t"]) - 1
        if i0 < 0 or i0 >= len(c) - 1:
            continue
        res = ev.simulate(c, i0, s["side"], s["price"], ev.LEV.get(s["rule"], 20), a.fee, ew, tw, a.trail)
        g = time.gmtime(s["t"] / 1000)
        s.update(res=res, day=time.strftime("%Y-%m-%d", g), minute=g.tm_hour * 60 + g.tm_min,
                 burst=per_candle[s["t"] - s["t"] % BAR])
        rows.append(s)
    if not rows:
        print("no signals with candles")
        return
    days = sorted({r["day"] for r in rows})
    print(f"{len(rows)} signals over {len(days)} days ({days[0]} to {days[-1]}). Returns are on margin, unresolved trades closed at the last price.\n")

    def report(title, keyfn, order):
        print(title)
        print(f"  {'':18s} {'n':>5s} {'TP1%':>6s} {'stop%':>6s} {'mean ROE':>9s} | {'mean of days':>12s} {'days>0':>8s} {'90% range (days)':>20s}")
        random.seed(7)
        for k in order:
            v = [r for r in rows if keyfn(r) == k]
            if not v:
                continue
            n = len(v)
            byday = defaultdict(list)
            for r in v:
                byday[r["day"]].append(100 * r["res"]["roe"])
            dm = [st.mean(x) for x in byday.values()]
            boots = sorted(st.mean(random.choices(dm, k=len(dm))) for _ in range(2000)) if len(dm) > 1 else dm * 2
            lo, hi = boots[int(0.05 * len(boots))], boots[int(0.95 * len(boots)) - 1]
            print(f"  {k:18s} {n:5d} {100 * sum(1 for r in v if r['res']['tp1']) / n:6.1f} "
                  f"{100 * sum(1 for r in v if r['res']['reason'] == 'stop') / n:6.1f} "
                  f"{100 * sum(r['res']['roe'] for r in v) / n:8.1f}% | {st.mean(dm):11.1f}% "
                  f"{sum(1 for x in dm if x > 0)}/{len(dm):<5d} {lo:9.1f}% to {hi:7.1f}%")
        print()

    report("By session (UTC)", lambda r: session(r["minute"]), [s[0] for s in SESSIONS])
    report("By how many signals fired in the same 15-minute candle", lambda r: burst_bucket(r["burst"]),
           ["1-3 together", "4-9 together", "10+ together"])
    hours = defaultdict(list)
    for r in rows:
        hours[r["minute"] // 60].append(100 * r["res"]["roe"])
    print("By UTC hour (signals, mean return):  " + "  ".join(f"{h:02d}:{len(hours[h])}/{st.mean(hours[h]):+.0f}%" for h in sorted(hours)))


if __name__ == "__main__":
    main()
