"""Locate the model-call harness, in the working tree or in a release copy.

The harness lives in the authors' A-VIP checkout during development and is
vendored into `vendor/` when the artifact is packaged for release. A script
that hard-codes either one runs in exactly one of those two trees, and the
first three experiments written after packaging began hard-coded the release
path and stopped running in the working tree.

Resolution order, first hit wins:

  1. `$AVIP_HARNESS_ROOT`, for anyone whose checkout is somewhere else
  2. `vendor/` beside the experiments directory, which is the released layout
  3. the A-VIP checkout beside this project, which is the development layout

Import it before the harness and call `add()`:

    from harness_path import add
    add()
    ollama = import_module("05_experiments._harness.ollama")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

MODULE = Path("05_experiments") / "_harness"


def candidates() -> list[Path]:
    here = Path(__file__).resolve()
    root = here.parent.parent
    found = []
    env = os.environ.get("AVIP_HARNESS_ROOT")
    if env:
        found.append(Path(env))
    found.append(root / "vendor")
    found.append(root.parent / "a-vip")
    return found


def resolve() -> Path:
    for base in candidates():
        if (base / MODULE).is_dir():
            return base
    tried = "\n  ".join(str(c) for c in candidates())
    raise RuntimeError(
        "Could not find the model-call harness. Looked in:\n  " + tried +
        "\n\nSet AVIP_HARNESS_ROOT to the directory containing "
        "05_experiments/_harness, or run from a release copy that carries "
        "vendor/.")


def add() -> Path:
    """Put the harness on `sys.path` and return the root it was found under."""
    base = resolve()
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    return base
