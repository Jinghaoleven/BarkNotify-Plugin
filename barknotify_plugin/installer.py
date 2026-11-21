"""Native plugin installation, compatibility registration, and configuration rollback."""

import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib

from . import __version__
from .rpc import inspect_hooks
from .runtime import BarkError, initialize, write_private


ROOT = Path(__file__).resolve().parent
SELECTOR = "barknotify@barknotify-plugin"
LEGACY_SELECTORS = ("bark@codex-bark", "bark@codex-bark-local")
CACHE_LOCATIONS = (("barknotify-plugin", "barknotify"), ("codex-bark", "bark"), ("codex-bark-local", "bark"))


def read_json(path, default=None):
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        raise BarkError("Cannot read " + path.name + ". Check its format and permissions.") from None


def merged_hooks(home, config, mode="compat", record=None, runtime_root=None, hook_template=None):
    previous = read_json(home / "hooks.json", {"hooks": {}})
    record = record if record is not None else read_json(home / "bark-install.json", {})
    if not isinstance(previous, dict) or not isinstance(previous.get("hooks", {}), dict) or not isinstance(record, dict):
        raise BarkError("Invalid existing hooks.json or Bark installation record.")
    runtime_root = runtime_root or config / "marketplace" / "barknotify_plugin"
    command = shlex.join(["env", "BARKNOTIFY_CONFIG_DIR=" + str(config), str(Path(sys.executable).resolve()),
                          str(runtime_root / "scripts" / "barknotify.py"), "hook", "--compat"])
    managed = {command}
    if isinstance(record.get("command"), str):
        managed.add(record["command"])
    result = copy.deepcopy(previous)
    result.setdefault("hooks", {})
    for event, groups in list(result["hooks"].items()):
        if not isinstance(groups, list):
            raise BarkError("Invalid hook groups in hooks.json.")
        preserved = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
                raise BarkError("Invalid hook handlers in hooks.json.")
            handlers = group.get("hooks", [])
            if any(not isinstance(handler, dict) for handler in handlers):
                raise BarkError("Invalid hook handler in hooks.json.")
            kept = [handler for handler in handlers if handler.get("command") not in managed]
            if kept or not handlers:
                if handlers:
                    group["hooks"] = kept
                preserved.append(group)
        if not preserved and groups:
            del result["hooks"][event]
        else:
            result["hooks"][event] = preserved
    if mode == "compat":
        template = copy.deepcopy(hook_template) if hook_template is not None else read_json(ROOT / "assets" / "lifecycle-hooks.json")
        for event, groups in template["hooks"].items():
            for group in groups:
                for handler in group["hooks"]:
                    handler["command"] = command
            result["hooks"].setdefault(event, []).extend(groups)
    return result, command


def native_command(binary, home, *args):
    with tempfile.TemporaryDirectory(prefix="barknotify-plugin-command-") as cwd:
        result = subprocess.run([binary, "plugin", *args], env={**os.environ, "CODEX_HOME": str(home)},
                                cwd=cwd, capture_output=True, text=True, timeout=30)
    if result.returncode:
        # Native stderr can include user config values. Do not relay it blindly.
        raise BarkError("Codex plugin " + args[0] + " failed. Run codex plugin " + args[0] + " --help and barknotify-plugin doctor.")
    if "--json" in args:
        try:
            return json.loads(result.stdout)
        except ValueError:
            raise BarkError("Codex returned an invalid plugin installation response. Update Codex and retry.") from None
    return {}


def configured(home, selector):
    path = home / "config.toml"
    if not path.exists():
        return False
    try:
        return selector in tomllib.loads(path.read_text()).get("plugins", {})
    except (OSError, ValueError):
        raise BarkError("Cannot read the target Codex config.toml.") from None


