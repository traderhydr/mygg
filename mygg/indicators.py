"""Indicators on plain lists of floats. EMAs are seeded with the SMA of the first n values."""
import statistics as st


def ema(values, n):
    k, out, e = 2 / (n + 1), [None] * len(values), None
    for i, x in enumerate(values):
        if i == n - 1:
            e = sum(values[:n]) / n
        elif i >= n:
            e = x * k + e * (1 - k)
        if i >= n - 1:
            out[i] = e
    return out


def macd_hist(closes, fast=12, slow=26, sig=9):
    """Histogram of the last point only (fast EMA - slow EMA - signal EMA)."""
    f, s = ema(closes, fast), ema(closes, slow)
    line = [a - b for a, b in zip(f, s) if a is not None and b is not None]
    if len(line) < sig:
        return None
    return line[-1] - ema(line, sig)[-1]


def ema_diff(closes, fast=9, slow=21):
    f, s = ema(closes, fast)[-1], ema(closes, slow)[-1]
    return None if f is None or s is None else f - s


def bollinger(closes, n=20, dev=2.0):
    """(lower, mean, upper) of the last n closes, population stdev."""
    w = closes[-n:]
    m, sd = st.mean(w), st.pstdev(w)
    return m - dev * sd, m, m + dev * sd
