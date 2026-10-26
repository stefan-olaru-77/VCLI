#!/usr/bin/env python3
"""Development launcher: ``python run.py [files...]`` without installing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Imported after the path insert so a checkout runs without installing.
from vcli.cli import main  # pylint: disable=wrong-import-position

if __name__ == "__main__":
    raise SystemExit(main())
