"""A restricted expression evaluator for recipe `expr`, `when`, and constraint
expressions.

Expressions operate on a pandas DataFrame and may use:
  - column names as bare identifiers (resolved to the DataFrame's Series)
  - numeric/string/bool literals
  - arithmetic, comparison, boolean, bitwise ops
  - a small allowlist of numpy/helper functions

This deliberately avoids `DataFrame.eval`/`query` (which allow attribute access
and arbitrary names) by walking the AST and rejecting anything not allowlisted.
"""
from __future__ import annotations

import ast
import operator
from typing import Any, Dict

import numpy as np
import pandas as pd

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
}

_UNARY_OPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Invert: operator.invert,
    ast.Not: operator.not_,
}

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_BOOL_OPS = {ast.And: operator.and_, ast.Or: operator.or_}


def _make_funcs(rng: np.random.Generator) -> Dict[str, Any]:
    """Functions available inside expressions. `rng`-backed randoms make derived
    columns reproducible under the master seed."""

    def randint(lo, hi, size=None):
        return rng.integers(int(lo), int(hi) + 1, size=size)

    def rand(size=None):
        return rng.random(size=size)

    def normal(mean=0.0, std=1.0, size=None):
        return rng.normal(mean, std, size=size)

    def choice(options, size=None, p=None):
        return rng.choice(options, size=size, p=p)

    return {
        "randint": randint,
        "rand": rand,
        "normal": normal,
        "choice": choice,
        "where": np.where,
        "clip": np.clip,
        "abs": np.abs,
        "log": np.log,
        "log1p": np.log1p,
        "exp": np.exp,
        "sqrt": np.sqrt,
        "floor": np.floor,
        "ceil": np.ceil,
        "round": np.round,
        "minimum": np.minimum,
        "maximum": np.maximum,
        "isin": lambda s, vals: pd.Series(s).isin(vals).to_numpy(),
        "min": np.minimum,
        "max": np.maximum,
    }


class SafeEvaluator:
    def __init__(self, df: pd.DataFrame, rng: np.random.Generator, n: int):
        self.df = df
        self.n = n
        self.funcs = _make_funcs(rng)

    def eval(self, expr: str):
        tree = ast.parse(expr, mode="eval")
        return self._eval(tree.body)

    def _eval(self, node):  # noqa: C901 - a dispatch tree is naturally branchy
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.df.columns:
                return self.df[node.id]
            if node.id in self.funcs:
                return self.funcs[node.id]
            if node.id == "n":
                return self.n
            if node.id in ("True", "False", "None"):
                return {"True": True, "False": False, "None": None}[node.id]
            raise NameError(f"Unknown name in expression: {node.id!r}")
        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Operator not allowed: {type(node.op).__name__}")
            return op(self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unary operator not allowed: {type(node.op).__name__}")
            return op(self._eval(node.operand))
        if isinstance(node, ast.BoolOp):
            op = _BOOL_OPS[type(node.op)]
            result = self._eval(node.values[0])
            for v in node.values[1:]:
                result = op(result, self._eval(v))
            return result
        if isinstance(node, ast.Compare):
            left = self._eval(node.left)
            result = None
            for op_node, comparator in zip(node.ops, node.comparators):
                op = _CMP_OPS.get(type(op_node))
                if op is None:
                    raise ValueError(f"Comparison not allowed: {type(op_node).__name__}")
                right = self._eval(comparator)
                cmp = op(left, right)
                result = cmp if result is None else (result & cmp)
                left = right
            return result
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in self.funcs:
                raise ValueError("Only allowlisted functions may be called.")
            func = self.funcs[node.func.id]
            args = [self._eval(a) for a in node.args]
            kwargs = {kw.arg: self._eval(kw.value) for kw in node.keywords}
            return func(*args, **kwargs)
        if isinstance(node, ast.List):
            return [self._eval(e) for e in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._eval(e) for e in node.elts)
        if isinstance(node, ast.IfExp):
            # vectorized ternary -> np.where
            cond = self._eval(node.test)
            return np.where(cond, self._eval(node.body), self._eval(node.orelse))
        raise ValueError(f"Expression node not allowed: {type(node).__name__}")


def evaluate(expr: str, df: pd.DataFrame, rng: np.random.Generator) -> Any:
    return SafeEvaluator(df, rng, len(df)).eval(expr)
