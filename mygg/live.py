"""Live scanner on Binance USD-M futures public data (no keys). Paper only: it prints and logs signals."""
import csv
import json
import os
import time
import urllib.parse
import urllib.request

from . import template
from .rules import DEFAULT_RULES

API = "https://fapi.binance.com/fapi/v1"
BAR_MS = 15 * 60 * 1000
DEFAULT_WATCHLIST = ("BTC ETH SOL BNB XRP DOGE ADA AVAX LINK DOT UNI ATOM LTC AAVE ARB OP APT SUI SEI INJ "
                     "RENDER FET IMX ONDO ENA WLD STRK PYTH JUP ORDI ICP GRT XLM TRX POL KAS WIF").split()


def _get(path, **params):
    url = f"{API}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def send_telegram(text):
    """Send to your own chat if MYGG_TG_TOKEN and MYGG_TG_CHAT are set. Never prints the token."""
    token, chat = os.environ.get("MYGG_TG_TOKEN"), os.environ.get("MYGG_TG_CHAT")
    if not token or not chat:
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=15)
        return True
    except Exception as ex:
        print("telegram send failed:", type(ex).__name__, getattr(ex, "code", ""), flush=True)
        return False


def format_signal(sig):
    arrow = "LONG" if sig["side"] == "long" else "SHORT"
    lo, hi = sig["zone"]
    return (f"MYGG paper signal | #{sig['symbol']} 15M | {sig['rule']}\n"
            f"{arrow} entry zone: {lo}-{hi}\nLeverage: {sig['leverage']}x\n"
            + "".join(f"Target {i + 1}: {p}\n" for i, p in enumerate(sig["tps"]))
            + f"Stop-loss: {sig['stop']}\nPaper trading only, not advice.")


def scan(symbols, interval=20, log="mygg_signals.csv", rules=DEFAULT_RULES, once=False):
    cache, seen = {}, set()
    if not os.path.exists(log):
        with open(log, "w", newline="") as f:
            csv.writer(f).writerow(["time_utc", "symbol", "rule", "direction", "price", "entry1", "stop"])
    while True:
        try:
            now = int(time.time() * 1000)
            prices = {p["symbol"]: float(p["price"]) for p in _get("ticker/price")}
            for sym in symbols:
                key = sym + "USDT"
                if key not in prices:
                    continue
                start = now - now % BAR_MS
                if cache.get(key, (None,))[0] != start:       # new candle: refresh the closed history
                    k = _get("klines", symbol=key, interval="15m", limit=320)
                    cache[key] = (start, [float(x[4]) for x in k if x[0] < start])
                closed = cache[key][1]
                for rule in rules:
                    side = rule.flip(closed, prices[key])
                    ident = (key, rule.name, start, side)
                    if side and ident not in seen:
                        seen.add(ident)
                        sig = template.build(side, prices[key])
                        sig.update(symbol=key, rule=rule.name, leverage=rule.leverage)
                        text = format_signal(sig)
                        print(text, "\n", flush=True)
                        send_telegram(text)
                        with open(log, "a", newline="") as f:
                            csv.writer(f).writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), key, rule.name,
                                                    sig["side"], prices[key], sig["entries"][0], sig["stop"]])
        except Exception as ex:                                 # network hiccup: keep going
            print("scan error:", ex, flush=True)
        if once:
            return
        time.sleep(interval)
