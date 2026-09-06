#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPAT456_PATH = HERE / "compat456.py"

spec = importlib.util.spec_from_file_location("p2000_compat456", COMPAT456_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("v4.5.6 compatibility bridge kon niet worden geladen")
compat456 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat456)

if __name__ == "__main__":
    compat456.compat.main()
