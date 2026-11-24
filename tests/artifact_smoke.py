#!/usr/bin/env python3
"""Run with a fresh venv that has only the built wheels installed."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading


def main():
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/ping"
            self.send_response(200)
            self.end_headers()
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"code":200}')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="bark-wheel-") as temp:
            root = Path(temp)
            env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "BARKNOTIFY_DEVICE_KEY", "CODEX_BARK_DEVICE_KEY")}
            env.update({"HOME": temp, "CODEX_HOME": str(root / "codex"), "BARKNOTIFY_CONFIG_DIR": str(root / "settings"),
                        "XDG_CONFIG_HOME": str(root / "config"), "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"})
            def run(module, *args, input=""):
                result = subprocess.run([sys.executable, "-m", module, *args], env=env, cwd=root, input=input,
                                        capture_output=True, text=True, timeout=15)
                assert result.returncode == 0, result.stderr
                return result.stdout
            assert "0.5.1" in run("barknotify_plugin", "--version")
            run("barknotify_plugin", "install", "--dry-run")
            run("barknotify_plugin", "setup", "--key-stdin", input="http://127.0.0.1:" + str(server.server_port) + "/artifact-key")
            run("barknotify_plugin", "disable")
            run("barknotify_plugin", "preferences", "--language", "zh")
            run("barknotify_plugin", "network")
            state = json.loads(run("barknotify_plugin", "status", "--json"))
            assert not state["enabled"] and state["language"] == "zh"
            assert state["last_delivery"]["source"] == "manual"
            assert requests[0]["device_key"] == "artifact-key" and len(requests) == 1
            assert "0.1.0" in run("barknotify_tunnel", "--version")
            run("barknotify_tunnel", "configure", "--host", "test-host")
            dry = json.loads(run("barknotify_tunnel", "service", "install", "--dry-run"))
            assert "runtime/scripts/barknotify-tunnel.py" in dry["command"][1]
            assert not (root / "config/barknotify-tunnel/default/runtime").exists()
            result = subprocess.run([sys.executable, "-c",
                "import importlib.resources as r; "
                "assert r.files('barknotify_plugin').joinpath('assets/lifecycle-hooks.json').is_file(); "
                "assert r.files('barknotify_plugin').joinpath('skills/barknotify/SKILL.md').is_file(); "
                "assert r.files('barknotify_tunnel').joinpath('scripts/barknotify-tunnel.py').is_file()"],
                env=env, cwd=root, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
        print("PASS: fresh installed wheels, bundled assets, staged setup, paused preferences, manual history, network probe, tunnel service preview")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
