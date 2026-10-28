"""Signal levels as fixed percentages of the live price M.

Fitted to the original signals to the last digit (BTC, ENA, ...): the entry zone is M * (1 -/+ 0.15%),
targets sit at +0.75 / 1.7 / 3.2 / 5.8 % of M and the stop at 5 % of M against the trade. For longs
the first entry is the top of the zone (0.15% above the live price), for shorts the bottom.
Relayed versions add two more entries, taken here as fixed fractions below/above entry 1.
"""
ZONE = 0.0015
TPS = (0.0075, 0.017, 0.032, 0.058)
STOP = 0.05
LADDER = (0.0272, 0.0441)


def round_price(p):
    """Heuristic display precision (the originals look exchange-tick rounded)."""
    if p >= 100:
        return round(p, 2)
    if p >= 1:
        return round(p, 3)
    if p >= 0.01:
        return round(p, 5)
    return float(f"{p:.4g}")


def build(side, price, ladder=False):
    """side +1 long / -1 short; price = live price M. Returns zone, entries, targets and stop."""
    at = lambda off: round_price(price * (1 + side * off))
    near, far = at(ZONE), at(-ZONE)
    entries = [near, far]
    if ladder:
        e1 = price * (1 + side * ZONE)
        entries += [round_price(e1 * (1 - side * o)) for o in LADDER]
    return {
        "side": "long" if side > 0 else "short",
        "zone": tuple(sorted((near, far))),
        "entries": entries,
        "tps": [at(t) for t in TPS],
        "stop": at(-STOP),
    }
