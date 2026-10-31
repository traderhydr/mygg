#!/usr/bin/env python3
"""Summarise Cornix signal exports (the CSV with Date, Symbol, Status, Leverage, Direction, Signal Gained Profit %).

  python3 cornix_report.py export1.csv [export2.csv ...] [--amount 5]

Merges the files (duplicates by date + symbol + direction are dropped), then reports status counts, profit by status,
by direction and leverage (25x is the MACD rule, 15x the EMA rule), by age and by day, the worst open trades, and an
estimate of the account effect at --amount percent of the balance per signal (profit% x amount x filled share).
An export of only active signals leaves out stopped and closed trades, so its totals are biased upward; the report
says so when it sees no closed or stopped status. Export the closed signals too. Standard library only.
"""
import argparse, csv, re, statistics as st
from collections import Counter, defaultdict


def minutes(s):
    t = {"day": 1440, "hr": 60, "min": 1}
    return sum(int(n) * t[u] for n, u in re.findall(r"(\d+)\s*(day|hr|min)", s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--amount", type=float, default=None, help="percent of the balance per signal; omit if unknown")
    a = ap.parse_args()
    seen, rows = set(), []
    for fn in a.files:
        for r in csv.DictReader(open(fn, newline="")):
            k = (r["Date"], r["Symbol"], r["Direction"])
            if k in seen:
                continue
            seen.add(k)
            try:
                r["p"] = float(r["Signal Gained Profit %"])
            except ValueError:
                continue
            r["age"] = minutes(r["Duration"])
            r["filled"] = float(r["Entry Targets % Filled"] or 0) / 100
            st_ = r["Status"]
            r["kind"] = ("active" if st_.startswith(("Buy", "Sell")) else "partial" if st_.startswith("Partial")
                         else "all targets" if st_.startswith("All") else "stopped" if st_.startswith("Stop")
                         else "cancelled" if st_.startswith("Cancel") else "closed/other")
            rows.append(r)
    if not rows:
        print("no rows")
        return
    dates = sorted(r["Date"] for r in rows)
    print(f"{len(rows)} signals, {dates[0]} to {dates[-1]}")
    print("\nStatus counts:", dict(Counter(r["Status"] for r in rows).most_common(12)))
    if not any(r["kind"] in ("stopped", "cancelled", "closed/other") for r in rows):
        print("NOTE: no stopped or closed statuses in this file. It looks like active signals only, so stop-outs and\n"
              "      breakeven exits are missing and the totals below are biased upward. Export the closed signals too.")

    def line(name, v):
        if not v:
            return
        eff = f"  account~{sum(r['p'] * r['filled'] for r in v) * a.amount / 100:+7.1f}%" if a.amount else ""
        print(f"  {name:22s} n={len(v):4d} mean={st.mean(x['p'] for x in v):7.2f}% median={st.median(x['p'] for x in v):7.2f}% "
              f"positive={sum(1 for x in v if x['p'] > 0):4d} negative={sum(1 for x in v if x['p'] < 0):4d} "
              f"sum={sum(x['p'] for x in v):9.1f}%{eff}")

    print("\nBy kind (profit % is per signal, on the margin of that signal):" +
          (f" account effect assumes {a.amount:g}% of the balance per signal" if a.amount else ""))
    for k in ("active", "partial", "all targets", "cancelled", "stopped", "closed/other"):
        line(k, [r for r in rows if r["kind"] == k])
    closed = [r for r in rows if r["kind"] != "active"]
    if closed:
        wins, losses = [r["p"] for r in closed if r["p"] > 0], [r["p"] for r in closed if r["p"] < 0]
        print(f"\nClosed trades only: {len(closed)}; winners {len(wins)} (avg {st.mean(wins):.1f}%), losers {len(losses)} "
              f"(avg {st.mean(losses) if losses else 0:.1f}%); total {sum(r['p'] for r in closed):.0f}%")
    # a cancelled trade that ends within 2.5 min of an opposite signal on the same coin was closed by that signal
    import datetime as _dt
    by_sym = defaultdict(list)
    for r in rows:
        r["t"] = _dt.datetime.strptime(r["Date"], "%Y-%m-%d %H:%M:%S").timestamp()
        by_sym[r["Symbol"]].append(r)
    canc = [r for r in rows if r["kind"] == "cancelled"]
    if canc:
        rev = [r for r in canc if any(x["Direction"] != r["Direction"] and abs(x["t"] - (r["t"] + r["age"] * 60)) < 150
                                      for x in by_sym[r["Symbol"]])]
        print(f"Cancelled trades that ended within 2.5 min of an opposite signal on the same coin: {len(rev)} of {len(canc)}")
        for lt in "0123":
            v = [r["p"] for r in canc if r["Last Target"] == lt]
            if v:
                print(f"  cancelled after target {lt}: n={len(v):3d} mean={st.mean(v):7.1f}% negative={sum(1 for x in v if x < 0)}")
    print("\nBy direction and leverage (25x MACD, 15x EMA):")
    for d in ("Long", "Short"):
        for lev in ("25.0X", "15.0X"):
            line(f"{d} {lev}", [r for r in rows if r["Direction"] == d and lev in r["Leverage"]])
    print("\nActive trades by age:")
    for lo, hi in ((0, 60), (60, 360), (360, 720), (720, 1440), (1440, 10 ** 6)):
        line(f"{lo}-{hi} min", [r for r in rows if r["kind"] == "active" and lo <= r["age"] < hi])
    print("\nBy day (signal date):")
    byday = defaultdict(list)
    for r in rows:
        byday[r["Date"][:10]].append(r)
    for d in sorted(byday):
        line(d, byday[d])
    print("\nCoins with the most signals:", ", ".join(f"{s} x{n}" for s, n in Counter(r["Symbol"] for r in rows).most_common(8)))
    print("\nWorst 8 trades by profit %:")
    for r in sorted(rows, key=lambda r: r["p"])[:8]:
        print(f"  {r['Date']} {r['Symbol']:10s} {r['Direction']:5s} {r['Leverage']:13s} {r['Status']:24s} {r['p']:8.2f}%  age {r['Duration']}")


if __name__ == "__main__":
    main()
