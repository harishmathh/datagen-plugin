"""Standalone recipe validator. Exits non-zero with a readable message on any
schema or structural error, so a skill can gate on it before showing the recipe.

Usage:  python validate_recipe.py <recipe.yaml>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recipe import RecipeError, load_recipe  # noqa: E402


def main(argv):
    if not argv:
        print("usage: python validate_recipe.py <recipe.yaml>", file=sys.stderr)
        return 2
    try:
        recipe = load_recipe(argv[0])
    except RecipeError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # yaml errors etc.
        print(f"INVALID: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    n_ds = len(recipe["datasets"])
    n_ent = len(recipe.get("entities", {}))
    n_cols = sum(len(d["columns"]) for d in recipe["datasets"])
    print(f"VALID: '{recipe['meta'].get('name')}' — {n_ds} dataset(s), "
          f"{n_ent} entity pool(s), {n_cols} column(s), seed={recipe['meta']['seed']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
