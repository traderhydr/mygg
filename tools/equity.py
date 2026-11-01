#!/usr/bin/env python3
"""Paper account equity: return, peak and drawdown from a few balance readings.

  python3 equity.py balances.csv

balances.csv has one reading per line: time,balance   (time like "2026-11-01 11:00", any timezone as long as it is
the same throughout; balance as a plain number). Include the start balance and the peak if you saw it. Prints the
total return, the peak and the drawdown from it, the largest drawdown between consecutive readings, and the change
between readings. More readings (one a day at the same time is enough) give a better curve. Standard library only.
"""
import csv, sys


def main():
    rows = []
    for r in csv.reader(open(sys.argv[1] if len(sys.argv) > 1 else "balances.csv")):
        if len(r) >= 2 and r[0].strip() and r[0].lower() != "time":
            rows.append((r[0].strip(), float(r[1].replace(",", ""))))
    rows.sort()
    if len(rows) < 2:
        print("need at least two readings")
        return
    start, now = rows[0][1], rows[-1][1]
    peak_t, peak = max(rows, key=lambda x: x[1])
    print(f"{len(rows)} readings, {rows[0][0]} to {rows[-1][0]}")
    print(f"start {start:,.0f}   now {now:,.0f}   change {now - start:+,.0f} ({100 * (now / start - 1):+.1f}%)")
    print(f"peak {peak:,.0f} on {peak_t} ({100 * (peak / start - 1):+.1f}% from start)")
    print(f"from the peak: {now - peak:+,.0f} ({100 * (now / peak - 1):+.1f}%); {100 * (1 - now / peak):.1f}% of the peak balance is gone")
    worst, run_peak = 0.0, rows[0][1]
    for _, b in rows:
        run_peak = max(run_peak, b)
        worst = max(worst, 1 - b / run_peak)
    print(f"largest drawdown in the readings: {100 * worst:.1f}%")
    print("\nstep by step:")
    for (t0, b0), (t1, b1) in zip(rows, rows[1:]):
        print(f"  {t0} -> {t1}: {b0:>10,.0f} -> {b1:>10,.0f}  {100 * (b1 / b0 - 1):+7.1f}%")


if __name__ == "__main__":
    main()
