#!/usr/bin/env python3
"""Features of each flip, to find what separates signals the original posted from flips it skipped.

Input: a CSV with columns symbol,time_utc,direction,entry,rule,posted   (posted = 1 if the original
bot sent it, 0 if my scanner fired it and the original stayed silent). entry is entry 1 as published.
Candles come from ./data/<SYMBOL>.csv (template_backtest.py fetch). For each row it prints, with the
live price M as the forming candle's close:
  hist   MACD histogram at the last close -> at M, in basis points of price (MACD rows)
  line   MACD line (fast EMA - slow EMA) at M, bp: its sign says whether the cross is below/above zero
  rsi    RSI(14) at M
  trend  price vs EMA50 and EMA200, bp
  ret1h, ret4h   price change over 4 and 16 candles
  vol    volume of the last 4 closed candles / average of the previous 48
  since  candles since the previous flip in the opposite direction
Standard library only; run from the tools folder.
"""
import argparse, csv, datetime as dt, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mygg import indicators as ix
from mygg.rules import MACDCross, EMACross

ZONE = 0.0015


def load(sym):
    with open(f"data/{sym}.csv") as f:
        return [(int(r["t"]), float(r["c"]), float(r["v"])) for r in csv.DictReader(f)]


def rsi(closes, n=14):
    d = [b - a for a, b in zip(closes, closes[1:])][-n * 6:]
    g = l = 0.0
    for k, x in enumerate(d):                                  # Wilder smoothing
        up, dn = max(x, 0), max(-x, 0)
        g = up if k == 0 else (g * (n - 1) + up) / n
        l = dn if k == 0 else (l * (n - 1) + dn) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def bars_since_opposite(rule, closes, side):
    """Candles back to the last close at which the rule's state had the opposite sign."""
    for k in range(len(closes) - 1, 40, -1):
        d = rule.value(closes[:k - 1], closes[k - 1])
        if d is not None and d * side < 0:
            return len(closes) - k
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("signals")
    a = ap.parse_args()
    print(f"{'symbol':9s} {'time_utc':16s} {'side':5s} {'rule':10s} post  hist(bp)        line  rsi  vs50  vs200 ret1h ret4h  vol since")
    for row in csv.DictReader(open(a.signals)):
        c = load(row["symbol"])
        t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        i = max(k for k in range(len(c)) if c[k][0] <= t)
        side = 1 if row["direction"].strip().lower() == "long" else -1
        m = float(row["entry"]) / (1 + side * ZONE)
        closes = [x[1] for x in c[max(0, i - 400):i]]
        vols = [x[2] for x in c[max(0, i - 60):i]]
        rule = MACDCross() if row.get("rule", "MACD Cross") == "MACD Cross" else EMACross()
        live = closes + [m]
        bp = lambda v: v / m * 1e4
        if isinstance(rule, MACDCross):
            h0, h1 = rule.value(closes[:-1], closes[-1]), rule.value(closes, m)
            f, s = ix.ema(live, 12)[-1], ix.ema(live, 26)[-1]
            hist, line = f"{bp(h0):+6.1f}->{bp(h1):+6.1f}", f"{bp(f - s):+7.1f}"
        else:
            d0, d1 = rule.value(closes[:-1], closes[-1]), rule.value(closes, m)
            hist, line = f"{bp(d0):+6.1f}->{bp(d1):+6.1f}", "    n/a"
        e50, e200 = ix.ema(live, 50)[-1], ix.ema(live, 200)[-1]
        vr = (sum(vols[-4:]) / 4) / (sum(vols[-52:-4]) / 48) if len(vols) >= 52 else float("nan")
        since = bars_since_opposite(rule, closes, side)
        print(f"{row['symbol']:9s} {row['time_utc']:16s} {row['direction']:5s} {rule.name:10s} {row.get('posted', '?'):>3s}  "
              f"{hist}  {line} {rsi(live):4.0f} {bp(m - e50):+6.0f} {bp(m - e200) if e200 else float('nan'):+6.0f} "
              f"{(m / live[-17] - 1) * 1e4 if len(live) > 17 else 0:+5.0f} {(m / live[-65] - 1) * 1e4 if len(live) > 65 else 0:+5.0f}  "
              f"{vr:4.2f} {since if since is not None else '-':>5}")


if __name__ == "__main__":
    main()
