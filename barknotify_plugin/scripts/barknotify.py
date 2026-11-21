#!/usr/bin/env python3
"""Load the bundled package even when Codex names its cache directory by version."""

import importlib.util
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("barknotify_plugin", root / "__init__.py", submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec)
sys.modules["barknotify_plugin"] = module
spec.loader.exec_module(module)

from barknotify_plugin.cli import main

raise SystemExit(main())
