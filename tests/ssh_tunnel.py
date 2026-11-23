#!/usr/bin/env python3
"""Real OpenSSH reverse-SOCKS test; disposable sshd and no external requests."""
import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extensions/reverse-socks"))
from barknotify_tunnel.cli import Controller, TunnelError


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    sshd = os.environ.get("BARKNOTIFY_TEST_SSHD") or shutil.which("sshd") or "/usr/sbin/sshd"
    if not Path(sshd).exists() or not shutil.which("ss"):
        print("SKIP: Linux sshd and ss are required for real tunnel integration")
        return 1 if os.environ.get("BARKNOTIFY_REQUIRE_SSH_TEST") == "1" else 0
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/ping" else 404)
            self.end_headers()
        def log_message(self, *args):
            pass
    with tempfile.TemporaryDirectory(prefix="bark-ssh-") as temp:
        root = Path(temp)
        key, hostkey = root / "key", root / "hostkey"
        for path in (key, hostkey):
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True)
        sshport = port()
        config = root / "sshd_config"
        config.write_text("\n".join(["Port " + str(sshport), "ListenAddress 127.0.0.1", "HostKey " + str(hostkey),
                          "PidFile " + str(root / "sshd.pid"), "AuthorizedKeysFile " + str(key) + ".pub",
                          "StrictModes no", "PasswordAuthentication no", "UsePAM no", "PermitRootLogin yes",
                          "AllowTcpForwarding yes", "GatewayPorts no", "LogLevel ERROR", ""]))
        client_config = root / "ssh_config"
        client_config.write_text("\n".join(["Host test-host", " HostName 127.0.0.1", " Port " + str(sshport),
                                 " User " + getpass.getuser(), " IdentityFile " + str(key),
                                 " StrictHostKeyChecking no", " UserKnownHostsFile /dev/null", ""]))
        bindir = root / "bin"
        bindir.mkdir()
        wrapper = bindir / "ssh"
        wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(shutil.which("ssh")) + " -F " + shlex.quote(str(client_config)) + ' "$@"\n')
        wrapper.chmod(0o700)
        os.environ["PATH"] = str(bindir) + os.pathsep + os.environ["PATH"]
        daemon = subprocess.Popen([sshd, "-D", "-e", "-f", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        c = Controller(root / "profiles")
        c.save({"schema_version": 1, "host": "test-host", "port": port(), "server": "http://127.0.0.1:" + str(server.server_port),
                "enabled": False, "service_installed": False})
        try:
            for _ in range(30):
                try:
                    with socket.create_connection(("127.0.0.1", sshport), timeout=.1):
                        break
                except OSError:
                    if daemon.poll() is not None:
                        raise AssertionError(daemon.stderr.read().decode())
                    time.sleep(.1)
            c.start()
            c.start()
            assert "HTTP 200" in c.check()
            pid = int(c.ssh("-O", "check").stderr.split("pid=")[1].split(")")[0])
            os.kill(pid, 15)
            for _ in range(30):
                if not c.connected():
                    break
                time.sleep(.1)
            c.ensure()
            assert c.connected() and "HTTP 200" in c.check(), "owned SSH master must recover"
            c.stop()
            c.ensure()
            assert not c.connected() and not c.config()["enabled"], "explicit stop must survive recovery"
            # Use a fresh port: the previous sshd child may still be closing its
            # listener or accepted sockets after the mux exit acknowledgement.
            c.save({**c.config(), "port": port()})
            with socket.socket() as conflict:
                conflict.bind(("127.0.0.1", c.config()["port"]))
                conflict.listen()
                try:
                    c.start()
                except TunnelError:
                    pass
                else:
                    raise AssertionError("a busy port must fail")
                assert not c.connected(), "failed start must clean up its owned master"
            print("PASS: real reverse SOCKS, loopback listener, repeat up, connection-loss recovery, explicit stop, port conflict")
        finally:
            try:
                c.stop()
            finally:
                daemon.terminate()
                daemon.wait(timeout=5)
                daemon.stderr.close()
                server.shutdown()
                server.server_close()
                thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
