#!/usr/bin/env python3
"""Baseline test for the fixed-percentage signal template.

fetch    download 15m futures candles into ./data (Binance, Bybit fallback)
baseline simulate "enter at market + template ladder" at random times and
         directions, so the AI's pair/direction picks can be compared to chance
score    run the same simulator on your own signals (csv: symbol,time_utc,direction[,entry])

Standard library only. Intrabar order is unknown on 15m candles, so every result
is shown twice: "pess" (adverse moves first) and "opt" (favourable moves first).
The truth lies between them.
"""
import argparse, csv, datetime as dt, json, os, random, statistics as st
import urllib.parse, urllib.request

DATA = "data"
ENTRY_OFF = [0.0, 0.0030, 0.0272, 0.0441]   # distance from entry 1, against the trade
ENTRY_W = [0.50, 0.25, 0.15, 0.10]
STOP_OFF = 0.0515
TP_OFF = [0.0060, 0.0155, 0.0304, 0.0564]    # distance from entry 1, with the trade
TP_W = [0.65, 0.15, 0.10, 0.10]
DEFAULT_SYMBOLS = ("BTCUSDT ETHUSDT SOLUSDT DOTUSDT ENAUSDT ICPUSDT ORDIUSDT ADAUSDT XRPUSDT "
                   "DOGEUSDT AVAXUSDT LINKUSDT NEARUSDT SUIUSDT APTUSDT").split()


def get(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=30) as r:
        return json.load(r)


def binance(sym, s, e):
    d = get("https://fapi.binance.com/fapi/v1/klines",
            dict(symbol=sym, interval="15m", startTime=s, endTime=e, limit=1500))
    return [[k[0], k[1], k[2], k[3], k[4], k[5]] for k in d]


def bybit(sym, s, e):
    d = get("https://api.bybit.com/v5/market/kline",
            dict(category="linear", symbol=sym, interval="15", start=s, end=e, limit=1000))
    return [[int(k[0])] + k[1:6] for k in reversed(d["result"]["list"])]


def fetch(symbols, days):
    os.makedirs(DATA, exist_ok=True)
    end = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    for sym in symbols:
        rows, cur = [], end - days * 86400000
        for fn in (binance, bybit):
            try:
                rows, cur = [], end - days * 86400000
                while cur < end:
                    chunk = fn(sym, cur, end)
                    if not chunk:
                        break
                    rows += chunk
                    cur = int(chunk[-1][0]) + 900000
                break
            except Exception as ex:
                print(sym, fn.__name__, "failed:", ex)
                rows = []
        with open(f"{DATA}/{sym}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t", "o", "h", "l", "c", "v"])
            w.writerows(rows)
        print(sym, len(rows), "candles")


def load(sym):
    with open(f"{DATA}/{sym}.csv") as f:
        r = csv.DictReader(f)
        return [(int(x["t"]), float(x["o"]), float(x["h"]), float(x["l"]), float(x["c"])) for x in r]


def simulate(c, i, side, p1, lev, fee, mode, horizon):
    """Trade opens at p1 (entry 1 filled) after candle i. side = +1 long, -1 short."""
    entries = [p1 * (1 - side * o) for o in ENTRY_OFF]
    stop = p1 * (1 - side * STOP_OFF)
    tps = [p1 * (1 + side * t) for t in TP_OFF]
    qty = ENTRY_W[0]
    avg = p1
    filled = [True, False, False, False]
    hit = [False] * 4
    max_qty, entered, exited, realized, mae = qty, qty, 0.0, 0.0, 0.0
    be, reason = False, None

    def adv(k, price):   # did the candle trade at/through price against the trade?
        return c[k][3] <= price if side > 0 else c[k][2] >= price

    def fav(k, price):
        return c[k][2] >= price if side > 0 else c[k][3] <= price

    def close(q, price):
        nonlocal qty, realized, exited
        realized += q * side * (price - avg) / avg
        exited += q
        qty -= q

    last = min(len(c) - 1, i + horizon)
    for k in range(i + 1, last + 1):
        def fills():
            nonlocal qty, avg, entered, max_qty
            for j in (1, 2, 3):
                if not filled[j] and adv(k, entries[j]):
                    filled[j] = True
                    avg = (avg * qty + entries[j] * ENTRY_W[j]) / (qty + ENTRY_W[j])
                    qty += ENTRY_W[j]
                    entered += ENTRY_W[j]
                    max_qty = max(max_qty, qty)

        def stop_hit():
            nonlocal reason
            if qty > 1e-12 and adv(k, stop):
                close(qty, stop)
                reason = "breakeven" if be else "stop"
                return True

        def tp_step():
            nonlocal be, stop, reason
            for j in range(4):
                if not hit[j] and fav(k, tps[j]):
                    left = sum(TP_W[m] for m in range(4) if not hit[m])
                    close(qty * TP_W[j] / left, tps[j])
                    hit[j] = True
                    if j == 0:
                        be, stop = True, avg
            if qty <= 1e-12:
                reason = "tp_all"

        if mode == "pess":
            fills()
            if stop_hit():
                break
            tp_step()
        else:
            tp_step()
            if reason:
                break
            fills()
            if stop_hit():
                break
        if reason:
            break
        worst = c[k][3] if side > 0 else c[k][2]
        mae = min(mae, side * (worst - avg) / avg * lev)
    if not reason:
        reason = "open"
        close(qty, c[last][4])
    fees = fee * (entered + exited)
    return dict(roe=lev * (realized - fees) / max_qty, tp1=hit[0], reason=reason, mae=mae, qty=max_qty)


