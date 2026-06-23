"""Load and validate a recipe, then resolve column generation order."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml


class RecipeError(Exception):
    pass


def load_recipe(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        recipe = yaml.safe_load(f)
    validate_recipe(recipe)
    return recipe


def validate_recipe(recipe: Dict[str, Any]) -> None:
    """Validate against the JSON schema if jsonschema is installed; always run a
    set of structural checks that the schema can't express (e.g. dependency
    cycles, dangling FK references)."""
    schema_path = Path(__file__).with_name("recipe.schema.json")
    try:
        import json

        import jsonschema

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(recipe, schema)
    except ImportError:
        pass  # jsonschema optional; structural checks below still run.
    except Exception as e:  # jsonschema.ValidationError
        raise RecipeError(f"Recipe failed schema validation: {e}") from e

    if "meta" not in recipe or "datasets" not in recipe:
        raise RecipeError("Recipe must contain 'meta' and 'datasets'.")
    if "seed" not in recipe["meta"]:
        raise RecipeError("meta.seed is required for reproducibility.")

    entities = recipe.get("entities", {})
    for ds in recipe["datasets"]:
        name = ds.get("name", "<unnamed>")
        pe = ds.get("primary_entity")
        if pe and pe not in entities:
            raise RecipeError(f"Dataset '{name}' references unknown primary_entity '{pe}'.")
        for fk in ds.get("foreign_keys", []):
            if fk["references"] not in entities:
                raise RecipeError(
                    f"Dataset '{name}' FK '{fk['column']}' references unknown entity '{fk['references']}'."
                )
        _check_column_dag(name, ds["columns"])


def _check_column_dag(ds_name: str, columns: Dict[str, Any]) -> None:
    """Topologically validate depends_on edges; raise on cycles or dangling refs."""
    deps = {col: set(spec.get("depends_on", [])) for col, spec in columns.items()}
    for col, ds in deps.items():
        for d in ds:
            if d not in columns:
                raise RecipeError(f"[{ds_name}] column '{col}' depends on unknown column '{d}'.")
    # Kahn's algorithm
    resolved: List[str] = []
    pending = dict(deps)
    while pending:
        ready = [c for c, d in pending.items() if d.issubset(resolved)]
        if not ready:
            raise RecipeError(f"[{ds_name}] dependency cycle among columns: {list(pending)}")
        for c in ready:
            resolved.append(c)
            del pending[c]


def generation_order(columns: Dict[str, Any]) -> List[str]:
    """Return a topological ordering of columns honoring depends_on, conditional
    references, correlate_with, and llm.conditioned_on edges."""
    edges: Dict[str, set] = {col: set() for col in columns}
    for col, spec in columns.items():
        for d in spec.get("depends_on", []):
            edges[col].add(d)
        cw = spec.get("correlate_with")
        if cw and cw.get("column") in columns:
            edges[col].add(cw["column"])
        for cond in spec.get("conditional", []):
            for ref in _referenced_names(cond.get("when", ""), columns):
                edges[col].add(ref)
        if spec.get("type") == "text":
            for c in spec.get("llm", {}).get("conditioned_on", []):
                if c in columns:
                    edges[col].add(c)
        if spec.get("type") == "derived" and spec.get("expr"):
            for ref in _referenced_names(spec["expr"], columns):
                edges[col].add(ref)

    order: List[str] = []
    pending = {c: set(d) for c, d in edges.items()}
    while pending:
        ready = sorted(c for c, d in pending.items() if d.issubset(order))
        if not ready:
            # Should have been caught by validation; break ties deterministically.
            ready = [sorted(pending)[0]]
        for c in ready:
            order.append(c)
            pending.pop(c, None)
    return order


_NAME_RE = re.compile(r"[A-Za-z_]\w*")


def _referenced_names(expr: str, columns: Dict[str, Any]) -> List[str]:
    return [t for t in _NAME_RE.findall(expr) if t in columns]