def resolve_binary(value):
    binary = shutil.which(value or "codex")
    if not binary:
        raise BarkError("Codex executable not found. Install Codex or use --codex-bin.")
    try:
        result = subprocess.run([binary, "plugin", "add", "--help"], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        raise BarkError("Cannot execute Codex. Check --codex-bin.") from None
    if result.returncode:
        raise BarkError("This Codex version lacks native plugin management. Update Codex first.")
    return str(Path(binary).absolute())


def select_mode(binary, home, mode, template):
    if mode == "compat":
        return "compat", "Compatibility mode was explicitly selected."
    try:
        hooks = inspect_hooks(binary, home)
        loaded = [hook for hook in hooks if hook.get("pluginId") == SELECTOR]
        expected = {event[0].lower() + event[1:] for event in template["hooks"]}
        supported = len(loaded) == len(expected) and {hook.get("eventName") for hook in loaded} == expected
    except (OSError, ValueError):
        supported = False
    if mode == "native" and not supported:
        raise BarkError("Codex did not expose the bundled hooks. Use --mode auto or --mode compat.")
    return ("native", None) if supported else ("compat", "Bundled hooks were not exposed by this local Codex runtime.")


def backup_changes(snapshots):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for path, previous in snapshots.items():
        if previous is not None and path.read_bytes() != previous:
            backup = path.parent / "backups" / "barknotify-plugin" / stamp / path.name
            write_private(backup, previous.decode("utf-8"))


def integrate(homes, config, binary=None, mode="auto", dry_run=False):
    """Connect an installed marketplace plugin without replacing its source.

    A stable per-home bridge copy survives versioned cache paths. Native add
    refreshes the bundle from the existing source; private settings stay outside it.
    """
    homes = list(dict.fromkeys(Path(home).expanduser().resolve() for home in homes))
    config = Path(config).expanduser().resolve()
    records = {home: read_json(home / "bark-install.json", {}) for home in homes}
    for home in homes:
        merged_hooks(home, config, record=records[home], runtime_root=home / "bark" / "runtime")
        if not configured(home, SELECTOR):
            raise BarkError("Install barknotify@barknotify-plugin with codex plugin add first, then run integrate.")
    if dry_run:
        for home in homes:
            print("Would connect installed " + SELECTOR + " in " + str(home) + " (mode: " + mode + ").")
        print("Marketplace sources and private credentials are preserved.")
        return
    binary = resolve_binary(binary)
    for home in homes:
        listing = native_command(binary, home, "list", "--json")
        installed = [entry for entry in listing.get("installed", []) if entry.get("pluginId") == SELECTOR]
        if len(installed) != 1 or installed[0].get("enabled") is not True:
            raise BarkError("Bark must be installed and enabled in /plugins before integration.")
    config.mkdir(parents=True, exist_ok=True, mode=0o700)
    initialize(config)
    paths = [home / name for home in homes for name in ("config.toml", "hooks.json", "bark-install.json")]
    snapshots = {path: path.read_bytes() if path.exists() else None for path in paths}
    with tempfile.TemporaryDirectory(prefix="barknotify-plugin-integrate-") as temporary:
        directories = {}
        for index, home in enumerate(homes):
            managed = [(market, home / "plugins" / "cache" / market / plugin) for market, plugin in CACHE_LOCATIONS]
            managed.append(("runtime", home / "bark" / "runtime"))
            for label, path in managed:
                snapshot = Path(temporary) / (str(index) + "-" + label)
                if path.exists():
                    shutil.copytree(path, snapshot)
                directories[path] = snapshot
        outcomes = []
        try:
            for home in homes:
                installation = native_command(binary, home, "add", SELECTOR, "--json")
                for selector in LEGACY_SELECTORS:
                    if configured(home, selector):
                        native_command(binary, home, "remove", selector)
                installed_path = installation.get("installedPath")
                plugin_root = Path(installed_path) if isinstance(installed_path, str) else None
                if plugin_root is None or not plugin_root.is_dir() or not (plugin_root / "scripts" / "barknotify.py").is_file():
                    raise BarkError("Codex did not expose a complete Bark plugin cache. Update Codex and retry.")
                template = read_json(plugin_root / "assets" / "lifecycle-hooks.json")
                selected, reason = select_mode(binary, home, mode, template)
                target = home / "bark" / "runtime"
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(plugin_root, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                # Codex add may delete the old cache this process was launched from.
                # Use the newly loaded bundle template, never reopen the old ROOT.
                merged, command = merged_hooks(home, config, selected, records[home], runtime_root=target, hook_template=template)
                write_private(home / "hooks.json", json.dumps(merged, indent=2) + "\n")
                record = {"version": installation.get("version", __version__), "plugin": SELECTOR,
                          "mode": selected, "distribution": "marketplace", "config_dir": str(config),
                          "plugin_root": str(plugin_root), "runtime_root": str(target), "codex_bin": binary}
                if selected == "compat":
                    record.update(command=command, reason=reason)
                write_private(home / "bark-install.json", json.dumps(record, indent=2) + "\n")
                outcomes.append("Connected BarkNotify-Plugin " + record["version"] + " in " + str(home) + " (" + selected + ").")
            backup_changes(snapshots)
        except BaseException:
            for path, previous in snapshots.items():
                if previous is None:
                    path.unlink(missing_ok=True)
                else:
                    write_private(path, previous.decode("utf-8"))
            for path, snapshot in directories.items():
                if path.exists():
                    shutil.rmtree(path)
                if snapshot.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(snapshot, path)
            raise
    for outcome in outcomes:
        print(outcome)
    print("Marketplace source preserved. Review Bark in /hooks in a new Codex session.")


def install(homes, config, binary=None, mode="auto", dry_run=False):
    homes = list(dict.fromkeys(Path(home).expanduser().resolve() for home in homes))
    config = Path(config).expanduser().resolve()
    records = {home: read_json(home / "bark-install.json", {}) for home in homes}
    for home in homes:
        merged_hooks(home, config, record=records[home])  # Validate before any writes.
        if configured(home, SELECTOR) and (not records[home] or records[home].get("distribution") == "marketplace"):
            raise BarkError("An existing marketplace installation was found. Use integrate to preserve its update source.")
    if dry_run:
        for home in homes:
            print("Would install " + SELECTOR + " in " + str(home) + " (mode: " + mode + ").")
        print("Private settings: " + str(config))
        return
    binary = resolve_binary(binary)
    config.mkdir(parents=True, exist_ok=True, mode=0o700)
    initialize(config)
    marketplace = config / "marketplace"
    marketplace.mkdir(parents=True, exist_ok=True)
    target = marketplace / "barknotify_plugin"
    paths = [home / name for home in homes for name in ("config.toml", "hooks.json", "bark-install.json")]
    snapshots = {path: path.read_bytes() if path.exists() else None for path in paths}
    with tempfile.TemporaryDirectory(prefix=".install-", dir=config) as temporary:
        staging = Path(temporary) / "package"
        old_source = Path(temporary) / "previous"
        shutil.copytree(ROOT, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # Use the installer interpreter for local native hooks; raw marketplace
        # bundles retain a portable python3 command.
        template_path = staging / "assets" / "lifecycle-hooks.json"
        template = read_json(template_path)
        for groups in template["hooks"].values():
            for group in groups:
                for handler in group["hooks"]:
                    handler["command"] = shlex.quote(str(Path(sys.executable).resolve())) + ' "${PLUGIN_ROOT}/scripts/barknotify.py" hook'
        template_path.write_text(json.dumps(template, indent=2) + "\n")
        caches = {}
        for index, home in enumerate(homes):
            for market, plugin in CACHE_LOCATIONS:
                path = home / "plugins" / "cache" / market / plugin
                snapshot = Path(temporary) / (str(index) + "-" + market)
                if path.exists():
                    shutil.copytree(path, snapshot)
                caches[path] = snapshot
        catalog = marketplace / ".agents" / "plugins" / "marketplace.json"
        previous_catalog = catalog.read_bytes() if catalog.exists() else None
        moved_old, swapped = False, False
        outcomes = []
        try:
            if target.exists():
                target.rename(old_source)
                moved_old = True
            staging.rename(target)
            swapped = True
            catalog.parent.mkdir(parents=True, exist_ok=True)
            write_private(catalog, json.dumps({"name": "barknotify-plugin", "interface": {"displayName": "BarkNotify-Plugin"}, "plugins": [
                {"name": "barknotify", "source": {"source": "local", "path": "./barknotify_plugin"},
                 "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}]}))
            for home in homes:
                home.mkdir(parents=True, exist_ok=True)
                native_command(binary, home, "marketplace", "add", str(marketplace))
                installation = native_command(binary, home, "add", SELECTOR, "--json")
                for selector in LEGACY_SELECTORS:
                    if configured(home, selector):
                        native_command(binary, home, "remove", selector)
                selected, reason = select_mode(binary, home, mode, template)
                merged, command = merged_hooks(home, config, selected, records[home], hook_template=template)
                write_private(home / "hooks.json", json.dumps(merged, indent=2) + "\n")
                version = __version__
                installed_path = installation.get("installedPath")
                plugin_root = Path(installed_path) if isinstance(installed_path, str) else None
                if plugin_root is None or not plugin_root.is_dir():
                    raise BarkError("Codex did not create the expected plugin cache. Update Codex and retry.")
                record = {"version": version, "plugin": SELECTOR, "mode": selected, "distribution": "tool",
                          "config_dir": str(config), "plugin_root": str(plugin_root), "codex_bin": binary}
                if selected == "compat":
                    record["command"] = command
                    record["reason"] = reason or "Compatibility mode was explicitly selected."
                write_private(home / "bark-install.json", json.dumps(record, indent=2) + "\n")
                outcomes.append("Installed BarkNotify-Plugin " + version + " in " + str(home) + " (" + selected + ").")
            # Keep reviewable backups only for files that changed.
            backup_changes(snapshots)
            for outcome in outcomes:
                print(outcome)
        except BaseException:
            for path, previous in snapshots.items():
                if previous is None:
                    path.unlink(missing_ok=True)
                else:
                    write_private(path, previous.decode("utf-8"))
            for path, snapshot in caches.items():
                if path.exists():
                    shutil.rmtree(path)
                if snapshot.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(snapshot, path)
            if swapped and target.exists():
                shutil.rmtree(target)
            if moved_old and old_source.exists():
                old_source.rename(target)
            if previous_catalog is None:
                catalog.unlink(missing_ok=True)
            else:
                write_private(catalog, previous_catalog.decode("utf-8"))
            raise
    print("Run barknotify-plugin setup, then review Bark in /hooks in a new Codex session.")


def uninstall(homes, config, binary=None, dry_run=False):
    for home in dict.fromkeys(Path(home).expanduser().resolve() for home in homes):
        record = read_json(home / "bark-install.json", {})
        if not record and not any(configured(home, selector) for selector in (SELECTOR, *LEGACY_SELECTORS)):
            print("Bark is already uninstalled in " + str(home) + ".")
            continue
        merged, _ = merged_hooks(home, config, "none", record)
        if dry_run:
            print("Would remove Bark and its compatibility hooks from " + str(home) + ".")
            continue
        executable = resolve_binary(binary or record.get("codex_bin"))
        paths = [home / name for name in ("config.toml", "hooks.json", "bark-install.json")]
        snapshots = {path: path.read_bytes() if path.exists() else None for path in paths}
        with tempfile.TemporaryDirectory(prefix="barknotify-plugin-uninstall-") as temporary:
            caches = {}
            for market, plugin in CACHE_LOCATIONS:
                path = home / "plugins" / "cache" / market / plugin
                snapshot = Path(temporary) / market
                if path.exists():
                    shutil.copytree(path, snapshot)
                caches[path] = snapshot
            runtime = home / "bark" / "runtime"
            snapshot = Path(temporary) / "bridge-runtime"
            if runtime.exists():
                shutil.copytree(runtime, snapshot)
            caches[runtime] = snapshot
            try:
                for selector in (SELECTOR, *LEGACY_SELECTORS):
                    if configured(home, selector):
                        native_command(executable, home, "remove", selector)
                write_private(home / "hooks.json", json.dumps(merged, indent=2) + "\n")
                if runtime.exists():
                    shutil.rmtree(runtime)
                (home / "bark-install.json").unlink(missing_ok=True)
            except BaseException:
                for path, previous in snapshots.items():
                    if previous is None:
                        path.unlink(missing_ok=True)
                    else:
                        write_private(path, previous.decode("utf-8"))
                for path, snapshot in caches.items():
                    if path.exists():
                        shutil.rmtree(path)
                    if snapshot.exists():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(snapshot, path)
                raise
        print("Uninstalled Bark from " + str(home) + ". Private settings were retained.")
