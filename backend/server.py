#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p2000_compat457',HERE/'compat457.py')
if spec is None or spec.loader is None:raise RuntimeError('v4.5.7 compatibility bridge kon niet worden geladen')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
if __name__=='__main__':mod.compat.main()
