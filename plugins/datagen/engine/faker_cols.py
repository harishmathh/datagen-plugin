"""Faker-backed columns (names, emails, cities, companies, addresses, ...).

Falls back to lightweight built-in generators if the `faker` package is not
installed, so the engine never hard-fails on a missing optional dependency.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np

_FALLBACK_FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Riya", "Arjun",
                   "Maya", "Liam", "Noah", "Aria", "Kai", "Zoe", "Ravi", "Sara"]
_FALLBACK_LAST = ["Sharma", "Patel", "Khan", "Singh", "Reddy", "Nair", "Bose",
                  "Smith", "Jones", "Garcia", "Mehta", "Iyer", "Das", "Roy"]
_FALLBACK_CITY = ["Mumbai", "Delhi", "Bengaluru", "Pune", "Hyderabad", "Chennai",
                  "Jaipur", "Lucknow", "Indore", "Nagpur", "Surat", "Bhopal"]


def _fallback(provider: str, rng: np.random.Generator, size: int) -> np.ndarray:
    if provider in ("name", "full_name"):
        f = rng.choice(_FALLBACK_FIRST, size)
        l = rng.choice(_FALLBACK_LAST, size)
        return np.array([f"{a} {b}" for a, b in zip(f, l)], dtype=object)
    if provider == "first_name":
        return rng.choice(_FALLBACK_FIRST, size).astype(object)
    if provider == "last_name":
        return rng.choice(_FALLBACK_LAST, size).astype(object)
    if provider in ("city",):
        return rng.choice(_FALLBACK_CITY, size).astype(object)
    if provider == "email":
        f = rng.choice([x.lower() for x in _FALLBACK_FIRST], size)
        num = rng.integers(1, 9999, size)
        return np.array([f"{a}{n}@example.com" for a, n in zip(f, num)], dtype=object)
    if provider in ("company",):
        bases = ["Acme", "Globex", "Initech", "Umbrella", "Stark", "Wayne", "Hooli"]
        suf = ["Ltd", "Inc", "LLC", "Group", "Co"]
        b = rng.choice(bases, size)
        s = rng.choice(suf, size)
        return np.array([f"{x} {y}" for x, y in zip(b, s)], dtype=object)
    if provider == "phone_number":
        return np.array([f"+91-{rng.integers(6,10)}{rng.integers(0,10**9):09d}" for _ in range(size)], dtype=object)
    # generic fallback
    return np.array([f"{provider}_{i}" for i in range(size)], dtype=object)


def generate_faker_column(spec: Dict[str, Any], rng: np.random.Generator, size: int) -> np.ndarray:
    fk = spec["faker"]
    provider = fk["provider"]
    locale = fk.get("locale")
    unique = fk.get("unique", False)

    try:
        from faker import Faker

        # Seed Faker from our rng so output is reproducible under the master seed.
        seed = int(rng.integers(0, 2**31 - 1))
        fake = Faker(locale) if locale else Faker()
        Faker.seed(seed)
        method = getattr(fake, provider)
        if unique:
            method = getattr(fake.unique, provider)
        return np.array([method() for _ in range(size)], dtype=object)
    except Exception:
        return _fallback(provider, rng, size)
