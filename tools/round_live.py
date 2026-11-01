#!/usr/bin/env python3
"""Round test at the exact moment: does the live-price flip list at the source's post time match what it posted?

Groups the source's signals (tools/source_signals.csv) into scans (posts less than 90 s apart). For each scan
it fetches 1-minute futures candles for every coin in ./data from the start of the 15m candle up to the scan
time, takes the price at the scan time (the open and the close of the minute that contains it), and asks our
MACD / EMA / BB rules (BB without the squeeze filter) whether they flip against the last closed 15m candle.
Compares with what the source posted in that scan. Needs network (Binance futures); standard library only.
"""
import argparse, csv, datetime as dt, glob, json, os, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mygg.rules import MACDCross, EMACross, BBBreak

BAR = 900000
SCALED = {"PEPEUSDT", "SHIBUSDT", "FLOKIUSDT", "BONKUSDT"}


def load(p):
    with open(p) as f:
        return [(int(r["t"]), float(r["c"])) for r in csv.DictReader(f)]


def minute_bar(sym, t_ms):
    """(open, close) of the 1m candle containing t_ms from Binance futures; None on failure."""
    api = "1000" + sym if sym in SCALED else sym
    q = urllib.parse.urlencode(dict(symbol=api, interval="1m", startTime=t_ms - t_ms % 60000, limit=1))
    for _ in range(3):
        try:
            with urllib.request.urlopen("https://fapi.binance.com/fapi/v1/klines?" + q, timeout=20) as r:
                d = json.load(r)
            if not d:
                return None
            k = 1 / 1000 if sym in SCALED else 1
            return float(d[0][1]) * k, float(d[0][4]) * k
        except Exception:
            time.sleep(1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--source", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_signals.csv"))
    ap.add_argument("--gap", type=int, default=90, help="seconds between posts that still belong to one scan")
    ap.add_argument("--pause", type=float, default=0.05)
    a = ap.parse_args()
    with open(a.source) as f:
        src = list(csv.DictReader(f))
    in_list = {r["symbol"] for r in src}
    coins = {os.path.basename(p)[:-4]: load(p) for p in sorted(glob.glob(os.path.join(a.data, "*.csv")))}
    rules = {"MACD Cross": MACDCross(), "EMA Cross": EMACross(), "BB": BBBreak(squeeze=None)}
    rows = sorted(((int(dt.datetime.strptime(r["time_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()), r)
                   for r in src), key=lambda x: x[0])
    scans, cur = [], []
    for ts, r in rows:
        if cur and ts - cur[-1][0] > a.gap:
            scans.append(cur)
            cur = []
        cur.append((ts, r))
    if cur:
        scans.append(cur)
    T = dict(hit=0, post=0, extra=0, off=0)
    for sc in scans:
        t0 = sc[0][0] * 1000
        cs = t0 - t0 % BAR
        posted = {(r["symbol"], r["rule"]): r["direction"] for _, r in sc}
        flips = {}
        for sym, c in coins.items():
            j = next((k for k in range(len(c)) if c[k][0] == cs), None)
            if j is None or j < 230:
                continue
            bar = minute_bar(sym, t0)
            time.sleep(a.pause)
            if not bar:
                continue
            closes = [x[1] for x in c[:j]]
            for name, rule in rules.items():
                f = [rule.flip(closes, p) for p in bar]
                if 1 in f or -1 in f:
                    flips[(sym, name)] = "long" if 1 in f else "short"
        hit = [k for k, d in posted.items() if flips.get(k) == d]
        miss = [k for k in posted if k not in hit and k[0] in coins]
        extra = [(k, d) for k, d in flips.items() if k not in posted and k[0] in in_list]
        off = [(k, d) for k, d in flips.items() if k[0] not in in_list]
        T["hit"] += len(hit); T["post"] += len(hit) + len(miss); T["extra"] += len(extra); T["off"] += len(off)
        tm = dt.datetime.fromtimestamp(sc[0][0], dt.timezone.utc).strftime("%m-%d %H:%M:%S")
        short = lambda k: f"{k[0][:-4]}:{k[1].split()[0]}"
        print(f"{tm}  posted {len(posted):2d}  found {len(hit):2d}  missed {len(miss):2d}  extra(in list) {len(extra):2d}  off-list {len(off):2d}", flush=True)
        if miss:
            print("      missed: " + " ".join(short(k) for k in miss))
        if extra:
            print("      extra:  " + " ".join(short(k) + ("+" if d == "long" else "-") for k, d in extra))
    print(f"\n{len(scans)} scans. Posted found: {T['hit']}/{T['post']}. Extra flips on listed coins: {T['extra']}; on never-listed coins: {T['off']}.")


if __name__ == "__main__":
    main()
