"""Live scanner on Binance USD-M futures public data (no keys). Paper only: it prints and logs signals."""
import calendar
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
    """Send to your own chats. MYGG_TG_TOKEN is the bot token; MYGG_TG_CHAT is one chat id or several
    separated by commas. A failure on one chat does not stop the others. Never prints the token."""
    token = os.environ.get("MYGG_TG_TOKEN")
    chats = [c.strip() for c in os.environ.get("MYGG_TG_CHAT", "").split(",") if c.strip()]
    if not token or not chats:
        return False
    sent = False
    for chat in chats:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        try:
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=15)
            sent = True
        except Exception as ex:
            print("telegram send failed:", chat, type(ex).__name__, getattr(ex, "code", ""), flush=True)
    return sent


HEADER = "⚡ SABBOT REAL ⚡"


def format_signal(sig):
    """Cornix-readable layout (pair, direction, leverage, entries, targets, stop)."""
    f = template.fmt
    return (f"{HEADER}\n\n"
            f"🪙 Pair: {sig['symbol']}\n"
            f"🧭 Direction: {sig['side'].upper()}\n"
            f"⚙️ Leverage: Cross {sig['leverage']}X\n"
            f"🎯 Entry: {'-'.join(f(p) for p in sig['entries'])}\n"
            f"💰 Take Profits: {'-'.join(f(p) for p in sig['tps'])}\n"
            f"🛑 Stop Loss: {f(sig['stop'])}")


def _restore(log):
    """Rebuild what was already logged so a restart does not repeat signals."""
    seen, last_pub, in_candle = set(), {}, set()
    if not os.path.exists(log):
        return seen, last_pub, in_candle
    with open(log) as f:
        for r in csv.DictReader(f):
            try:
                ms = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
            except (ValueError, KeyError):
                continue
            start, side = ms - ms % BAR_MS, 1 if r["direction"] == "long" else -1
            seen.add((r["symbol"], r["rule"], start, side))
            if r.get("published", "1") != "0":
                k = (r["symbol"], r["rule"], side)
                last_pub[k] = max(last_pub.get(k, 0), start)
                in_candle.add((r["symbol"], start))
    return seen, last_pub, in_candle


def scan(symbols, interval=20, log="mygg_flips.csv", rules=DEFAULT_RULES, once=False, cooldown=4):
    """Log every raw flip; publish (print + Telegram) unless the same coin, rule and direction was
    published within `cooldown` candles, or the coin already has a published signal in this candle (the
    original's batches never repeat a coin). The cooldown is a guess to tune against the original."""
    cache = {}
    heartbeat = os.path.join(os.path.dirname(os.path.abspath(log)), "mygg_heartbeat")
    seen, last_pub, in_candle = _restore(log)
    if not os.path.exists(log):
        with open(log, "w", newline="") as f:
            csv.writer(f).writerow(["time_utc", "symbol", "rule", "direction", "price", "entry1", "stop", "published"])
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
                    if not side or (key, rule.name, start, side) in seen:
                        continue
                    seen.add((key, rule.name, start, side))
                    publish = (start - last_pub.get((key, rule.name, side), -10 ** 15) >= cooldown * BAR_MS
                               and (key, start) not in in_candle)         # one published signal per coin per candle
                    sig = template.build(side, prices[key], ladder=True)
                    sig.update(symbol=key, rule=rule.name, leverage=rule.leverage)
                    if publish:
                        last_pub[(key, rule.name, side)] = start
                        in_candle.add((key, start))
                        text = format_signal(sig)
                        print(text, "\n", flush=True)
                        send_telegram(text)
                    with open(log, "a", newline="") as f:
                        csv.writer(f).writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), key, rule.name,
                                                sig["side"], prices[key], sig["entries"][0], sig["stop"], int(publish)])
        except Exception as ex:                                 # network hiccup: keep going
            print("scan error:", type(ex).__name__, flush=True)
        try:                                                    # proof of life for tools/status.sh
            with open(heartbeat, "w") as f:
                f.write(str(int(time.time())))
        except OSError:
            pass
        if once:
            return
        time.sleep(interval)
