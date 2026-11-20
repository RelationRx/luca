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

# A bare `assert` would be stripped by `python -O` / PYTHONOPTIMIZE, which is
# exactly when a silent wrong import does the most damage. Raise instead.
#
# The sys.path insert above cannot win against every editable install: a PEP
# 660 install registers a finder on sys.meta_path, which runs first. Where that
# happens this raises rather than corrects, which is the point — it refuses to
# measure code from somewhere else.
if not Path(luca.__file__).resolve().is_relative_to(REPO_ROOT):
    raise RuntimeError(
        f"pytest imported luca from {luca.__file__}, not from {REPO_ROOT}. "
        f"An editable install of `luca` elsewhere is shadowing this checkout. "
        f"Uninstall it, or run `pip install -e .` from here."
    )
