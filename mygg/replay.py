"""Replay rules over stored 15m candles and compare with real signals.

A candle is treated as one forming candle: a bullish flip occurs if the rule's state at the candle's
high differs from the state at the last close, a bearish flip if it differs at the low. For MACD and
EMA rules the exact price of the flip is solved (trigger_price), which is the live price M.
"""
import csv
import datetime as dt

from . import template
from .rules import DEFAULT_RULES

WINDOW = 300          # closes fed to the indicators; ample for EMA convergence


def load(path):
    with open(path) as f:
        return [(int(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]))
                for r in csv.DictReader(f)]


def replay_symbol(symbol, candles, rules=DEFAULT_RULES, start=100):
    closes = [c[4] for c in candles]
    out = []
    for i in range(start, len(candles)):
        closed = closes[max(0, i - WINDOW):i]
        t, _, hi, lo, _ = candles[i]
        for rule in rules:
            for side, live in ((1, hi), (-1, lo)):
                if rule.flip(closed, live) != side:
                    continue
                trig = rule.trigger_price(closed)
                price = trig if trig is not None and lo <= trig <= hi else live
                out.append({"symbol": symbol, "time": t, "rule": rule.name, "side": side, "price": price})
    return out


def classify(rule, candles, i, side, m, window=WINDOW):
    """How the rule relates to a real signal at live price m in candle i (see validate)."""
    closed = [c[4] for c in candles[max(0, i - window):i]]
    extreme = candles[i][2] if side > 0 else candles[i][3]
    d0 = rule.value(closed[:-1], closed[-1])
    if rule.flip(closed, m) == side:
        return "flip@M", closed
    if rule.flip(closed, extreme) == side:
        return "flip in bar", closed
    if d0 is not None and d0 * side > 0:
        return "already", closed
    return "no", closed


def _rows(signals_path, data_dir):
    for row in csv.DictReader(open(signals_path)):
        try:
            candles = load(f"{data_dir}/{row['symbol']}.csv")
        except FileNotFoundError:
            print(f"skipping {row['symbol']} {row['time_utc']}: no candles in {data_dir}")
            continue
        t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        i = max(k for k in range(len(candles)) if candles[k][0] <= t)
        side = 1 if row["direction"].strip().lower() == "long" else -1
        m = float(row["entry"]) / (1 + side * template.ZONE)     # entry 1 is 0.15% beyond the live price
        yield row, candles, i, side, m


def validate(signals_path, data_dir="data", rules=DEFAULT_RULES, window=WINDOW):
    """Real signals (symbol,time_utc,direction,entry[,rule]) vs what the rules say at that moment.

    Status per signal:
      flip@M       the rule flips at the signal's live price M
      flip in bar  it flips at the candle's high (long) / low (short) but not at M: price crossed the
                   trigger and came back before the post, or the rule latches within the candle
      already      the state had already flipped before this candle (an older cross)
      no           none of the above
    """
    byname = {r.name: r for r in rules}
    hits, totals = {}, {}
    print(f"{'symbol':10s} {'time_utc':16s} {'side':5s} {'rule':11s} {'status':12s} M vs solved trigger  (window {window})")
    for row, candles, i, side, m in _rows(signals_path, data_dir):
        for name in ([row["rule"]] if row.get("rule") else list(byname)):
            rule = byname[name]
            status, closed = classify(rule, candles, i, side, m, window)
            trig = rule.trigger_price(closed)
            note = f"M {m:.6g} vs {trig:.6g} ({(m / trig - 1) * 1e4:+.0f} bp)" if trig else f"M {m:.6g}"
            print(f"{row['symbol']:10s} {row['time_utc']:16s} {row['direction']:5s} {name:11s} {status:12s} {note}")
            totals[name] = totals.get(name, 0) + 1
            hits[name] = hits.get(name, 0) + (status in ("flip@M", "flip in bar"))
    print("\nFlipped in the posting candle: " + ", ".join(f"{n} {hits[n]}/{totals[n]}" for n in totals))


def fit(signals_path, data_dir="data", rules=DEFAULT_RULES, windows=(40, 50, 60, 80, 100, 150, 200, 300, 500, 1000)):
    """Try different numbers of closed candles fed to the indicators.

    EMAs are seeded with an SMA of the first values, so how much history a service loads shifts the
    result by a few basis points. Marginal crosses (SUI, ORDI) are sensitive to it. A window that makes
    every signal flip is a fingerprint of the service's data window.
    """
    byname = {r.name: r for r in rules}
    data = list(_rows(signals_path, data_dir))
    names = sorted({row.get("rule") or n for row, *_ in data for n in ([row.get("rule")] if row.get("rule") else byname)})
    print(f"{'window':>7s}  " + "  ".join(f"{n:>12s}" for n in names) + "   misses")
    for w in windows:
        counts = {n: [0, 0] for n in names}
        misses = []
        for row, candles, i, side, m in data:
            for n in ([row["rule"]] if row.get("rule") else list(byname)):
                status, _ = classify(byname[n], candles, i, side, m, w)
                counts[n][1] += 1
                if status in ("flip@M", "flip in bar"):
                    counts[n][0] += 1
                else:
                    misses.append(f"{row['symbol']}({status})")
        print(f"{w:>7d}  " + "  ".join(f"{c[0]:>9d}/{c[1]:<2d}" for c in counts.values()) + "   " + ", ".join(misses))
