#!/usr/bin/env python3
"""Line up my scanner's signals with the original bot's posts.

  python3 compare.py ~/mygg/mygg_signals.csv original.csv [--tz 5] [--window 30]

mygg_signals.csv: time_utc,symbol,rule,direction,... (written by the scanner, UTC)
original.csv:     time,symbol,direction,rule          (your notes; rule optional; time in your local zone,
                  --tz is the hours ahead of UTC, 5 for UTC+5). Symbols may be BTC or BTCUSDT.
Each original post is matched to the nearest unmatched scanner signal for the same coin and direction (and
rule if given) within --window minutes. Output: matches with the delay, scanner-only signals (flips the
original did not post: the filter), and original-only posts (flips my rules missed).
"""
import argparse, csv, datetime as dt


def when(text, off=0.0):
    text = text.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(text[:19] if fmt.endswith("%S") else text[:16], fmt) - dt.timedelta(hours=off)
        except ValueError:
            pass
    raise ValueError(f"cannot read time {text!r}")


def coin(s):
    s = s.strip().upper()
    return s[:-4] if s.endswith("USDT") else s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mine")
    ap.add_argument("original")
    ap.add_argument("--tz", type=float, default=0.0)
    ap.add_argument("--window", type=float, default=30.0, help="minutes")
    a = ap.parse_args()
    mine = [dict(t=when(r["time_utc"]), c=coin(r["symbol"]), d=r["direction"].strip().lower(), rule=r.get("rule", ""))
            for r in csv.DictReader(open(a.mine))]
    orig = [dict(t=when(r["time"], a.tz), c=coin(r["symbol"]), d=r["direction"].strip().lower(), rule=r.get("rule", ""))
            for r in csv.DictReader(open(a.original))]
    used, pairs, missed = set(), [], []
    for o in sorted(orig, key=lambda x: x["t"]):
        best = None
        for k, m in enumerate(mine):
            if k in used or m["c"] != o["c"] or m["d"] != o["d"]:
                continue
            if o["rule"] and m["rule"] and o["rule"].lower() != m["rule"].lower():
                continue
            gap = (o["t"] - m["t"]).total_seconds() / 60
            if abs(gap) <= a.window and (best is None or abs(gap) < abs(best[1])):
                best = (k, gap)
        if best:
            used.add(best[0])
            pairs.append((o, mine[best[0]], best[1]))
        else:
            missed.append(o)
    extra = [m for k, m in enumerate(mine) if k not in used]
    print(f"Matched {len(pairs)} of {len(orig)} original posts; scanner fired {len(mine)}.")
    print("\nMATCHED (delay = original post minus my signal, minutes; positive = original later)")
    for o, m, g in pairs:
        print(f"  {o['t']:%m-%d %H:%M} {o['c']:8s} {o['d']:5s} {m['rule'] or o['rule']:11s} delay {g:+6.1f}")
    print("\nSCANNER ONLY (flips the original did not post)")
    for m in sorted(extra, key=lambda x: x["t"]):
        print(f"  {m['t']:%m-%d %H:%M} {m['c']:8s} {m['d']:5s} {m['rule']}")
    print("\nORIGINAL ONLY (posts my rules did not produce)")
    for o in missed:
        print(f"  {o['t']:%m-%d %H:%M} {o['c']:8s} {o['d']:5s} {o['rule']}")


if __name__ == "__main__":
    main()
