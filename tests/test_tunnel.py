import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extensions/reverse-socks"))
from barknotify_tunnel.cli import Controller, TunnelError, origin


class FakeController(Controller):
    def __init__(self, directory, name="default"):
        super().__init__(directory, name)
        self.live = False
        self.forwarded = False
        self.calls = []
        self.bind = "127.0.0.1"
        self.denied = False

    def socket_dir(self):
        pass

    def connected(self):
        return self.live

    def ssh(self, *options, **kwargs):
        self.calls.append(options)
        code = 0
        if "-M" in options:
            self.live = True
        if "forward" in options:
            if self.denied:
                code = 1
            else:
                self.forwarded = True
        if "exit" in options:
            self.live = self.forwarded = False
        return subprocess.CompletedProcess(options, code, "", "")

    def remote(self, command, **kwargs):
        if command.startswith("if command"):
            output = "LISTEN 0 128 " + self.bind + ":" + str(self.config()["port"]) + " 0.0.0.0:*\n" if self.forwarded else ""
        else:
            output = "200"
        return subprocess.CompletedProcess([], 0, output, "")


class TunnelTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.controller = FakeController(self.root)
        self.controller.save({"schema_version": 1, "host": "codex-host", "port": 10808,
                              "server": "https://api.day.app", "enabled": False, "service_installed": False})

    def tearDown(self):
        self.temporary.cleanup()

    def test_up_is_idempotent_and_down_prevents_recovery(self):
        c = self.controller
        c.start()
        connected_at = c.state()["last_connected_at"]
        c.start()
        self.assertEqual(c.state()["last_connected_at"], connected_at)
        self.assertEqual(sum("forward" in options for options in c.calls), 1)
        self.assertTrue(c.config()["enabled"])
        self.assertIn("HTTP 200", c.check())
        c.stop()
        count = len(c.calls)
        c.ensure()
        self.assertEqual(len(c.calls), count)
        self.assertFalse(c.live)

    def test_failed_forward_does_not_enable_or_leave_owned_master(self):
        c = self.controller
        c.denied = True
        with self.assertRaises(TunnelError):
            c.start()
        self.assertFalse(c.live)
        self.assertFalse(c.config()["enabled"])

    def test_wildcard_binding_is_rejected_and_rolled_back(self):
        self.controller.bind = "0.0.0.0"
        with self.assertRaises(TunnelError):
            self.controller.start()
        self.assertFalse(self.controller.live)

    def test_recovery_after_loss_and_backoff_after_failure(self):
        c = self.controller
        c.start()
        c.live = c.forwarded = False
        c.ensure()
        self.assertTrue(c.live)
        c.live = c.forwarded = False
        c.denied = True
        with self.assertRaises(TunnelError):
            c.ensure()
        calls = len(c.calls)
        c.ensure()
        self.assertEqual(len(c.calls), calls)
        self.assertGreater(c.state()["next_retry"], 0)

    def test_profiles_and_short_private_socket_paths(self):
        first = Controller(self.root, "first")
        second = Controller(self.root, "second")
        self.assertNotEqual(first.socket, second.socket)
        self.assertNotEqual(first.label, second.label)
        self.assertLess(len(str(first.socket).encode()), 100)
        with self.assertRaises(TunnelError):
            Controller(self.root, "../escape")

    def test_service_dry_run_and_launchd_runtime(self):
        c = self.controller
        paths = [self.root / "services/job.plist"]
        before = sorted(str(p) for p in self.root.rglob("*"))
        with patch("barknotify_tunnel.cli.sys.platform", "darwin"), patch.object(c, "service_paths", return_value=paths):
            result = c.install_service(True)
            data = plistlib.loads(c.service_files()[paths[0]])
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        self.assertEqual(result["command"], data["ProgramArguments"])
        self.assertEqual(data["StartInterval"], 30)
        self.assertIn("/runtime/scripts/", data["ProgramArguments"][1])

    def test_service_failure_restores_runtime_units_settings_and_running_tunnel(self):
        c = self.controller
        c.start()
        c.save({**c.config(), "service_installed": True})
        runtime = c.root / "runtime"
        runtime.mkdir()
        (runtime / "previous").write_text("old-runtime")
        path = self.root / "services/job.plist"
        path.parent.mkdir()
        path.write_bytes(b"old-unit")
        before = c.config()
        with patch.object(c, "service_files", return_value={path: b"new-unit"}), patch.object(c, "deactivate_service"), patch.object(c, "activate_service", side_effect=[TunnelError("install failed"), None]) as activate:
            with self.assertRaises(TunnelError):
                c.install_service()
        self.assertEqual(c.config(), before)
        self.assertEqual((runtime / "previous").read_text(), "old-runtime")
        self.assertEqual(path.read_bytes(), b"old-unit")
        self.assertTrue(c.live)
        self.assertEqual(activate.call_count, 2)

    def test_fresh_service_failure_stops_tunnel_and_restores_disabled_state(self):
        c = self.controller
        path = self.root / "services/job.plist"
        with patch.object(c, "service_files", return_value={path: b"new-unit"}), patch.object(c, "deactivate_service"), patch.object(c, "activate_service", side_effect=TunnelError("install failed")):
            with self.assertRaises(TunnelError):
                c.install_service()
        self.assertFalse(c.live)
        self.assertFalse(c.config()["enabled"])
        self.assertFalse(path.exists())
        self.assertFalse((c.root / "runtime").exists())

    def test_linux_service_escapes_paths_and_uninstall_stops_recovery(self):
        c = self.controller
        paths = [self.root / "services/job.service", self.root / "services/job.timer"]
        with patch("barknotify_tunnel.cli.sys.platform", "linux"), patch.object(c, "service_paths", return_value=paths), patch.object(c, "service_command"):
            c.install_service()
            self.assertIn(b"Type=oneshot", paths[0].read_bytes())
            self.assertIn(b"OnUnitActiveSec=30", paths[1].read_bytes())
            c.uninstall_service()
        self.assertFalse(c.config()["service_installed"])
        self.assertFalse(c.config()["enabled"])
        self.assertFalse(c.live)
        self.assertFalse(any(p.exists() for p in paths))

    def test_invalid_server_and_config_errors_do_not_echo_credentials(self):
        for value in ("https://user:secret@host", "https://host/key", "file:///key"):
            with self.assertRaises(TunnelError) as caught:
                origin(value)
            self.assertNotIn("secret", str(caught.exception))

    def test_failed_health_probe_records_its_own_timestamp(self):
        c = self.controller
        c.start()
        c.record(last_health_at="2000-01-01T00:00:00Z")
        with patch.object(c, "verify_listener"), patch.object(c, "remote", return_value=subprocess.CompletedProcess([], 22, "503", "private response")):
            with self.assertRaises(TunnelError):
                c.check()
        self.assertEqual(c.state()["last_health"], "failed")
        self.assertNotEqual(c.state()["last_health_at"], "2000-01-01T00:00:00Z")
        self.assertNotIn("private response", json.dumps(c.state()))


if __name__ == "__main__":
    unittest.main()
