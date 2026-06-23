"""Constraint enforcement.

Each constraint has a boolean `expr` that must hold for every row, and a
`repair` strategy. We evaluate the expression, find violating rows, and apply
the repair. `resample` re-draws the offending columns a bounded number of times;
`clip` is a best-effort numeric clamp parsed from simple comparison exprs;
`drop` removes violating rows; `error` raises.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List

import numpy as np
import pandas as pd

from safe_eval import evaluate

_MAX_RESAMPLE_PASSES = 25


def _violations(expr: str, df: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    mask = evaluate(expr, df, rng)
    if isinstance(mask, pd.Series):
        mask = mask.to_numpy()
    mask = np.asarray(mask, dtype=bool)
    return ~mask  # True where the constraint is violated


def apply_constraints(
    df: pd.DataFrame,
    constraints: List[Dict[str, Any]],
    rng: np.random.Generator,
    resampler: Callable[[pd.DataFrame, np.ndarray], pd.DataFrame] | None = None,
    report: Dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Enforce constraints in order. Returns the repaired DataFrame.

    `resampler(df, mask)` should return a new df with the masked rows
    regenerated; if None, resample falls back to clip/drop heuristics.
    """
    for c in constraints:
        expr = c["expr"]
        repair = c.get("repair", "resample")
        viol = _violations(expr, df, rng)
        n_viol = int(viol.sum())
        if report is not None:
            report.setdefault("constraints", []).append(
                {"expr": expr, "repair": repair, "initial_violations": n_viol}
            )
        if n_viol == 0:
            continue

        if repair == "error":
            raise ValueError(f"Constraint violated by {n_viol} rows: {expr}")

        if repair == "drop":
            df = df.loc[~viol].reset_index(drop=True)
            continue

        if repair == "clip":
            df = _try_clip(expr, df)
            continue

        # resample
        if resampler is not None:
            passes = 0
            while n_viol > 0 and passes < _MAX_RESAMPLE_PASSES:
                df = resampler(df, viol)
                viol = _violations(expr, df, rng)
                n_viol = int(viol.sum())
                passes += 1
            if n_viol > 0:
                # last resort: clip then drop the stubborn rows
                df = _try_clip(expr, df)
                viol = _violations(expr, df, rng)
                df = df.loc[~viol].reset_index(drop=True)
        else:
            df = _try_clip(expr, df)
            viol = _violations(expr, df, rng)
            df = df.loc[~viol].reset_index(drop=True)

        if report is not None:
            report["constraints"][-1]["final_violations"] = int(_violations(expr, df, rng).sum())

    return df


_SIMPLE_CMP = re.compile(r"^\s*([A-Za-z_]\w*)\s*(>=|<=|>|<)\s*(.+?)\s*$")


def _try_clip(expr: str, df: pd.DataFrame) -> pd.DataFrame:
    """Best-effort clip for simple `col >= value` / `col <= value` constraints
    where the right side is a constant or another column expression."""
    m = _SIMPLE_CMP.match(expr)
    if not m:
        return df
    col, op, rhs = m.group(1), m.group(2), m.group(3)
    if col not in df.columns:
        return df
    try:
        # constant rhs
        bound = float(rhs)
        rhs_vals = bound
    except ValueError:
        if rhs in df.columns:
            rhs_vals = df[rhs]
        else:
            return df  # too complex to clip safely
    if op in (">=", ">"):
        df[col] = np.maximum(df[col], rhs_vals)
    else:
        df[col] = np.minimum(df[col], rhs_vals)
    return df
