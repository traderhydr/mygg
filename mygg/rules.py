"""Entry rules. Each rule gives a number d(closed, live) whose sign is the state.

A signal fires on the forming candle when the sign flips between the last closed candle
(live = last close) and the live price. d is affine in the live price for MACD and EMA rules,
so the exact price where it crosses zero can be solved (trigger_price).
"""
from . import indicators as ix

LEVERAGE = {"MACD Cross": 25, "EMA Cross": 15, "BB": 20}


class Rule:
    name = ""
    leverage = 0
    min_history = 35

    def value(self, closed, live):
        raise NotImplementedError

    def flip(self, closed, live):
        """+1 bullish flip, -1 bearish flip, 0 none, comparing the last closed state with live."""
        if len(closed) < self.min_history:
            return 0
        d0 = self.value(closed[:-1], closed[-1])
        d1 = self.value(closed, live)
        if d0 is None or d1 is None:
            return 0
        return 1 if d0 <= 0 < d1 else -1 if d0 >= 0 > d1 else 0

    def trigger_price(self, closed):
        """Live price at which d crosses zero (affine rules). None if flat."""
        p0 = closed[-1]
        d0, d1 = self.value(closed, p0), self.value(closed, p0 * 1.01)
        if d0 is None or d1 is None or d1 == d0:
            return None
        return p0 - d0 * (p0 * 0.01) / (d1 - d0)


class MACDCross(Rule):
    name, leverage = "MACD Cross", LEVERAGE["MACD Cross"]

    def __init__(self, fast=12, slow=26, sig=9):
        self.fast, self.slow, self.sig = fast, slow, sig

    def value(self, closed, live):
        return ix.macd_hist(closed + [live], self.fast, self.slow, self.sig)


class EMACross(Rule):
    name, leverage = "EMA Cross", LEVERAGE["EMA Cross"]

    def __init__(self, fast=9, slow=21):
        self.fast, self.slow = fast, slow

    def value(self, closed, live):
        return ix.ema_diff(closed + [live], self.fast, self.slow)


class BBBreak(Rule):
    """Placeholder: price beyond the band of the previous n closes. Parameters not confirmed."""
    name, leverage = "BB", LEVERAGE["BB"]

    def __init__(self, n=20, dev=2.0):
        self.n, self.dev = n, dev

    def value(self, closed, live):
        """Positive above the upper band, negative below the lower band, zero inside."""
        if len(closed) < self.n:
            return None
        lo, _, up = ix.bollinger(closed, self.n, self.dev)
        return live - up if live > up else live - lo if live < lo else 0.0

    def flip(self, closed, live):
        if len(closed) < self.n + 1:
            return 0
        d0 = self.value(closed[:-1], closed[-1])
        d1 = self.value(closed, live)
        return 1 if d1 > 0 >= d0 else -1 if d1 < 0 <= d0 else 0

    def trigger_price(self, closed):
        return None


DEFAULT_RULES = (MACDCross(), EMACross(), BBBreak())
