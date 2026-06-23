"""Cross-column relationships: induced correlation and outlier injection."""
from __future__ import annotations

from typing import Any, Dict

import numpy as np


def induce_correlation(
    target: np.ndarray, anchor: np.ndarray, rho: float, rng: np.random.Generator
) -> np.ndarray:
    """Return a reordered/blended version of `target` that has approximately
    Pearson correlation `rho` with `anchor`, while preserving target's marginal
    distribution as closely as possible.

    Uses the standard Gaussian-copula trick: build a latent variable correlated
    with the anchor's ranks, then reorder target's sorted values by that latent.
    """
    n = len(target)
    if n < 3:
        return target

    # Rank-transform the anchor to standard normal scores.
    anchor_ranks = np.argsort(np.argsort(anchor))
    u = (anchor_ranks + 0.5) / n
    z_anchor = _norm_ppf(u)

    noise = rng.normal(size=n)
    # Latent correlated with z_anchor at level rho.
    latent = rho * z_anchor + np.sqrt(max(0.0, 1 - rho**2)) * noise

    # Reorder target's values to match the latent ordering.
    target_sorted = np.sort(target)
    order = np.argsort(np.argsort(latent))
    return target_sorted[order]


def _norm_ppf(p: np.ndarray) -> np.ndarray:
    """Inverse normal CDF (Acklam's algorithm) — avoids a scipy dependency."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p = np.clip(p, 1e-12, 1 - 1e-12)
    plow, phigh = 0.02425, 1 - 0.02425
    out = np.empty_like(p)

    lo = p < plow
    q = np.sqrt(-2 * np.log(p[lo]))
    out[lo] = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
              ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

    hi = p > phigh
    q = np.sqrt(-2 * np.log(1 - p[hi]))
    out[hi] = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

    mid = ~(lo | hi)
    q = p[mid] - 0.5
    r = q * q
    out[mid] = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    return out


def inject_outliers(
    arr: np.ndarray, spec: Dict[str, Any], rng: np.random.Generator
) -> np.ndarray:
    frac = spec.get("fraction", 0.0)
    if frac <= 0:
        return arr
    arr = arr.astype("float64", copy=True)
    n = len(arr)
    k = max(1, int(round(frac * n)))
    idx = rng.choice(n, size=k, replace=False)
    kind = spec.get("kind", "both")
    mag = spec.get("magnitude", 4.0)
    std = np.nanstd(arr) or 1.0
    for i in idx:
        direction = rng.choice([-1, 1]) if kind == "both" else (1 if kind == "high" else -1)
        arr[i] = arr[i] + direction * mag * std
    return arr
