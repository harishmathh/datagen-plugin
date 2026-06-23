"""Entity pools and referential integrity across datasets.

An `entity` (e.g. `customers`) defines a stable pool of ids. Datasets reference
entities in two ways:
  * `primary_entity`: the dataset is keyed 1:1 on the entity; its key column is
    injected and rows default to the entity count.
  * `foreign_keys`: a column draws ids from an entity's pool (many:1), so joins
    line up across tables.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np


class EntityPools:
    def __init__(self, entities: Dict[str, Any], master_seed: int):
        self.pools: Dict[str, np.ndarray] = {}
        self.keys: Dict[str, str] = {}
        for i, (name, spec) in enumerate(sorted(entities.items())):
            key = spec["key"]
            count = int(spec["count"])
            fmt = spec.get("id_format", "{name}{n:08d}".replace("{name}", name.upper()[:4]))
            ids = self._make_ids(fmt, count)
            self.pools[name] = ids
            self.keys[name] = key

    @staticmethod
    def _make_ids(fmt: str, count: int) -> np.ndarray:
        # Support both '{:07d}' positional and '{n:07d}' named styles.
        out = np.empty(count, dtype=object)
        for i in range(count):
            try:
                out[i] = fmt.format(i + 1, n=i + 1)
            except (IndexError, KeyError):
                out[i] = f"{fmt}{i+1}"
        return out

    def has(self, name: str) -> bool:
        return name in self.pools

    def key_of(self, name: str) -> str:
        return self.keys[name]

    def pool(self, name: str) -> np.ndarray:
        return self.pools[name]

    def count(self, name: str) -> int:
        return len(self.pools[name])

    def sample_fk(self, name: str, size: int, rng: np.random.Generator) -> np.ndarray:
        pool = self.pools[name]
        idx = rng.integers(0, len(pool), size=size)
        return pool[idx]
