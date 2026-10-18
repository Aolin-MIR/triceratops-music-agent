"""Explicit workspace identity and request-local storage for all plug-in formats."""

from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

_CURRENT_ROOT = ContextVar("triceratops_workspace_root", default=None)


def storage_path(name: str, default: Path) -> Path:
    root = _CURRENT_ROOT.get()
    if root is None:
        return default
    return root if name == "RUNS_DIR" else root / default.name


@contextmanager
def workspace_scope(root: Path | None):
    token = _CURRENT_ROOT.set(root)
    try:
        if root is not None:
            root.mkdir(parents=True, exist_ok=True)
        yield
    finally:
        _CURRENT_ROOT.reset(token)


def scoped(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with workspace_scope(self.storage_root):
            return method(self, *args, **kwargs)

    return call
