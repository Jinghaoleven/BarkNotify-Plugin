#!/usr/bin/env python3
"""Load the bundled package even when Codex names its cache directory by version."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

if sys.version_info < (3, 11):
    candidates = [os.environ.get("BARKNOTIFY_PYTHON")]
    try:
        home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        record = json.loads((home / "bark-install.json").read_text())
        candidates.append(record.get("python_executable"))
        candidates.extend(value for value in shlex.split(record.get("command", ""))
                          if value.startswith("/") and Path(value).name.startswith("python"))
    except (OSError, ValueError):
        pass
    candidates.extend(shutil.which(name) for name in ("python3.14", "python3.13", "python3.12", "python3.11"))
    for candidate in dict.fromkeys(value for value in candidates if isinstance(value, str) and value):
        try:
            usable = subprocess.run([candidate, "-c", "import sys; sys.exit(sys.version_info < (3, 11))"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            if usable.returncode == 0:
                os.execv(candidate, [candidate, str(Path(__file__).resolve()), *sys.argv[1:]])
        except (OSError, subprocess.SubprocessError):
            continue
    print("BarkNotify requires Python 3.11+. Install it or set BARKNOTIFY_PYTHON to its executable.", file=sys.stderr)
    raise SystemExit(1)

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("barknotify_plugin", root / "__init__.py", submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec)
sys.modules["barknotify_plugin"] = module
spec.loader.exec_module(module)

from barknotify_plugin.cli import main

raise SystemExit(main())
