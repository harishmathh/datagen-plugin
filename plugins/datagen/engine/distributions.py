"""Distribution samplers for the DataGen engine.

Every sampler takes a numpy Generator (for reproducibility) and a size, plus
distribution-specific parameters, and returns a numpy array of length `size`.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict

import numpy as np


def _clip(arr: np.ndarray, dist: Dict[str, Any]) -> np.ndarray:
    lo = dist.get("min")
    hi = dist.get("max")
    if lo is not None or hi is not None:
        arr = np.clip(arr, lo if lo is not None else -np.inf, hi if hi is not None else np.inf)
    return arr


def _round(arr: np.ndarray, dist: Dict[str, Any]) -> np.ndarray:
    r = dist.get("round")
    if r is not None:
        arr = np.round(arr, r)
        if r == 0:
            arr = arr.astype("int64")
    return arr


def sample_numeric(rng: np.random.Generator, size: int, dist: Dict[str, Any]) -> np.ndarray:
    kind = dist["kind"]

    if kind == "normal":
        arr = rng.normal(dist.get("mean", 0.0), dist.get("std", 1.0), size)
    elif kind == "lognormal":
        # Parameterized by the mean/std of the *underlying* normal if given,
        # otherwise derive sensible logspace params from a target mean/std.
        if "mean" in dist and "std" in dist and dist.get("logspace", True) is False:
            mu, sigma = dist["mean"], dist["std"]
            m = np.log(mu**2 / np.sqrt(sigma**2 + mu**2))
            s = np.sqrt(np.log(1 + (sigma**2) / (mu**2)))
            arr = rng.lognormal(m, s, size)
        else:
            arr = rng.lognormal(dist.get("mean", 0.0), dist.get("std", 1.0), size)
    elif kind == "uniform":
        arr = rng.uniform(dist.get("min", 0.0), dist.get("max", 1.0), size)
    elif kind == "uniform_int":
        arr = rng.integers(int(dist.get("min", 0)), int(dist.get("max", 100)) + 1, size)
    elif kind == "exponential":
        scale = dist.get("scale", 1.0 / dist["lam"] if "lam" in dist else 1.0)
        arr = rng.exponential(scale, size)
    elif kind == "poisson":
        arr = rng.poisson(dist.get("lam", 1.0), size)
    elif kind == "beta":
        arr = rng.beta(dist.get("alpha", 2.0), dist.get("beta", 2.0), size)
        # Optionally rescale a [0,1] beta into [min,max]
        if "min" in dist or "max" in dist:
            lo, hi = dist.get("min", 0.0), dist.get("max", 1.0)
            arr = lo + arr * (hi - lo)
    elif kind == "gamma":
        arr = rng.gamma(dist.get("shape", 2.0), dist.get("scale", 1.0), size)
    elif kind == "pareto":
        arr = (rng.pareto(dist.get("alpha", 2.0), size) + 1) * dist.get("scale", 1.0)
    elif kind == "zipf":
        arr = rng.zipf(dist.get("s", 2.0), size).astype("float64")
    elif kind == "constant":
        arr = np.full(size, dist["value"])
    else:
        raise ValueError(f"Unknown numeric distribution kind: {kind}")

    arr = _clip(arr, dist)
    arr = _round(arr, dist)
    return arr


def sample_bernoulli(rng: np.random.Generator, size: int, dist: Dict[str, Any]) -> np.ndarray:
    return rng.random(size) < dist.get("p", 0.5)


def sample_categorical(rng: np.random.Generator, size: int, dist: Dict[str, Any]) -> np.ndarray:
    values = dist["values"]
    cats = list(values.keys())
    weights = np.array([float(values[c]) for c in cats], dtype="float64")
    weights = weights / weights.sum()
    idx = rng.choice(len(cats), size=size, p=weights)
    return np.array(cats, dtype=object)[idx]


def _parse_date(s: str) -> _dt.datetime:
    return _dt.datetime.fromisoformat(s)


def sample_datetime(rng: np.random.Generator, size: int, dist: Dict[str, Any]) -> np.ndarray:
    start = _parse_date(dist.get("start", "2023-01-01"))
    end = _parse_date(dist.get("end", "2024-12-31"))
    span = (end - start).total_seconds()

    if dist["kind"] == "datetime_uniform":
        offsets = rng.uniform(0, span, size)
    elif dist["kind"] == "datetime_seasonal":
        # Build a per-day weight curve over the span, then sample days, then a
        # uniform time within the chosen day.
        seasonality = dist.get("seasonality", {})
        monthly = seasonality.get("monthly", [1.0] * 12)
        weekday = seasonality.get("weekday", [1.0] * 7)
        n_days = max(1, int(span // 86400) + 1)
        days = [start + _dt.timedelta(days=i) for i in range(n_days)]
        day_weights = np.array(
            [monthly[d.month - 1] * weekday[d.weekday()] for d in days], dtype="float64"
        )
        day_weights /= day_weights.sum()
        chosen = rng.choice(n_days, size=size, p=day_weights)
        intra = rng.uniform(0, 86400, size)
        offsets = chosen * 86400.0 + intra
        offsets = np.clip(offsets, 0, span)
    else:
        raise ValueError(f"Unknown datetime kind: {dist['kind']}")

    base = np.datetime64(start)
    return base + offsets.astype("timedelta64[s]")


def sample(rng: np.random.Generator, size: int, dist: Dict[str, Any]) -> np.ndarray:
    """Dispatch on distribution kind."""
    kind = dist["kind"]
    if kind == "bernoulli":
        return sample_bernoulli(rng, size, dist)
    if kind == "categorical":
        return sample_categorical(rng, size, dist)
    if kind in ("datetime_uniform", "datetime_seasonal"):
        return sample_datetime(rng, size, dist)
    return sample_numeric(rng, size, dist)
