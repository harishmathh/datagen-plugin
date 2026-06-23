"""DataGen generation engine — CLI entrypoint.

Reads a recipe.yaml, builds every dataset deterministically (seeded), enforces
constraints, links tables via shared entity pools, fills LLM/Faker columns, and
writes CSVs plus a validation report.

Usage:
    python generate.py --recipe recipe.yaml --out outputs/run/ [--rows-scale 1.0]
                       [--only customers,spendings] [--offline] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# Allow running as a plain script (engine/ on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import constraints as _constraints  # noqa: E402
import distributions as _dist  # noqa: E402
import faker_cols  # noqa: E402
import llm_text  # noqa: E402
import relations  # noqa: E402
from recipe import generation_order, load_recipe  # noqa: E402
from safe_eval import evaluate  # noqa: E402
from tables import EntityPools  # noqa: E402
from validate import build_validation_report  # noqa: E402


def _derive_seed(master: int, *parts: str) -> int:
    h = master
    for p in parts:
        for ch in p:
            h = (h * 1000003 + ord(ch)) & 0xFFFFFFFF
    return h & 0x7FFFFFFF


def _resolve_rows(rows_spec, entities: EntityPools, ds_name: str, rows_scale: float) -> int:
    if isinstance(rows_spec, str) and rows_spec.startswith("per:"):
        body = rows_spec[len("per:"):]
        mult = 1.0
        if "*" in body:
            ent, m = body.split("*", 1)
            mult = float(m)
        else:
            ent = body
        base = entities.count(ent.strip())
        return max(1, int(round(base * mult * rows_scale)))
    if rows_spec is None:
        return 0
    return max(1, int(round(int(rows_spec) * rows_scale)))


def _apply_nullable(arr: np.ndarray, frac: float, rng: np.random.Generator) -> np.ndarray:
    if not frac:
        return arr
    arr = arr.astype(object)
    mask = rng.random(len(arr)) < frac
    arr[mask] = None
    return arr


def _generate_column(
    col_name: str,
    spec: Dict[str, Any],
    df: pd.DataFrame,
    rng: np.random.Generator,
    n: int,
    entities: EntityPools,
    cache_dir: Path,
    offline: bool,
) -> np.ndarray:
    ctype = spec["type"]

    if ctype in ("numeric", "integer"):
        arr = _sample_with_conditionals(spec, df, rng, n)
        if spec.get("correlate_with"):
            cw = spec["correlate_with"]
            anchor = df[cw["column"]].to_numpy(dtype="float64")
            arr = relations.induce_correlation(arr.astype("float64"), anchor, cw["rho"], rng)
        if spec.get("outliers"):
            arr = relations.inject_outliers(arr, spec["outliers"], rng)
        if ctype == "integer":
            arr = np.round(arr).astype("int64")

    elif ctype in ("categorical", "boolean"):
        arr = _sample_with_conditionals(spec, df, rng, n)

    elif ctype in ("datetime", "date"):
        arr = _dist.sample(rng, n, spec["distribution"])
        if ctype == "date":
            arr = arr.astype("datetime64[D]")

    elif ctype == "derived":
        result = evaluate(spec["expr"], df, rng)
        arr = np.asarray(result)
        if arr.ndim == 0:
            arr = np.full(n, arr)

    elif ctype == "faker":
        arr = faker_cols.generate_faker_column(spec, rng, n)

    elif ctype == "text":
        arr = llm_text.generate_text_column(df, spec, rng, cache_dir, offline=offline)

    else:
        raise ValueError(f"Unsupported column type '{ctype}' for column '{col_name}'.")

    arr = _apply_nullable(arr, spec.get("nullable", 0.0), rng)
    return arr


def _sample_with_conditionals(spec, df, rng, n) -> np.ndarray:
    """Sample a column that may have conditional distributions keyed on other
    already-generated columns. Rows not matching any `when` use the base
    `distribution`."""
    conds = spec.get("conditional")
    if not conds:
        return _dist.sample(rng, n, spec["distribution"])

    out = np.empty(n, dtype=object)
    assigned = np.zeros(n, dtype=bool)
    for cond in conds:
        mask = evaluate(cond["when"], df, rng)
        mask = np.asarray(mask.to_numpy() if isinstance(mask, pd.Series) else mask, dtype=bool)
        mask = mask & ~assigned
        k = int(mask.sum())
        if k:
            out[mask] = _dist.sample(rng, k, cond["distribution"])
            assigned |= mask
    rest = ~assigned
    k = int(rest.sum())
    if k:
        base = spec.get("distribution")
        if base is None:
            raise ValueError("Conditional column needs a base `distribution` for unmatched rows.")
        out[rest] = _dist.sample(rng, k, base)
    # Try to give a clean dtype back if everything is numeric.
    try:
        return out.astype("float64")
    except (ValueError, TypeError):
        return out


def generate_dataset(
    ds: Dict[str, Any],
    recipe: Dict[str, Any],
    entities: EntityPools,
    out_dir: Path,
    rows_scale: float,
    offline: bool,
    report: Dict[str, Any],
    frames: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    name = ds["name"]
    master = int(recipe["meta"]["seed"])
    seed = _derive_seed(master, name)
    rng = np.random.default_rng(seed)
    cache_dir = out_dir / ".cache" / name

    rows_spec = ds.get("rows")
    if rows_spec is None and ds.get("primary_entity"):
        n = entities.count(ds["primary_entity"])
        n = max(1, int(round(n * rows_scale)))
    else:
        n = _resolve_rows(rows_spec, entities, name, rows_scale)

    df = pd.DataFrame(index=range(n))

    # Inject the primary entity key (1:1, in pool order, truncated/sampled to n).
    primary_key = None
    if ds.get("primary_entity"):
        ent = ds["primary_entity"]
        primary_key = entities.key_of(ent)
        pool = entities.pool(ent)
        if n <= len(pool):
            df[primary_key] = pool[:n]
        else:
            df[primary_key] = pool[rng.integers(0, len(pool), size=n)]

    # Inject foreign keys (many:1).
    for fk in ds.get("foreign_keys", []):
        df[fk["column"]] = entities.sample_fk(fk["references"], n, rng)

    # Inherit columns from sibling tables sharing this primary key (e.g. pull
    # `segment` from `customers` so `spendings` can condition on it).
    inherited_cols: set[str] = set()
    for inh in ds.get("inherit", []):
        src_name = inh["from"]
        src = frames.get(src_name)
        if src is None:
            raise ValueError(
                f"Dataset '{name}' inherits from '{src_name}', which has not been generated yet. "
                "Order matters: list the source dataset earlier in the recipe."
            )
        if primary_key is None or primary_key not in src.columns:
            raise ValueError(
                f"Dataset '{name}' can only inherit from a sibling sharing its primary key "
                f"'{primary_key}'; '{src_name}' does not expose it."
            )
        cols = inh["columns"]
        joined = df.merge(
            src[[primary_key] + cols], on=primary_key, how="left", suffixes=("", "_inh")
        )
        for c in cols:
            df[c] = joined[c].to_numpy()
            if not inh.get("keep", False):
                inherited_cols.add(c)

    # Generate the rest in dependency order.
    order = generation_order(ds["columns"])
    for col_name in order:
        spec = ds["columns"][col_name]
        col_rng = np.random.default_rng(_derive_seed(master, name, col_name))
        df[col_name] = _generate_column(
            col_name, spec, df, col_rng, n, entities, cache_dir, offline
        )

    # Constraints with a resampler that re-draws independent (non-key) columns
    # for the violating rows.
    def resampler(frame: pd.DataFrame, mask: np.ndarray) -> pd.DataFrame:
        idx = np.where(mask)[0]
        sub_rng = np.random.default_rng(_derive_seed(master, name, "resample", str(len(idx))))
        for col_name in order:
            spec = ds["columns"][col_name]
            if spec.get("type") in ("text", "faker", "id"):
                continue  # don't churn expensive/unique columns
            new_vals = _generate_column(
                col_name, spec, frame.iloc[idx], sub_rng, len(idx), entities, cache_dir, offline
            )
            frame.loc[frame.index[idx], col_name] = new_vals
        return frame

    df = _constraints.apply_constraints(
        df, ds.get("constraints", []), rng, resampler=resampler, report=report.setdefault(name, {})
    )

    # Keep the full frame (incl. inherited cols) in memory for downstream
    # siblings, but drop transient inherited columns from the written CSV.
    full = df
    out_df = df.drop(columns=[c for c in inherited_cols if c in df.columns]) if inherited_cols else df

    out_path = out_dir / f"{name}.csv"
    out_df.to_csv(out_path, index=False)
    report[name]["rows"] = len(out_df)
    report[name]["columns"] = list(out_df.columns)
    report[name]["path"] = str(out_path)
    # Return the FULL frame (with inherited cols) so later siblings can inherit
    # from this table too; the report/CSV reflect the trimmed output.
    return full


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DataGen generation engine")
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows-scale", type=float, default=1.0)
    ap.add_argument("--only", default="", help="comma-separated dataset names to build")
    ap.add_argument("--offline", action="store_true", help="never call the LLM API")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args(argv)

    if args.workers:
        import os
        os.environ["DATAGEN_LLM_WORKERS"] = str(args.workers)

    recipe = load_recipe(args.recipe)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    entities = EntityPools(recipe.get("entities", {}), int(recipe["meta"]["seed"]))

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    report: Dict[str, Any] = {"recipe": recipe["meta"].get("name"), "datasets": {}}
    frames: Dict[str, pd.DataFrame] = {}

    for ds in recipe["datasets"]:
        if only and ds["name"] not in only:
            continue
        print(f"[datagen] generating '{ds['name']}' ...", file=sys.stderr)
        frames[ds["name"]] = generate_dataset(
            ds, recipe, entities, out_dir, args.rows_scale, args.offline, report["datasets"], frames
        )

    validation = build_validation_report(recipe, frames, entities)
    report["validation"] = validation
    (out_dir / "generation_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(f"[datagen] done. {len(frames)} dataset(s) written to {out_dir}", file=sys.stderr)
    print(json.dumps({"out": str(out_dir), "datasets": {k: len(v) for k, v in frames.items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
