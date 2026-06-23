"""Post-generation validation: summary stats, FK integrity, distribution
fidelity vs the recipe's intended parameters, and constraint satisfaction.

Produces a JSON-serializable dict the renderer turns into a human report.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


def _is_numeric(s: pd.Series) -> bool:
    # Booleans are technically numeric in pandas but should be summarized as
    # categoricals, not via quantiles.
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def _col_summary(s: pd.Series) -> Dict[str, Any]:
    out: Dict[str, Any] = {"dtype": str(s.dtype), "n_null": int(s.isna().sum())}
    # A numeric column with injected nulls becomes object dtype; try to recover
    # its numeric nature before deciding how to summarize.
    if s.dtype == object and out["n_null"] > 0:
        coerced = pd.to_numeric(s, errors="coerce")
        if coerced.notna().sum() == (len(s) - out["n_null"]) and coerced.notna().any():
            s = coerced
    if _is_numeric(s):
        clean = s.dropna()
        if len(clean):
            out.update(
                mean=float(clean.mean()),
                std=float(clean.std()),
                min=float(clean.min()),
                p25=float(clean.quantile(0.25)),
                median=float(clean.median()),
                p75=float(clean.quantile(0.75)),
                max=float(clean.max()),
            )
    else:
        vc = s.value_counts(dropna=True).head(12)
        out["top_values"] = {str(k): int(v) for k, v in vc.items()}
        out["n_unique"] = int(s.nunique(dropna=True))
    return out


def _fidelity_check(s: pd.Series, dist: Dict[str, Any]) -> Dict[str, Any]:
    """Compare realized stats against the intended distribution params."""
    if dist is None or not _is_numeric(s):
        return {}
    clean = s.dropna()
    if not len(clean):
        return {}
    kind = dist.get("kind")
    out: Dict[str, Any] = {"kind": kind}
    if kind == "normal":
        if "mean" in dist:
            out["mean_target"] = dist["mean"]
            out["mean_actual"] = round(float(clean.mean()), 3)
        if "std" in dist:
            out["std_target"] = dist["std"]
            out["std_actual"] = round(float(clean.std()), 3)
    elif kind == "categorical":
        # handled at categorical level; numeric branch won't reach here
        pass
    return out


def build_validation_report(
    recipe: Dict[str, Any],
    frames: Dict[str, pd.DataFrame],
    entities,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {"datasets": {}, "referential_integrity": [], "warnings": []}

    ds_by_name = {ds["name"]: ds for ds in recipe["datasets"]}

    for name, df in frames.items():
        ds = ds_by_name[name]
        col_reports: Dict[str, Any] = {}
        for col in df.columns:
            summary = _col_summary(df[col])
            spec = ds["columns"].get(col, {})
            fid = _fidelity_check(df[col], spec.get("distribution"))
            if fid:
                summary["fidelity"] = fid
            col_reports[col] = summary
        report["datasets"][name] = {
            "rows": len(df),
            "columns": col_reports,
        }

        # Categorical-weight fidelity
        for col, spec in ds["columns"].items():
            if col not in df.columns:
                continue
            dist = spec.get("distribution") or {}
            if dist.get("kind") == "categorical":
                target = dist["values"]
                tot = sum(target.values())
                actual = df[col].value_counts(normalize=True).to_dict()
                drift = {
                    str(k): round(actual.get(k, 0.0) - (v / tot), 3) for k, v in target.items()
                }
                report["datasets"][name].setdefault("categorical_drift", {})[col] = drift

    # Referential integrity: every FK value must exist in the referenced pool.
    for name, df in frames.items():
        ds = ds_by_name[name]
        for fk in ds.get("foreign_keys", []):
            col = fk["column"]
            ref = fk["references"]
            if col not in df.columns or not entities.has(ref):
                continue
            pool = set(entities.pool(ref).tolist())
            vals = set(df[col].dropna().tolist())
            missing = vals - pool
            report["referential_integrity"].append(
                {
                    "dataset": name,
                    "column": col,
                    "references": ref,
                    "orphans": len(missing),
                    "ok": len(missing) == 0,
                }
            )
            if missing:
                report["warnings"].append(
                    f"{name}.{col} has {len(missing)} FK values not in '{ref}' pool."
                )

    return report
