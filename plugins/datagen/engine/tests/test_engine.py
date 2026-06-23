"""Lightweight regression tests for the DataGen engine.

Run with:  python -m pytest tests/  (from the engine/ dir)
or simply: python tests/test_engine.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow either layout
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The engine modules live alongside generate.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib.util


def _load(mod_name):
    path = Path(__file__).resolve().parents[1] / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = m
    spec.loader.exec_module(m)
    return m


distributions = _load("distributions")
safe_eval = _load("safe_eval")
relations = _load("relations")


def test_normal_respects_bounds_and_round():
    rng = np.random.default_rng(0)
    arr = distributions.sample(rng, 5000, {"kind": "normal", "mean": 50, "std": 10, "min": 30, "max": 70, "round": 0})
    assert arr.min() >= 30 and arr.max() <= 70
    assert arr.dtype.kind in ("i",)


def test_categorical_weights():
    rng = np.random.default_rng(0)
    arr = distributions.sample(rng, 20000, {"kind": "categorical", "values": {"A": 0.7, "B": 0.3}})
    frac_a = (arr == "A").mean()
    assert abs(frac_a - 0.7) < 0.02


def test_safe_eval_blocks_attribute_access():
    df = pd.DataFrame({"x": [1, 2, 3]})
    rng = np.random.default_rng(0)
    # Legal expression works
    out = safe_eval.evaluate("x + 1", df, rng)
    assert list(out) == [2, 3, 4]
    # Attribute access / dunder is rejected
    for bad in ["x.__class__", "__import__('os')", "x.values"]:
        try:
            safe_eval.evaluate(bad, df, rng)
            raise AssertionError(f"expected rejection of: {bad}")
        except (ValueError, NameError, AttributeError):
            pass


def test_induced_correlation_direction():
    rng = np.random.default_rng(1)
    anchor = rng.normal(size=5000)
    target = rng.normal(size=5000)
    out = relations.induce_correlation(target, anchor, 0.7, rng)
    rho = np.corrcoef(anchor, out)[0, 1]
    assert rho > 0.55, f"expected strong positive correlation, got {rho}"
    # marginal preserved (same sorted values)
    assert np.allclose(np.sort(out), np.sort(target))


def test_derived_ternary():
    df = pd.DataFrame({"has": [True, False, True], "n": [3, 4, 1]})
    rng = np.random.default_rng(0)
    out = safe_eval.evaluate("where(has, clip(n - 1, 0, 5), 0)", df, rng)
    assert list(np.asarray(out)) == [2, 0, 0]


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'OK' if failures == 0 else f'{failures} FAILURE(S)'}")
    sys.exit(1 if failures else 0)
