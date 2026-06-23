"""LLM-authored text columns via the Anthropic API.

Cost & latency control:
  * `cardinality`: generate only K distinct texts per (group of conditioning
    values) and sample with replacement across rows. A column of 10k product
    reviews conditioned on a 5-way `segment` becomes ~5*K API-bound items, not
    10k.
  * On-disk cache keyed by (model, prompt, conditioning tuple) so re-runs and
    resumes are free.
  * Concurrent requests via a thread pool.

If ANTHROPIC_API_KEY is unset or the SDK is missing, falls back to a templated
placeholder so the engine still produces a complete dataset offline.
"""
from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

DEFAULT_MODEL = os.environ.get("DATAGEN_LLM_MODEL", "claude-haiku-4-5-20251001")
_MAX_WORKERS = int(os.environ.get("DATAGEN_LLM_WORKERS", "8"))


def _cache_key(model: str, prompt: str) -> str:
    h = hashlib.sha256(f"{model}\x00{prompt}".encode("utf-8")).hexdigest()
    return h[:32]


class _Cache:
    def __init__(self, cache_dir: Path):
        self.path = cache_dir / "llm_cache.json"
        self.data: Dict[str, str] = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}

    def get(self, key: str):
        return self.data.get(key)

    def set(self, key: str, value: str):
        self.data[key] = value

    def flush(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=0), encoding="utf-8")


def _render_prompt(template: str, row: Dict[str, Any]) -> str:
    try:
        return template.format(**row)
    except (KeyError, IndexError):
        return template


def _have_api() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call_anthropic(client, model: str, prompt: str, max_tokens: int) -> str:
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return " ".join(parts).strip()


def generate_text_column(
    df: pd.DataFrame,
    spec: Dict[str, Any],
    rng: np.random.Generator,
    cache_dir: Path,
    offline: bool | None = None,
) -> np.ndarray:
    """Return an array of generated strings, one per row of `df`."""
    llm = spec["llm"]
    template = llm["prompt"]
    max_tokens = int(llm.get("max_tokens", 120))
    cardinality = llm.get("cardinality")
    conditioned_on = llm.get("conditioned_on", [])
    model = llm.get("model", DEFAULT_MODEL)

    n = len(df)
    if offline is None:
        offline = not _have_api()

    # Determine the set of distinct prompts we actually need to fill.
    if conditioned_on:
        groups = df.groupby(conditioned_on, sort=False)
        group_keys = list(groups.groups.keys())
    else:
        group_keys = [None]

    # Build a pool of (representative row dict) per group, capped by cardinality.
    jobs: List[Tuple[Any, str]] = []  # (group_key, rendered_prompt)
    prompts_per_group: Dict[Any, List[str]] = {}
    for gk in group_keys:
        if gk is None:
            sample_row = df.iloc[0].to_dict() if n else {}
        else:
            sub = groups.get_group(gk)
            sample_row = sub.iloc[0].to_dict()
        k = cardinality if cardinality else 1
        rendered = [_render_prompt(template, sample_row) for _ in range(k)]
        # Add a uniqueness nudge so K calls don't return identical text.
        rendered = [f"{p}\n\n(Variation #{i+1}; make it distinct.)" if k > 1 else p
                    for i, p in enumerate(rendered)]
        prompts_per_group[gk] = rendered
        for p in rendered:
            jobs.append((gk, p))

    cache = _Cache(cache_dir)
    results: Dict[str, str] = {}

    if offline:
        for gk, prompt in jobs:
            results[prompt] = _offline_placeholder(prompt, gk)
    else:
        import anthropic  # imported lazily

        client = anthropic.Anthropic()
        to_call = []
        for gk, prompt in jobs:
            key = _cache_key(model, prompt)
            cached = cache.get(key)
            if cached is not None:
                results[prompt] = cached
            else:
                to_call.append((key, prompt))

        if to_call:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
                futs = {
                    ex.submit(_call_anthropic, client, model, prompt, max_tokens): (key, prompt)
                    for key, prompt in to_call
                }
                for fut in as_completed(futs):
                    key, prompt = futs[fut]
                    try:
                        text = fut.result()
                    except Exception as e:  # degrade gracefully per-item
                        text = _offline_placeholder(prompt, None) + f" [llm_error: {type(e).__name__}]"
                    results[prompt] = text
                    cache.set(key, text)
            cache.flush()

    # Now assign a result to every row by sampling within its group.
    out = np.empty(n, dtype=object)
    if conditioned_on:
        for gk in group_keys:
            idx = groups.get_group(gk).index.to_numpy()
            pool = [results[p] for p in prompts_per_group[gk]]
            chosen = rng.integers(0, len(pool), size=len(idx))
            for j, row_i in enumerate(idx):
                out[row_i] = pool[chosen[j]]
    else:
        pool = [results[p] for p in prompts_per_group[None]]
        chosen = rng.integers(0, len(pool), size=n)
        for i in range(n):
            out[i] = pool[chosen[i]]
    return out


def _offline_placeholder(prompt: str, group_key: Any) -> str:
    tag = "" if group_key is None else f" [{group_key}]"
    # Keep it short and clearly synthetic so reviewers know the API wasn't used.
    return f"<synthetic text{tag}>"
