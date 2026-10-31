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
                     "RENDER FET IMX ONDO ENA WLD STRK PYTH JUP ORDI ICP GRT XLM TRX POL KAS WIF PEPE SHIB FLOKI BONK").split()

# Binance quotes these as 1000x contracts (1000PEPEUSDT ~ 0.004). The signals show the plain price (~4e-06).
SCALED = {"PEPE", "SHIB", "FLOKI", "BONK"}
SCALE = 1000


def market(sym):
    """(Binance symbol, price divisor) for a coin like PEPE or BTC."""
    return (f"{SCALE}{sym}USDT", SCALE) if sym in SCALED else (f"{sym}USDT", 1)


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


def strategy_label(rule, side):
    """Name shown in the message, as the original labels them."""
    if rule == "BB":
        return "BB Breakout" if side == "long" else "BB Breakdown"
    return rule


def format_signal(sig):
    """Cornix-readable layout (pair, direction, leverage, entries, targets, stop)."""
    f = template.fmt
    return (f"{HEADER}\n\n"
            f"🧠 Strategy: {strategy_label(sig['rule'], sig['side'])}\n"
            f"🪙 Pair: {sig['symbol']}\n"
            f"🧭 Direction: {sig['side'].upper()}\n"
            f"⚙️ Leverage: Cross {sig['leverage']}X\n"
            f"🎯 Entry: {'-'.join(f(p) for p in sig['entries'])}\n"
            f"💰 Take Profits: {'-'.join(f(p) for p in sig['tps'])}\n"
            f"🛑 Stop Loss: {f(sig['stop'])}")


def _cooldown_key(sym, rule, side, scope):
    return {"rule": (sym, rule, side), "dir": (sym, side), "coin": (sym,)}[scope]


def _restore(log, scope="rule"):
    """Rebuild what was already logged so a restart does not repeat signals or exceed the hourly cap."""
    seen, last_pub, in_candle, hours = set(), {}, set(), {}
    if not os.path.exists(log):
        return seen, last_pub, in_candle, hours
    with open(log) as f:
        for r in csv.DictReader(f):
            try:
                ms = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
            except (ValueError, KeyError):
                continue
            start, side = ms - ms % BAR_MS, 1 if r["direction"] == "long" else -1
            seen.add((r["symbol"], r["rule"], start, side))
            if r.get("published", "1") != "0":
                k = _cooldown_key(r["symbol"], r["rule"], side, scope)
                last_pub[k] = max(last_pub.get(k, 0), start)
                in_candle.add((r["symbol"], start))
                hours[ms // 3600000] = hours.get(ms // 3600000, 0) + 1
    return seen, last_pub, in_candle, hours


def scan(symbols, interval=20, log="mygg_flips.csv", rules=DEFAULT_RULES, once=False, cooldown=4,
         cooldown_scope="rule", max_per_hour=0):
    """Log every raw flip; publish (print + Telegram) unless the same coin, rule and direction was
    published within `cooldown` candles, or the coin already has a published signal in this candle (the
    original's batches never repeat a coin). The cooldown is a guess to tune against the original.
    cooldown_scope: "rule" (coin+rule+direction, the default), "dir" (coin+direction, any rule) or "coin".
    max_per_hour: cap on published signals per UTC hour (0 = no cap)."""
    cache = {}
    heartbeat = os.path.join(os.path.dirname(os.path.abspath(log)), "mygg_heartbeat")
    seen, last_pub, in_candle, hours = _restore(log, cooldown_scope)
    if not os.path.exists(log):
        with open(log, "w", newline="") as f:
            csv.writer(f).writerow(["time_utc", "symbol", "rule", "direction", "price", "entry1", "stop", "published"])
    while True:
        try:
            now = int(time.time() * 1000)
            prices = {p["symbol"]: float(p["price"]) for p in _get("ticker/price")}
            for sym in symbols:
                api, scale = market(sym)
                key = sym + "USDT"                              # the name shown in signals and the log
                if api not in prices:
                    continue
                start = now - now % BAR_MS
                if cache.get(key, (None,))[0] != start:       # new candle: refresh the closed history
                    k = _get("klines", symbol=api, interval="15m", limit=320)
                    cache[key] = (start, [float(x[4]) for x in k if x[0] < start])
                closed = cache[key][1]
                price = prices[api] / scale
                for rule in rules:
                    side = rule.flip(closed, prices[api])       # indicator signs do not depend on the scale
                    if not side or (key, rule.name, start, side) in seen:
                        continue
                    seen.add((key, rule.name, start, side))
                    ck = _cooldown_key(key, rule.name, side, cooldown_scope)
                    hour = now // 3600000
                    publish = (start - last_pub.get(ck, -10 ** 15) >= cooldown * BAR_MS
                               and (key, start) not in in_candle           # one published signal per coin per candle
                               and (not max_per_hour or hours.get(hour, 0) < max_per_hour))
                    sig = template.build(side, price, ladder=True)
                    sig.update(symbol=key, rule=rule.name, leverage=rule.leverage)
                    if publish:
                        last_pub[ck] = start
                        in_candle.add((key, start))
                        hours[hour] = hours.get(hour, 0) + 1
                        text = format_signal(sig)
                        print(text, "\n", flush=True)
                        send_telegram(text)
                    with open(log, "a", newline="") as f:
                        csv.writer(f).writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), key, rule.name,
                                                sig["side"], price, sig["entries"][0], sig["stop"], int(publish)])
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
