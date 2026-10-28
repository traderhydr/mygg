#!/usr/bin/env python3
"""Download 15m candles from Hyperliquid's public API into the same CSV layout as template_backtest.py.

The original signals mention a "Hyper" desk, so their prices may come from Hyperliquid, whose last
price differs from Binance by a few basis points. That is enough to flip marginal crosses.

  python3 fetch_hyperliquid.py SUIUSDT ORDIUSDT ATOMUSDT --days 30 --out data_hl
Then:  python3 -m mygg validate signals_v.csv --data tools/data_hl
Standard library only; needs access to api.hyperliquid.xyz.
"""
import argparse, csv, json, os, time, urllib.request

RENAME = {"PEPE": "kPEPE", "SHIB": "kSHIB", "FLOKI": "kFLOKI", "BONK": "kBONK", "1000PEPE": "kPEPE",
          "1000SHIB": "kSHIB", "1000FLOKI": "kFLOKI", "1000BONK": "kBONK"}


def coin(sym):
    base = sym[:-4] if sym.endswith("USDT") else sym
    return RENAME.get(base, base)


def parse(rows):
    """Hyperliquid candle dicts -> [t, o, h, l, c, v] sorted by open time."""
    return sorted([[int(r["t"]), r["o"], r["h"], r["l"], r["c"], r["v"]] for r in rows])


def fetch(sym, days):
    end = int(time.time() * 1000)
    body = json.dumps({"type": "candleSnapshot", "req": {
        "coin": coin(sym), "interval": "15m", "startTime": end - days * 86400000, "endTime": end}}).encode()
    req = urllib.request.Request("https://api.hyperliquid.xyz/info", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return parse(json.load(r))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="+")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default="data_hl")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for sym in a.symbols:
        try:
            rows = fetch(sym, a.days)
        except Exception as ex:
            print(sym, "failed:", ex)
            continue
        with open(f"{a.out}/{sym}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t", "o", "h", "l", "c", "v"])
            w.writerows(rows)
        print(sym, len(rows), "candles")
