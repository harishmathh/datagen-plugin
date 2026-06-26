"""Validate a research.json against research_schema.json.

Exits non-zero with a readable message on any schema or structural error, so the
Dataset-Research skill can gate on it before rendering the report.

If the optional `jsonschema` package is not installed, it falls back to a light
structural check of the required top-level keys, so the skill still gets a useful
signal without a hard dependency.

Usage:  python validate_research.py <research.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCHEMA = Path(__file__).resolve().parent / "research_schema.json"
_REQUIRED_TOP = ["business", "objective", "generated",
                 "business_profile", "customer_base", "metrics",
                 "relationships", "sources"]


def main(argv):
    if not argv:
        print("usage: python validate_research.py <research.json>", file=sys.stderr)
        return 2
    path = argv[0]
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"INVALID: cannot read JSON: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    try:
        import jsonschema  # type: ignore
        schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            loc = "/".join(str(p) for p in e.absolute_path) or "(root)"
            print(f"INVALID at {loc}: {e.message}", file=sys.stderr)
            return 1
    except ImportError:
        missing = [k for k in _REQUIRED_TOP if k not in data]
        if missing:
            print(f"INVALID: missing required keys: {', '.join(missing)}", file=sys.stderr)
            return 1
        print("NOTE: jsonschema not installed; ran a light key check only.", file=sys.stderr)

    n_attr = len(data.get("business_profile", {}).get("attributes", []))
    n_seg = len(data.get("customer_base", {}).get("segments", []))
    n_metric = len(data.get("metrics", []))
    n_src = len(data.get("sources", []))
    print(f"VALID: '{data.get('business','?')}', {n_attr} figure(s) checked, "
          f"{n_seg} segment(s), {n_metric} metric(s), {n_src} source(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
