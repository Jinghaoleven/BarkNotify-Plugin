import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from barknotify_plugin import cli, installer, runtime


class InstallTests(unittest.TestCase):
    def test_merge_preserves_other_handlers_and_uninstall_removes_only_bark(self):
        with tempfile.TemporaryDirectory(prefix="bark-merge-") as temporary:
            home = Path(temporary)
            config = home / "configuration with spaces"
            original = {"description": "existing user hooks", "hooks": {
                "Stop": [{"matcher": "*", "hooks": [
                    {"type": "command", "command": "existing command"},
                    {"type": "mcp_tool", "server": "audit", "tool": "log"},
                ]}], "PostToolUse": []}}
            path = home / "hooks.json"
            path.write_text(json.dumps(original))
            registry = home / "bark-install.json"
            merged, command = installer.merged_hooks(home, config)
            self.assertEqual(merged["description"], original["description"])
            self.assertEqual(merged["hooks"]["Stop"][0], original["hooks"]["Stop"][0])
            self.assertIn("'", command)  # Shell-quoted custom paths.
            path.write_text(json.dumps(merged))
            registry.write_text(json.dumps({"command": command}))
            repeated, _ = installer.merged_hooks(home, config)
            self.assertEqual(repeated, merged)
            uninstalled, _ = installer.merged_hooks(home, config, mode="none")
            self.assertEqual(uninstalled, original)

    def test_relocation_removes_previously_registered_command(self):
        with tempfile.TemporaryDirectory(prefix="bark-move-") as temporary:
            home = Path(temporary)
            registry = home / "bark-install.json"
            hooks, command = installer.merged_hooks(home, home / "old")
            (home / "hooks.json").write_text(json.dumps(hooks))
            registry.write_text(json.dumps({"command": command}))
            new, replacement = installer.merged_hooks(home, home / "new")
            commands = [h["command"] for groups in new["hooks"].values() for group in groups for h in group["hooks"]]
            self.assertEqual(commands, [replacement] * 6)

    def test_invalid_existing_hooks_are_rejected_without_writes(self):
        with tempfile.TemporaryDirectory(prefix="bark-invalid-") as temporary:
            home = Path(temporary)
            for invalid in ({"hooks": []}, {"hooks": {"Stop": "bad"}}, {"hooks": {"Stop": [{"hooks": [None]}]}}):
                path = home / "hooks.json"
                before = json.dumps(invalid)
                path.write_text(before)
                with self.assertRaises(ValueError):
                    installer.merged_hooks(home, home / "config")
                self.assertEqual(path.read_text(), before)

    def test_failed_install_restores_existing_config_hooks_registry_and_source(self):
        with tempfile.TemporaryDirectory(prefix="bark-rollback-") as temporary:
            root = Path(temporary)
            home, private = root / "home", root / "private"
            home.mkdir()
            source = private / "marketplace" / "barknotify_plugin"
            source.mkdir(parents=True)
            (source / "previous-release.py").write_text("old release")
            original = {"config.toml": 'model = "existing"\n', "hooks.json": '{"hooks":{}}\n', "bark-install.json": '{"command":"old hook"}\n'}
            for name, value in original.items():
                (home / name).write_text(value)

            def fail(binary, target, *args):
                (target / "config.toml").write_text('model = "changed"\n')
                raise installer.BarkError("Simulated native install failure")

            with patch.object(installer, "resolve_binary", return_value="fake-codex"), patch.object(installer, "native_command", side_effect=fail):
                with self.assertRaises(installer.BarkError):
                    installer.install([home], private, mode="compat")
            for name, value in original.items():
                self.assertEqual((home / name).read_text(), value)
            self.assertEqual((source / "previous-release.py").read_text(), "old release")
            self.assertFalse((source / "plugin.json").exists())

    def test_dry_run_does_not_create_any_runtime_files(self):
        with tempfile.TemporaryDirectory(prefix="bark-dry-run-") as temporary:
            root = Path(temporary)
            with patch.object(installer, "resolve_binary", side_effect=AssertionError("should not execute Codex")):
                installer.install([root / "home"], root / "private", dry_run=True)
            self.assertEqual(list(root.iterdir()), [])

    def test_detected_native_hooks_remove_the_previous_compatibility_bridge(self):
        with tempfile.TemporaryDirectory(prefix="bark-native-mode-") as temporary:
            root = Path(temporary)
            home, private = root / "home", root / "private"
            home.mkdir()
            (home / "config.toml").write_text("")
            hooks, command = installer.merged_hooks(home, private)
            (home / "hooks.json").write_text(json.dumps(hooks))
            (home / "bark-install.json").write_text(json.dumps({"mode": "compat", "command": command}))
            cache = home / "plugins" / "cache" / "barknotify-plugin" / "barknotify" / "local"
            cache.mkdir(parents=True)

            def native(binary, target, *args):
                if args[0] == "add":
                    (target / "config.toml").write_text('[plugins."barknotify@barknotify-plugin"]\nenabled = true\n')
                    return {"installedPath": str(cache)}
                return {}

            events = ("sessionStart", "userPromptSubmit", "permissionRequest", "stop", "interrupt", "sessionEnd")
            discovered = [{"pluginId": installer.SELECTOR, "eventName": event} for event in events]
            with patch.object(installer, "resolve_binary", return_value="fake-codex"), patch.object(installer, "native_command", side_effect=native), patch.object(installer, "inspect_hooks", return_value=discovered):
                installer.install([home], private)
            self.assertEqual(json.loads((home / "hooks.json").read_text()), {"hooks": {}})
            record = json.loads((home / "bark-install.json").read_text())
            self.assertEqual(record["mode"], "native")
            self.assertEqual(record["plugin_root"], str(cache))
            self.assertNotIn("command", record)

    def test_catalog_write_failure_restores_previous_source_and_catalog(self):
        with tempfile.TemporaryDirectory(prefix="bark-catalog-rollback-") as temporary:
            root = Path(temporary)
            home, private = root / "home", root / "private"
            home.mkdir()
            source = private / "marketplace" / "barknotify_plugin"
            source.mkdir(parents=True)
            (source / "previous.py").write_text("old source")
            catalog = private / "marketplace" / ".agents" / "plugins" / "marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text('{"name":"previous"}')
            write = installer.write_private
            failed = False

            def fail_once(path, value):
                nonlocal failed
                if path == catalog and not failed:
                    failed = True
                    raise OSError("Simulated catalogue write failure")
                return write(path, value)

            with patch.object(installer, "resolve_binary", return_value="fake-codex"), patch.object(installer, "write_private", side_effect=fail_once):
                with self.assertRaises(OSError):
                    installer.install([home], private, mode="compat")
            self.assertEqual((source / "previous.py").read_text(), "old source")
            self.assertEqual(catalog.read_text(), '{"name":"previous"}')

    def test_install_does_not_replace_an_existing_native_marketplace(self):
        with tempfile.TemporaryDirectory(prefix="bark-existing-") as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            original = '[plugins."barknotify@barknotify-plugin"]\nenabled = true\n'
            (home / "config.toml").write_text(original)
            with self.assertRaisesRegex(installer.BarkError, "Use integrate"):
                installer.install([home], home / "private")
            self.assertEqual((home / "config.toml").read_text(), original)
            self.assertFalse((home / "private").exists())

    def test_integration_failure_restores_the_bridge_cache_and_host_files(self):
        with tempfile.TemporaryDirectory(prefix="bark-integrate-rollback-") as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            private = Path(temporary) / "private"
            cache = home / "plugins" / "cache" / "barknotify-plugin" / "barknotify" / "old"
            bridge = home / "bark" / "runtime"
            for path in (cache, bridge):
                path.mkdir(parents=True)
                (path / "previous.py").write_text("previous runtime")
            original = {"config.toml": '[plugins."barknotify@barknotify-plugin"]\nenabled = true\n',
                        "hooks.json": '{"hooks":{}}\n', "bark-install.json": '{"command":"previous"}\n'}
            for name, value in original.items():
                (home / name).write_text(value)

            def native(binary, target, *args):
                if args[0] == "list":
                    return {"installed": [{"pluginId": installer.SELECTOR, "enabled": True}]}
                self.assertEqual(args, ("add", installer.SELECTOR, "--json"))
                (target / "config.toml").write_text("changed")
                (bridge / "previous.py").write_text("changed")
                (cache / "previous.py").write_text("changed")
                raise installer.BarkError("Simulated refresh failure")

            with patch.object(installer, "resolve_binary", return_value="fake-codex"), patch.object(installer, "native_command", side_effect=native):
                with self.assertRaises(installer.BarkError):
                    installer.integrate([home], private)
            for name, value in original.items():
                self.assertEqual((home / name).read_text(), value)
            for path in (cache, bridge):
                self.assertEqual((path / "previous.py").read_text(), "previous runtime")

    def test_integration_never_enables_a_disabled_plugin(self):
        with tempfile.TemporaryDirectory(prefix="bark-disabled-plugin-") as temporary:
            physical = Path(temporary) / "physical-home"
            physical.mkdir()
            home = Path(temporary) / "linked-home"
            home.symlink_to(physical, target_is_directory=True)
            (home / "config.toml").write_text('[plugins."barknotify@barknotify-plugin"]\nenabled = false\n')
            with patch.object(installer, "resolve_binary", return_value="fake-codex"), patch.object(installer, "native_command", return_value={"installed": [{"pluginId": installer.SELECTOR, "enabled": False}]}) as native:
                with self.assertRaisesRegex(installer.BarkError, "enabled"):
                    installer.integrate([home], home / "private")
            native.assert_called_once_with("fake-codex", home.resolve(), "list", "--json")
            self.assertFalse((home / "private").exists())

    def test_single_target_home_discovers_its_own_private_settings(self):
        with tempfile.TemporaryDirectory(prefix="bark-target-home-") as temporary:
            base = Path(temporary)
            target = base / "target"
            target.mkdir()
            private = base / "custom-private"
            (target / "bark-install.json").write_text(json.dumps({"config_dir": str(private)}))
            with patch.dict(os.environ, {"CODEX_HOME": str(base / "other-home")}):
                os.environ.pop("BARKNOTIFY_CONFIG_DIR", None)
                os.environ.pop("CODEX_BARK_CONFIG_DIR", None)
                with patch.object(installer, "integrate") as integrate:
                    self.assertEqual(cli.main(["integrate", "--codex-home", str(target), "--dry-run"]), 0)
                    integrate.assert_called_once_with([str(target)], private, None, "auto", True)

    def test_rename_reuses_legacy_default_settings_without_copying_the_key(self):
        with tempfile.TemporaryDirectory(prefix="barknotify-legacy-settings-") as temporary:
            base = Path(temporary)
            legacy = base / "config" / "codex-bark"
            legacy.mkdir(parents=True)
            settings = {**runtime.DEFAULTS, "device_key_env": "CODEX_BARK_DEVICE_KEY", "language": "zh", "group": "existing-group"}
            original = json.dumps(settings)
            (legacy / "config.json").write_text(original)
            (legacy / "device-key").write_text("existing-device-key\n")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(base / "config"), "CODEX_HOME": str(base / "home")}):
                for name in ("BARKNOTIFY_CONFIG_DIR", "CODEX_BARK_CONFIG_DIR", "BARKNOTIFY_DEVICE_KEY", "CODEX_BARK_DEVICE_KEY"):
                    os.environ.pop(name, None)
                self.assertEqual(runtime.config_dir(), legacy)
                self.assertEqual(runtime.initialize()["language"], "zh")
                self.assertEqual(runtime.device_key(runtime.load_config()), "existing-device-key")
            self.assertEqual((legacy / "config.json").read_text(), original)
            self.assertFalse((base / "config" / "barknotify-plugin").exists())


if __name__ == "__main__":
    unittest.main()
