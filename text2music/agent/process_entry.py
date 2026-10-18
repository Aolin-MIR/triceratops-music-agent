"""Launch packaged modules with embeddable and standard Python alike."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_BOOTSTRAP = (
    "import json,runpy,sys; "
    "sys.path[:0]=json.loads(sys.argv.pop(1)); "
    "runpy.run_module(sys.argv.pop(1),run_name='__main__')"
)


def python_module_command(module: str, *arguments: str, python: str | Path | None = None) -> list[str]:
    # Pass runtime paths explicitly: Windows embeddable Python ignores PYTHONPATH.
    # A private CUDA target must remain ahead of the seed runtime's CPU packages.
    root = Path(__file__).resolve().parents[2]
    paths = [str(root), *[p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                        if p and p != str(root)]]
    return [str(python or sys.executable), "-X", "utf8", "-c", _BOOTSTRAP,
            json.dumps(paths, ensure_ascii=True), module, *map(str, arguments)]
