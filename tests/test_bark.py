import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "barknotify_plugin" / "scripts" / "barknotify.py"
spec = importlib.util.spec_from_file_location("bark", ROOT / "barknotify_plugin" / "runtime.py")
bark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bark)


class BarkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bark-test-")
        self.root = Path(self.temporary.name)
        self.requests = []
        self.code = 200
        self.http_status = 200
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.requests.append((self.path, payload))
                self.send_response(test.http_status)
                self.end_headers()
                self.wfile.write(json.dumps({"code": test.code, "message": "sensitive server error"}).encode())

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = {k: v for k, v in os.environ.items() if k not in
                    ("BARKNOTIFY_DEVICE_KEY", "BARKNOTIFY_LABEL", "CODEX_BARK_DEVICE_KEY", "CODEX_BARK_LABEL", "TMUX", "TMUX_PANE")}
        self.env.update({"BARKNOTIFY_CONFIG_DIR": str(self.root / "config"),
                         "CODEX_HOME": str(self.root / "codex"), "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"})
        self.run_command("init")
        self.run_command("configure", "--server", "http://127.0.0.1:" + str(self.server.server_port),
                         "--key-stdin", input="test-key")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def run_command(self, *args, input="", env=None, expected=0):
        if args[0] == "configure":
            args = (*args, "--no-test")
        result = subprocess.run([sys.executable, str(SCRIPT), *args], input=input, text=True,
                                capture_output=True, env=env or self.env, timeout=10)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def hook(self, name="Stop", **fields):
        return self.run_command("hook", input=json.dumps({"hook_event_name": name, "cwd": "/private/source/project",
                                "session_id": "session-123", "turn_id": "turn-secret", "model": "test-model", **fields}))

    def test_defaults_and_private_idempotent_config(self):
        path = self.root / "config" / "config.json"
        key = self.root / "config" / "device-key"
        before = path.read_bytes()
        self.run_command("init")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
        status = self.run_command("status", "--json").stdout
        self.assertNotIn("test-key", status)
        self.assertEqual(json.loads(status)["device_key_status"], "available")
        self.assertEqual(json.loads(status)["events"], ["turn.completed", "approval.required"])

    def test_stop_passive_output_and_metadata_only(self):
        result = self.hook(last_assistant_message="private response", prompt="private prompt", tool_input={"command": "secret command"})
        self.assertEqual(result.stdout, "{}\n")
        self.assertEqual(result.stderr, "")
        path, payload = self.requests[-1]
        self.assertEqual(path, "/push")
        self.assertEqual(payload["device_key"], "test-key")
        self.assertEqual(payload["title"], "project · Turn ended")
        self.assertIn("test-model", payload["body"])
        for secret in ("private response", "private prompt", "secret command", "session-123", "turn-secret", "/private/source"):
            self.assertNotIn(secret, json.dumps(payload))

    def test_approval_never_returns_a_decision(self):
        result = self.hook("PermissionRequest", tool_name="Bash", tool_input={"command": "password", "description": "private reason"})
        self.assertEqual(json.loads(result.stdout), {})
        payload = self.requests[-1][1]
        self.assertEqual(payload["title"], "project · Approval requested")
        self.assertIn("Bash", payload["body"])
        self.assertNotIn("password", json.dumps(payload))
        self.assertNotIn("private reason", json.dumps(payload))

    def test_disabled_unknown_compact_and_subagent_are_ignored(self):
        self.hook("SessionStart", source="startup")
        self.run_command("disable")
        self.hook()
        self.run_command("enable")
        self.hook("SubagentStop")
        self.hook(agent_id="subagent")
        self.run_command("configure", "--events", "session.started")
        self.hook("SessionStart", source="compact")
        self.assertEqual(self.requests, [])

    def test_event_selection_and_resume(self):
        self.run_command("configure", "--events", "session.started,turn.started,turn.interrupted,session.ended")
        for event in ("SessionStart", "UserPromptSubmit", "Interrupt", "SessionEnd"):
            self.assertEqual(self.hook(event, source="resume").stdout, "{}\n")
        self.assertEqual(len(self.requests), 4)
        self.assertIn("resume", self.requests[0][1]["body"])
        self.hook()
        self.assertEqual(len(self.requests), 4)

    def test_missing_key_and_malformed_input_are_passive(self):
        (self.root / "config" / "device-key").unlink()
        self.assertEqual(self.hook().stdout, "{}\n")
        for value in ("invalid", "[]", "null", '{"hook_event_name":[]}'):
            result = self.run_command("hook", input=value)
            self.assertEqual(result.stdout, "{}\n")
            self.assertEqual(result.stderr, "")
        self.assertEqual(self.requests, [])

    def test_transport_failures_are_passive_but_test_reports_failure(self):
        self.code = 500
        self.assertEqual(self.hook().stdout, "{}\n")
        result = self.run_command("test", expected=1)
        self.assertNotIn("sensitive server error", result.stderr)
        self.assertNotIn("test-key", result.stderr)
        self.http_status = 403
        self.assertEqual(self.hook().stdout, "{}\n")
        self.run_command("test", expected=1)

    def test_connection_failure_and_session_end_time_budget(self):
        self.run_command("configure", "--events", "session.ended", "--server", "http://127.0.0.1:1")
        start = time.monotonic()
        self.assertEqual(self.hook("SessionEnd").stdout, "{}\n")
        self.assertLess(time.monotonic() - start, 2.5)
        with patch.dict(os.environ, self.env), patch.object(bark.subprocess, "run", side_effect=subprocess.TimeoutExpired("curl", 1.5)) as call:
            with self.assertRaises(ValueError):
                bark.send(bark.load_config(), "Title", "Body", timeout=1.5)
            self.assertLessEqual(call.call_args.kwargs["timeout"], 1.75)
            self.assertNotIn("test-key", " ".join(call.call_args.args[0]))

    def test_environment_key_precedence_and_manual_test_when_disabled(self):
        self.run_command("disable")
        env = {**self.env, "BARKNOTIFY_DEVICE_KEY": "environment-key"}
        self.run_command("test", env=env)
        self.assertEqual(self.requests[-1][1]["device_key"], "environment-key")
        self.run_command("send", "--title", "Requested title", "--body", "Requested body")
        self.assertEqual(self.requests[-1][1]["body"], "Requested body")

    def test_legacy_environment_aliases_work_and_new_key_takes_precedence(self):
        env = {**self.env, "CODEX_BARK_CONFIG_DIR": self.env["BARKNOTIFY_CONFIG_DIR"],
               "CODEX_BARK_DEVICE_KEY": "legacy-environment-key"}
        env.pop("BARKNOTIFY_CONFIG_DIR")
        result = self.run_command("test", env=env)
        self.assertEqual(self.requests[-1][1]["device_key"], "legacy-environment-key")
        self.assertNotIn("legacy-environment-key", result.stdout + result.stderr)
        env["BARKNOTIFY_DEVICE_KEY"] = "new-environment-key"
        self.run_command("test", env=env)
        self.assertEqual(self.requests[-1][1]["device_key"], "new-environment-key")

    def test_session_names_from_sqlite_and_index(self):
        home = self.root / "codex"
        home.mkdir()
        with sqlite3.connect(home / "state_10.sqlite") as db:
            db.execute("CREATE TABLE threads (id TEXT, title TEXT, name TEXT, first_user_message TEXT)")
            db.execute("INSERT INTO threads VALUES (?, ?, ?, ?)", ("session-123", "old title", "renamed session", "private prompt"))
        self.hook()
        self.assertEqual(self.requests[-1][1]["title"], "renamed session · Turn ended")
        with sqlite3.connect(home / "state_10.sqlite") as db:
            db.execute("UPDATE threads SET name = '', title = ''")
        (home / "session_index.jsonl").write_text('invalid line\n' + json.dumps({"id": "session-123", "thread_name": "index name"}) + "\n")
        self.hook()
        self.assertEqual(self.requests[-1][1]["title"], "index name · Turn ended")
        # No SQL interpolation or transcript fallback for malformed IDs.
        self.hook(session_id="'; DROP TABLE threads;--")
        self.assertEqual(self.requests[-1][1]["title"], "project · Turn ended")

    def test_invalid_config_does_not_replace_working_settings(self):
        path = self.root / "config" / "config.json"
        before = path.read_bytes()
        for args in (("--events", "invented.success"), ("--server", "https://api.day.app/SECRET/")):
            self.run_command("configure", *args, expected=1)
            self.assertEqual(path.read_bytes(), before)
        path.write_text("invalid JSON")
        self.assertEqual(self.hook().stdout, "{}\n")

    def test_setup_accepts_full_push_url_and_verifies_without_exposing_key(self):
        url = "http://127.0.0.1:" + str(self.server.server_port) + "/new-secret-key/"
        result = self.run_command("setup", "--key-stdin", input=url)
        self.assertEqual(self.requests[-1][1]["device_key"], "new-secret-key")
        self.assertNotIn("new-secret-key", result.stdout + result.stderr)
        self.assertEqual(len(self.requests), 1)
        status = self.run_command("status", "--json").stdout
        self.assertNotIn("new-secret-key", status)
        self.assertTrue(json.loads(status)["enabled"])

    def test_setup_verification_failure_keeps_delivery_disabled(self):
        self.code = 500
        result = self.run_command("setup", "--key-stdin", input="replacement-key", expected=1)
        self.assertNotIn("replacement-key", result.stderr)
        config = json.loads((self.root / "config" / "config.json").read_text())
        self.assertFalse(config["enabled"])
        self.assertEqual((self.root / "config" / "device-key").read_text().strip(), "replacement-key")

    def test_language_option_changes_notification_without_requiring_a_key(self):
        self.run_command("setup", "--language", "zh", "--no-test")
        self.hook()
        self.assertEqual(self.requests[-1][1]["title"], "project · 本轮结束")

    def test_compatibility_follows_plugin_toggle_removal_and_avoids_native_duplicates(self):
        home = self.root / "codex"
        cache = home / "plugins" / "cache" / "barknotify-plugin" / "barknotify" / "0.2.0"
        cache.mkdir(parents=True)
        record = {"mode": "compat", "plugin": "barknotify@barknotify-plugin", "plugin_root": str(cache)}
        (home / "bark-install.json").write_text(json.dumps(record))
        config = home / "config.toml"
        config.write_text('[plugins."barknotify@barknotify-plugin"]\nenabled = true\n')
        value = json.dumps({"hook_event_name": "Stop", "cwd": "/project"})

        def invoke(compat):
            output = io.StringIO()
            with patch.dict(os.environ, self.env), patch.object(bark.sys, "stdin", io.StringIO(value)), patch.object(bark.sys, "stdout", output), patch.object(bark, "send") as sender:
                bark.hook(compat)
                self.assertEqual(output.getvalue(), "{}\n")
                return sender.call_count

        self.assertEqual(invoke(True), 1)
        self.assertEqual(invoke(False), 0)  # Native hooks appearing after a runtime update.
        config.write_text('[plugins."barknotify@barknotify-plugin"]\nenabled = false\n')
        self.assertEqual(invoke(True), 0)
        config.write_text("")
        self.assertEqual(invoke(True), 0)
        config.write_text('[plugins."barknotify@barknotify-plugin"]\nenabled = true\n')
        cache.rmdir()
        self.assertEqual(invoke(True), 0)

    def test_failed_hook_records_only_an_actionable_local_summary(self):
        self.code = 500
        self.hook(prompt="private prompt")
        text = (self.root / "config" / "last-delivery.json").read_text()
        self.assertEqual(json.loads(text)["outcome"], "failed")
        for secret in ("test-key", "private prompt", "sensitive server error", "session-123"):
            self.assertNotIn(secret, text)

    def test_doctor_never_sends_a_push(self):
        result = self.run_command("doctor", "--json", expected=1)
        self.assertIn("configuration", {item["check"] for item in json.loads(result.stdout)["checks"]})
        self.assertEqual(self.requests, [])

    def test_invalid_push_urls_produce_safe_errors(self):
        for value in ("https://user:secret@server/key", "https://server/secret/title", "https://server/secret?extra=1"):
            with self.assertRaises(bark.BarkError) as caught:
                bark.parse_destination(value)
            self.assertNotIn("secret", str(caught.exception))

    def test_setup_reports_environment_override_before_replacing_saved_key(self):
        env = {**self.env, "BARKNOTIFY_DEVICE_KEY": "environment-key"}
        result = self.run_command("setup", "--key-stdin", input="new-key", env=env, expected=1)
        self.assertIn("Unset BARKNOTIFY_DEVICE_KEY", result.stderr)
        self.assertNotIn("environment-key", result.stderr)
        self.assertEqual((self.root / "config" / "device-key").read_text().strip(), "test-key")


if __name__ == "__main__":
    unittest.main()
