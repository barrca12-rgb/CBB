"""No-vig probabilities for a two-way moneyline (research/moneyline follow-ups). Vectorized; implied probabilities in,
fair (home, away) probabilities out.

  proportional   p_i = pi_i / (pi_home + pi_away)
  power          p_i = pi_i ** k, with k such that the two sum to 1
  shin           Shin (1993): p_i = (sqrt(z^2 + 4 (1 - z) pi_i^2 / B) - z) / (2 (1 - z)), B = pi_home + pi_away,
                 with z (the insider share) such that the two sum to 1
"""
from __future__ import annotations

import numpy as np


def implied(ml):
    ml = np.asarray(ml, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ml > 0, 100 / (ml + 100), -ml / (-ml + 100))


def _bisect(f, lo, hi, n=60):
    lo, hi = np.broadcast_to(lo, f(lo).shape).astype(float).copy(), np.broadcast_to(hi, f(hi).shape).astype(float).copy()
    for _ in range(n):
        mid = (lo + hi) / 2
        pos = f(mid) > 0
        hi = np.where(pos, mid, hi)
        lo = np.where(pos, lo, mid)
    return (lo + hi) / 2


def proportional(ph, pa):
    ph, pa = np.asarray(ph, float), np.asarray(pa, float)
    return ph / (ph + pa), pa / (ph + pa)


def power(ph, pa):
    """k >= 1 with ph**k + pa**k = 1 (sum of implied probabilities above 1); returns (home, away)."""
    ph, pa = np.asarray(ph, float), np.asarray(pa, float)
    # g(k) = ph^k + pa^k - 1 decreases in k; root in [1, 10] when ph + pa > 1
    k = _bisect(lambda k: -(ph ** k + pa ** k - 1), np.ones_like(ph), np.full_like(ph, 10.0))
    return ph ** k, pa ** k


def shin(ph, pa):
    """Shin's method for two outcomes; returns (home, away)."""
    ph, pa = np.asarray(ph, float), np.asarray(pa, float)
    b = ph + pa

    def p(pi, z):
        return (np.sqrt(z ** 2 + 4 * (1 - z) * pi ** 2 / b) - z) / (2 * (1 - z))
    # sum of p falls as z rises; at z = 0 it is sqrt(sum pi^2 / B) * ... >= 1 for b > 1
    z = _bisect(lambda z: -(p(ph, z) + p(pa, z) - 1), np.zeros_like(ph), np.full_like(ph, 0.5))
    h, a = p(ph, z), p(pa, z)
    return h / (h + a), a / (h + a)          # exact normalization (bisection residue)


METHODS = {"shin": shin, "power": power, "proportional": proportional}
