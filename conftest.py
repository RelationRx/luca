"""Make `pytest` test this repository, not the frozen archive.

`luca` may be pip-installed in editable mode against a different checkout.
pytest's default `prepend` import mode puts the *test file's* directory on
sys.path, never the repository root, so a bare `pytest` from here imported that
other checkout's engine, and every test that covers a fix this repository made
— the issue 1 hold-out seal, for one — failed or, worse, silently passed
against different code.

This file's presence makes pytest prepend the repository root. The assertion
below fails loudly if anything ever resolves `luca` elsewhere.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import luca  # noqa: E402

assert Path(luca.__file__).resolve().is_relative_to(REPO_ROOT), (
    f"pytest imported luca from {luca.__file__}, not from {REPO_ROOT}"
)
