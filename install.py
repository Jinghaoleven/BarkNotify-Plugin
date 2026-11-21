#!/usr/bin/env python3
"""Compatibility entry point; new installations use barknotify-plugin install."""

import sys
from barknotify_plugin.cli import main

args = sys.argv[1:]
uninstall = "--uninstall" in args
apply = "--apply" in args
args = [value for value in args if value not in ("--uninstall", "--apply", "--plan")]
if not apply and not uninstall and "--dry-run" not in args:
    args.append("--dry-run")
raise SystemExit(main(["uninstall" if uninstall else "install", *args]))
