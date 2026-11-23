#!/usr/bin/env python3
"""Verify the real Codex CLI in disposable homes without model or push requests."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from barknotify_plugin import __version__, installer
from barknotify_plugin.rpc import inspect_hooks

ROOT = Path(__file__).resolve().parents[1]


def main():
    binary = shutil.which("codex")
    if not binary:
        print("SKIP: Codex is not installed")
        return 1 if os.environ.get("BARKNOTIFY_REQUIRE_NATIVE_TEST") == "1" else 0
    with tempfile.TemporaryDirectory(prefix="bark-native-") as temporary:
        # macOS exposes /var through a symlink; CLI paths are canonicalized.
        base = Path(temporary).resolve()
        private = base / "custom-private" / "bark"
        env = {**os.environ, "HOME": str(base), "XDG_CONFIG_HOME": str(base / "config"),
               "BARKNOTIFY_CONFIG_DIR": str(private), "PYTHONPATH": str(ROOT)}
        homes = [base / "alpha", base / "beta"]
        original = 'model = "test-model"\n[model_providers.example]\nname = "Example"\nbase_url = "https://example.invalid"\n'
        original_hooks = {"description": "User hooks", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "true"}]}]}}
        for home in homes:
            home.mkdir()
            (home / "config.toml").write_text(original)
            (home / "hooks.json").write_text(json.dumps(original_hooks))
        command = [sys.executable, "-m", "barknotify_plugin", "install", "--codex-bin", binary]
        for home in homes:
            command += ["--codex-home", str(home)]

        def run(args, selected_env=None):
            result = subprocess.run(args, env=selected_env or env, cwd=base, capture_output=True, text=True, timeout=40)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            return result.stdout

        run(command + ["--dry-run"])
        assert not private.exists(), "dry-run must not write"
        run(command)
        key = private / "device-key"
        key.write_text("private-test-key\n")
        config_path = private / "config.json"
        config = json.loads(config_path.read_text())
        config["group"] = "custom-group"
        config_path.write_text(json.dumps(config))
        source = private / "marketplace" / "barknotify_plugin"
        (source / "obsolete.py").write_text("# Removed in the next release")
        run(command)
        assert not (source / "obsolete.py").exists(), "upgrade must replace stale source files"
        assert key.read_text() == "private-test-key\n"
        assert json.loads(config_path.read_text())["group"] == "custom-group"
        for home in homes:
            config_text = (home / "config.toml").read_text()
            assert config_text.count('[plugins."barknotify@barknotify-plugin"]') == 1
            assert 'model = "test-model"' in config_text and 'base_url = "https://example.invalid"' in config_text
            record = json.loads((home / "bark-install.json").read_text())
            cache = Path(record["plugin_root"])
            assert record["version"] == __version__ and cache.is_dir()
            assert record["runtime_version"] == __version__
            assert record["python_executable"] == str(Path(sys.executable).resolve())
            assert record["runtime_digest"] == installer.runtime_metadata(cache)["runtime_digest"]
            assert "bark-proxy" in record["capabilities"]
            assert (cache / "plugin.json").is_file() and (cache / "assets" / "lifecycle-hooks.json").is_file()
            assert not list(cache.rglob("device-key")), "credentials must stay outside the cache"
            assert json.loads((home / "hooks.json").read_text())["hooks"]["Stop"][0] == original_hooks["hooks"]["Stop"][0]
            selected_env = {**env, "CODEX_HOME": str(home)}
            selected_env.pop("BARKNOTIFY_CONFIG_DIR")
            status = json.loads(run([sys.executable, str(cache / "scripts" / "barknotify.py"), "status", "--json"], selected_env))
            assert status["config_dir"] == str(private), "custom settings should be discovered from the installation record"
            assert status["device_key_status"] == "available"
            hooks = inspect_hooks(binary, home)
            matching = [h for h in hooks if h.get("pluginId") == installer.SELECTOR] if record["mode"] == "native" else [h for h in hooks if h.get("command") == record["command"]]
            assert len(matching) == 6, hooks
            assert all(h["trustStatus"] == "untrusted" and not h["isManaged"] for h in matching)
            assert any(h.get("command") == "true" for h in hooks)
            backups = list((home / "backups" / "barknotify-plugin").glob("*/config.toml"))
            assert any(path.read_text() == original for path in backups)
            assert all(path.stat().st_mode & 0o777 == 0o600 for path in backups)
        uninstall = ["uninstall" if part == "install" else part for part in command]
        run(uninstall)
        run(uninstall)  # Idempotent cleanup, even after native cache removal.
        assert key.exists() and config_path.exists()
        for home in homes:
            assert not (home / "plugins" / "cache" / "barknotify-plugin" / "barknotify").exists()
            assert 'model = "test-model"' in (home / "config.toml").read_text()
            assert json.loads((home / "hooks.json").read_text()) == original_hooks
            assert not (home / "bark-install.json").exists()

        # Native-first flow, using a marketplace distinct from the private settings.
        marketplace = base / "repository-marketplace"
        shutil.copytree(ROOT / "barknotify_plugin", marketplace / "barknotify_plugin", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        catalog = marketplace / ".agents" / "plugins" / "marketplace.json"
        catalog.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / ".agents" / "plugins" / "marketplace.json", catalog)
        home = base / "native-first"
        home.mkdir()
        (home / "config.toml").write_text(original)
        (home / "hooks.json").write_text(json.dumps(original_hooks))
        selected_env = {**env, "CODEX_HOME": str(home), "BARKNOTIFY_DEVICE_KEY": "private-test-key"}

        # An older product registration and bridge must disappear on migration.
        legacy_market = base / "legacy-marketplace"
        legacy_catalog = legacy_market / ".agents" / "plugins" / "marketplace.json"
        legacy_catalog.parent.mkdir(parents=True)
        legacy_catalog.write_text(json.dumps({"name": "codex-bark", "plugins": [{"name": "bark", "source": {"source": "local", "path": "./plugin"}}]}))
        legacy_root = legacy_market / "plugin"
        shutil.copytree(ROOT / "barknotify_plugin", legacy_root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        legacy_manifest = json.loads((legacy_root / "plugin.json").read_text())
        legacy_manifest.update(name="bark", version="0.3.0")
        (legacy_root / "plugin.json").write_text(json.dumps(legacy_manifest))
        template = json.loads((ROOT / "barknotify_plugin" / "assets" / "lifecycle-hooks.json").read_text())
        (legacy_root / "assets" / "lifecycle-hooks.json").write_text(json.dumps(template))
        run([binary, "plugin", "marketplace", "add", str(legacy_market)], selected_env)
        legacy = json.loads(run([binary, "plugin", "add", "bark@codex-bark", "--json"], selected_env))
        (home / "bark-install.json").write_text(json.dumps({"mode": "compat", "plugin": "bark@codex-bark", "plugin_root": legacy["installedPath"], "config_dir": str(private), "command": "legacy-bark-fixture-command"}))
        managed = json.loads(json.dumps(original_hooks))
        for event, groups in template["hooks"].items():
            for group in groups:
                for handler in group["hooks"]:
                    handler["command"] = "legacy-bark-fixture-command"
            managed["hooks"].setdefault(event, []).extend(groups)
        (home / "hooks.json").write_text(json.dumps(managed))
        run([binary, "plugin", "marketplace", "add", str(marketplace)], selected_env)
        installed = json.loads(run([binary, "plugin", "add", installer.SELECTOR, "--json"], selected_env))
        source_before = json.loads(run([binary, "plugin", "marketplace", "list", "--json"], selected_env))
        script = Path(installed["installedPath"]) / "scripts" / "barknotify.py"
        previous_record = (home / "bark-install.json").read_bytes()
        run([sys.executable, str(script), "integrate", "--dry-run"], selected_env)
        assert (home / "bark-install.json").read_bytes() == previous_record
        run([sys.executable, str(script), "setup", "--integrate", "--no-test", "--language", "zh"], selected_env)
        assert not installer.configured(home, "bark@codex-bark")
        assert not Path(legacy["installedPath"]).exists()
        assert "legacy-bark-fixture-command" not in (home / "hooks.json").read_text()
        record = json.loads((home / "bark-install.json").read_text())
        assert record["distribution"] == "marketplace"
        command_before = record.get("command")
        assert source_before == json.loads(run([binary, "plugin", "marketplace", "list", "--json"], selected_env))
        assert 'base_url = "https://example.invalid"' in (home / "config.toml").read_text()
        assert key.read_text() == "private-test-key\n"
        assert json.loads(config_path.read_text())["group"] == "custom-group"
        stable_runtime = home / "bark" / "runtime"
        assert (stable_runtime / "scripts" / "barknotify.py").is_file()
        (stable_runtime / "obsolete.py").write_text("old runtime")

        # Simulate a new marketplace release and refresh using the old cached script.
        manifest = marketplace / "barknotify_plugin" / "plugin.json"
        content = json.loads(manifest.read_text())
        content["version"] = "99.0.0"
        manifest.write_text(json.dumps(content))
        init = marketplace / "barknotify_plugin" / "__init__.py"
        init.write_text(init.read_text().replace(__version__, "99.0.0"))
        run([sys.executable, str(script), "integrate"], selected_env)
        updated = json.loads((home / "bark-install.json").read_text())
        assert updated["version"] == "99.0.0"
        assert updated["runtime_version"] == "99.0.0"
        assert updated["runtime_digest"] == installer.runtime_metadata(stable_runtime)["runtime_digest"]
        assert Path(updated["plugin_root"]) != Path(record["plugin_root"])
        assert updated.get("command") == command_before, "compatibility command must survive cache version changes"
        status = json.loads(run([sys.executable, "-m", "barknotify_plugin", "status", "--json"], selected_env))
        assert status["version"] == __version__ and status["plugin_version"] == "99.0.0"
        assert not (stable_runtime / "obsolete.py").exists()
        assert source_before == json.loads(run([binary, "plugin", "marketplace", "list", "--json"], selected_env))
        assert key.read_text() == "private-test-key\n"
        assert json.loads(config_path.read_text())["language"] == "zh"
        matching = [h for h in inspect_hooks(binary, home) if h.get("command") == updated.get("command")] if updated["mode"] == "compat" else [h for h in inspect_hooks(binary, home) if h.get("pluginId") == installer.SELECTOR]
        assert len(matching) == 6 and all(h["trustStatus"] == "untrusted" for h in matching)
        new_script = Path(updated["plugin_root"]) / "scripts" / "barknotify.py"
        run([sys.executable, str(new_script), "uninstall"], selected_env)
        assert not stable_runtime.exists()
        assert json.loads((home / "hooks.json").read_text()) == original_hooks
        assert key.exists()
        assert source_before == json.loads(run([binary, "plugin", "marketplace", "list", "--json"], selected_env))
        print("Tool-managed and native-first installation, source retention, versioned upgrades, multiple homes, settings, trust, and cleanup passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