def summarize(name, rs):
    if not rs:
        print(name, "no trades")
        return
    roes = [r["roe"] for r in rs]
    wins = [x for x in roes if x > 0]
    loss = [x for x in roes if x <= 0]
    n = len(rs)
    pf = (sum(wins) / -sum(loss)) if loss and sum(loss) < 0 else float("inf")
    cnt = lambda key: sum(1 for r in rs if r["reason"] == key) / n
    print(f"{name:5s} n={n:5d} tp1={sum(r['tp1'] for r in rs)/n:6.1%} stop={cnt('stop'):6.1%} "
          f"be={cnt('breakeven'):6.1%} open={cnt('open'):5.1%} win={len(wins)/n:6.1%} "
          f"mean_roe={st.mean(roes):7.2%} med={st.median(roes):7.2%} "
          f"avg_win={(st.mean(wins) if wins else 0):7.2%} avg_loss={(st.mean(loss) if loss else 0):8.2%} "
          f"pf={pf:5.2f} worst={min(roes):8.2%} mae<=-95%={sum(r['mae']<=-0.95 for r in rs)/n:5.1%}")


def run(trades, lev, fee, horizon, title):
    print(f"\n{title}  (lev={lev}x, fee={fee:.4%}/side, horizon={horizon//96}d; roe is on margin used)")
    for mode in ("pess", "opt"):
        rs = [simulate(c, i, side, p1, lev, fee, mode, horizon) for c, i, side, p1 in trades]
        summarize(mode, rs)


def baseline(symbols, per, lev, fee, horizon, seed):
    rng = random.Random(seed)
    trades = []
    for sym in symbols:
        try:
            c = load(sym)
        except FileNotFoundError:
            print("missing", sym)
            continue
        if len(c) < horizon + 100:
            print("too short", sym, len(c))
            continue
        for _ in range(per):
            i = rng.randrange(50, len(c) - horizon - 1)
            trades.append((c, i, rng.choice((1, -1)), c[i][4]))
    run(trades, lev, fee, horizon, f"BASELINE random time + random direction, {len(trades)} trades")
    for s, name in ((1, "LONG only"), (-1, "SHORT only")):
        run([t for t in trades if t[2] == s], lev, fee, horizon, f"BASELINE {name}")


def score(path, lev, fee, horizon):
    trades = []
    with open(path) as f:
        for row in csv.DictReader(f):
            c = load(row["symbol"])
            t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                    .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            i = max(k for k in range(len(c)) if c[k][0] <= t)
            side = 1 if row["direction"].strip().lower() == "long" else -1
            p1 = float(row["entry"]) if row.get("entry") else c[i][4]
            trades.append((c, i, side, p1))
    run(trades, lev, fee, horizon, f"YOUR SIGNALS, {len(trades)} trades")


def selftest():
    """ENA 28 Oct 2026: entry 1 0.20852, long, 20x. Expect E2, TP1, TP2, breakeven."""
    rows = [(0, .20671, .20898, .20654, .20797), (1, .20796, .20999, .20737, .20970),
            (2, .20971, .21210, .20865, .21015), (3, .21016, .21041, .20811, .20812),
            (4, .20812, .20825, .20590, .20638), (5, .20639, .20661, .20517, .20560)]
    r = simulate(rows, 0, 1, 0.20852, 20, 0.0005, "pess", 10)
    assert r["reason"] == "breakeven" and r["tp1"], r
    print("selftest ok:", r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "baseline", "score", "selftest"])
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--per", type=int, default=200, help="random trades per symbol")
    ap.add_argument("--lev", type=float, default=20)
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--horizon-days", type=int, default=7)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--signals", default="signals.csv")
    a = ap.parse_args()
    h = a.horizon_days * 96
    if a.cmd == "fetch":
        fetch(a.symbols, a.days)
    elif a.cmd == "baseline":
        baseline(a.symbols, a.per, a.lev, a.fee, h, a.seed)
    elif a.cmd == "score":
        score(a.signals, a.lev, a.fee, h)
    else:
        selftest()
