#!/usr/bin/env python3
"""Run the installed service copy without relying on a checkout or shell init."""

import importlib.util
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("barknotify_tunnel", root / "__init__.py", submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec)
sys.modules["barknotify_tunnel"] = module
spec.loader.exec_module(module)
from barknotify_tunnel.cli import main

raise SystemExit(main())
