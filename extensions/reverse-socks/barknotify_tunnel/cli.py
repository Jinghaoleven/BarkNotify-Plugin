"""Portable tunnel ownership, loopback verification and opt-in supervision."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

from . import __version__


class TunnelError(ValueError):
    pass


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".tunnel-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(value if isinstance(value, bytes) else value.encode())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def origin(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or
                parsed.password is not None or parsed.path not in ("", "/") or parsed.query or parsed.fragment or
                any(c.isspace() or ord(c) < 32 for c in value)):
            raise ValueError()
        parsed.port
    except (ValueError, TypeError):
        raise TunnelError("Use a Bark HTTP(S) server origin without credentials or paths.") from None
    return value.rstrip("/")


class Controller:
    def __init__(self, directory, name="default"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}", name):
            raise TunnelError("Profile names may contain letters, digits, dots, underscores and hyphens.")
        self.root = Path(directory).expanduser().resolve() / name
        self.name = name
        token = hashlib.sha256(str(self.root).encode()).hexdigest()[:16]
        # macOS TMPDIR is too long for Unix-domain control sockets.
        self.socket_directory = Path("/tmp") / ("barknotify-tunnel-" + str(os.getuid()))
        self.socket = self.socket_directory / (token + ".sock")
        self.label = "org.barknotify.tunnel." + token

    @contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.root / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "w") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def config(self):
        try:
            config = json.loads((self.root / "config.json").read_text())
            if (config.get("schema_version") != 1 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", config["host"]) or
                    type(config["port"]) is not int or not 1 <= config["port"] <= 65535 or
                    type(config["enabled"]) is not bool or type(config.get("service_installed", False)) is not bool):
                raise ValueError()
            config["server"] = origin(config["server"])
            return config
        except FileNotFoundError:
            raise TunnelError("Run configure --host <SSH-alias> first.") from None
        except (OSError, ValueError, KeyError, TypeError):
            raise TunnelError("Invalid tunnel configuration; check config.json.") from None

    def save(self, config):
        write(self.root / "config.json", json.dumps(config, indent=2) + "\n")

    def state(self):
        try:
            value = json.loads((self.root / "state.json").read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def record(self, **values):
        state = {**self.state(), **values, "updated_at": datetime.now(timezone.utc).isoformat()}
        write(self.root / "state.json", json.dumps(state, indent=2) + "\n")

    def ssh(self, *options, timeout=25):
        config = self.config()
        try:
            return subprocess.run(["ssh", "-S", str(self.socket), "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                                   *options, config["host"]], capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise TunnelError("OpenSSH is missing. Install OpenSSH 7.6 or later.") from None
        except (OSError, subprocess.SubprocessError):
            raise TunnelError("SSH operation timed out or failed; check the SSH alias and network.") from None

    def connected(self):
        if not self.socket.exists():
            return False
        return self.ssh("-O", "check", timeout=3).returncode == 0

    def socket_dir(self):
        path = self.socket_directory
        if path.is_symlink():
            raise TunnelError("Unsafe tunnel control directory.")
        path.mkdir(mode=0o700, exist_ok=True)
        info = path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise TunnelError("Tunnel control directory must be private and owned by this user.")
        if len(os.fsencode(self.socket)) >= 100:
            raise TunnelError("Control socket path is too long; use a shorter temporary directory.")

    def remote(self, command, timeout=15):
        try:
            config = self.config()
            # Mux uses our socket; if it disappears, false prevents an unrelated
            # fallback SSH connection (including inherited ProxyJump settings).
            return subprocess.run(["ssh", "-S", str(self.socket), "-o", "BatchMode=yes", "-o", "ProxyCommand=false", "-o", "ClearAllForwardings=yes",
                                   config["host"], command], capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            raise TunnelError("Cannot communicate with the tunnel's remote host.") from None

    def verify_listener(self):
        port = self.config()["port"]
        command = ("if command -v ss >/dev/null 2>&1; then ss -H -ltn 'sport = :" + str(port) +
                   "'; elif command -v lsof >/dev/null 2>&1; then lsof -nP -iTCP:" + str(port) +
                   " -sTCP:LISTEN -Fn; else exit 3; fi")
        result = self.remote(command)
        addresses = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts and parts[0] == "LISTEN" and len(parts) >= 5:
                addresses.append(parts[3])
            elif line.startswith("n") and ":" in line:
                addresses.append(line[1:])
        allowed = {"127.0.0.1:" + str(port), "[::1]:" + str(port), "::1:" + str(port)}
        if result.returncode or not addresses or any(value not in allowed for value in addresses):
            raise TunnelError("Remote listener is missing or not loopback-only. Check sshd GatewayPorts and ss/lsof availability.")

    def start(self, enable=True):
        config = self.config()
        self.socket_dir()
        created = not self.connected()
        if created:
            if self.socket.exists():
                info = self.socket.lstat()
                if info.st_uid != os.getuid() or not stat.S_ISSOCK(info.st_mode):
                    raise TunnelError("Refusing to replace an unexpected control socket file.")
                self.socket.unlink()
            result = self.ssh("-f", "-N", "-M", "-o", "ClearAllForwardings=yes", "-o", "ServerAliveInterval=20",
                              "-o", "ServerAliveCountMax=3")
            if result.returncode:
                raise TunnelError("Cannot start SSH. Verify the alias, keys, host trust and network with ssh first.")
        try:
            if created:
                result = self.ssh("-O", "forward", "-R", "127.0.0.1:" + str(config["port"]))
                if result.returncode:
                    raise TunnelError("Reverse forwarding failed; the remote port may be busy or sshd may deny forwarding.")
            self.verify_listener()
            if enable:
                config["enabled"] = True
                self.save(config)
            values = {"last_error": None, "failures": 0, "next_retry": 0}
            if created:
                values["last_connected_at"] = datetime.now(timezone.utc).isoformat()
            self.record(**values)
        except BaseException:
            if created:
                try:
                    self.ssh("-O", "exit")
                except TunnelError:
                    pass
            raise

    def stop(self):
        config = self.config()
        config["enabled"] = False
        self.save(config)  # A supervisor must not revive an explicitly stopped tunnel.
        if self.connected() and self.ssh("-O", "exit").returncode:
            raise TunnelError("Could not stop the owned SSH connection; automatic recovery is disabled.")
        self.record(stopped_at=datetime.now(timezone.utc).isoformat())

    def check(self):
        if not self.connected():
            raise TunnelError("Tunnel is disconnected. Run up, or enable service recovery.")
        self.verify_listener()
        config = self.config()
        command = shlex.join(["curl", "-q", "--fail", "--silent", "--show-error", "--proxy",
                              "socks5h://127.0.0.1:" + str(config["port"]), "--noproxy", "", "--connect-timeout", "3",
                              "--max-time", "8", "--output", "/dev/null", "--write-out", "%{http_code}",
                              config["server"] + "/ping"])
        result = self.remote(command)
        if result.returncode or result.stdout.strip() != "200":
            self.record(last_health="failed", last_health_at=datetime.now(timezone.utc).isoformat())
            raise TunnelError("Bark /ping failed through SOCKS. Check the remote curl, exit network and Bark server.")
        self.record(last_health="ok", last_health_at=datetime.now(timezone.utc).isoformat())
        return "Bark /ping returned HTTP 200 through the reverse SOCKS tunnel."

    def ensure(self):
        if not self.config()["enabled"]:
            return
        state = self.state()
        if time.time() < state.get("next_retry", 0):
            return
        try:
            self.start(enable=False)
        except TunnelError as error:
            failures = state.get("failures", 0) + 1
            self.record(last_error=str(error), failures=failures, next_retry=time.time() + min(120, 5 * 2 ** min(failures, 5)))
            raise

    def service_paths(self):
        if sys.platform == "darwin":
            return [Path.home() / "Library/LaunchAgents" / (self.label + ".plist")]
        if sys.platform.startswith("linux"):
            directory = Path.home() / ".config/systemd/user"
            return [directory / (self.label + ".service"), directory / (self.label + ".timer")]
        raise TunnelError("Service recovery supports macOS launchd and Linux user systemd.")

    def service_arguments(self):
        return [str(Path(sys.executable).resolve()), str(self.root / "runtime/scripts/barknotify-tunnel.py"),
                "--config-dir", str(self.root.parent), "--name", self.name, "ensure"]

    def service_files(self):
        paths = self.service_paths()
        args = self.service_arguments()
        if sys.platform == "darwin":
            return {paths[0]: plistlib.dumps({"Label": self.label, "ProgramArguments": args, "RunAtLoad": True,
                                              "StartInterval": 30, "ProcessType": "Background"})}
        escaped = [json.dumps(value.replace("%", "%%").replace("$", "$$"), ensure_ascii=False) for value in args]
        return {paths[0]: ("[Unit]\nDescription=BarkNotify reverse SOCKS recovery\n[Service]\nType=oneshot\nExecStart=" +
                           " ".join(escaped) + "\nTimeoutStartSec=60\n").encode(),
                paths[1]: ("[Unit]\nDescription=BarkNotify tunnel recovery timer\n[Timer]\nOnBootSec=30\nOnUnitActiveSec=30\n"
                           "[Install]\nWantedBy=timers.target\n").encode()}

    def service_command(self, args, required=True):
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=15)
            if required and result.returncode:
                raise TunnelError("Service manager failed. Check the logged-in user session and service permissions.")
            return result
        except (OSError, subprocess.SubprocessError):
            if required:
                raise TunnelError("User service manager is unavailable.") from None

    def activate_service(self, files):
        if sys.platform == "darwin":
            self.deactivate_service()
            self.service_command(["launchctl", "bootstrap", "gui/" + str(os.getuid()), str(next(iter(files)))])
        else:
            self.service_command(["systemctl", "--user", "daemon-reload"])
            self.service_command(["systemctl", "--user", "enable", "--now", self.label + ".timer"])

    def deactivate_service(self):
        if sys.platform == "darwin":
            self.service_command(["launchctl", "bootout", "gui/" + str(os.getuid()) + "/" + self.label], False)
        else:
            self.service_command(["systemctl", "--user", "disable", "--now", self.label + ".timer"], False)

    def install_service(self, dry_run=False):
        config = self.config()
        files = self.service_files()
        if dry_run:
            return {"files": [str(path) for path in files], "command": self.service_arguments()}
        previous_config = dict(config)
        previous = {path: path.read_bytes() if path.exists() else None for path in files}
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.root / "backups" / stamp
        for path, data in previous.items():
            if data is not None:
                write(backup / path.name, data)
        target = self.root / "runtime"
        had_runtime = target.exists()
        was_connected = self.connected()
        replaced_runtime = False
        try:
            self.start()
            package = Path(__file__).resolve().parent
            with tempfile.TemporaryDirectory(prefix=".runtime-", dir=self.root) as temporary:
                staged = Path(temporary) / "runtime"
                shutil.copytree(package, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                if had_runtime:
                    backup.mkdir(parents=True, exist_ok=True, mode=0o700)
                    target.rename(backup / "runtime")
                replaced_runtime = True
                staged.rename(target)
            for path, data in files.items():
                write(path, data)
            self.activate_service(files)
            config = {**config, "enabled": True, "service_installed": True}
            self.save(config)
        except BaseException:
            self.deactivate_service()
            if not was_connected:
                try:
                    self.stop()
                except TunnelError:
                    pass
            for path, data in previous.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    write(path, data)
            if replaced_runtime:
                if target.exists():
                    shutil.rmtree(target)
                if had_runtime:
                    (backup / "runtime").rename(target)
            self.save(previous_config)
            if previous_config.get("service_installed"):
                self.activate_service(files)
            raise
        return {"files": [str(path) for path in files], "backup": str(backup)}

    def uninstall_service(self):
        self.stop()
        paths = self.service_paths()
        self.deactivate_service()
        for path in paths:
            path.unlink(missing_ok=True)
        if sys.platform.startswith("linux"):
            self.service_command(["systemctl", "--user", "daemon-reload"])
        config = self.config()
        config["service_installed"] = False
        self.save(config)


def parser():
    root = argparse.ArgumentParser(prog="barknotify-tunnel", description="Run on the machine whose network should reach Bark.")
    root.add_argument("--version", action="version", version="barknotify-tunnel " + __version__)
    root.add_argument("--config-dir", default=str(Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "barknotify-tunnel"))
    root.add_argument("--name", default="default", help="Independent profile name")
    commands = root.add_subparsers(dest="action", required=True)
    configure = commands.add_parser("configure", help="Save the SSH alias and remote SOCKS port")
    configure.add_argument("--host", required=True, help="Existing SSH alias to the Codex host")
    configure.add_argument("--port", type=int, default=10808)
    configure.add_argument("--server", default="https://api.day.app")
    for action in ("up", "down", "check", "ensure"):
        commands.add_parser(action, help=argparse.SUPPRESS if action == "ensure" else None)
    status = commands.add_parser("status", help="Show saved intent, connection and last health probe")
    status.add_argument("--json", action="store_true")
    service = commands.add_parser("service", help="Install or remove optional automatic recovery")
    service.add_argument("operation", choices=("install", "uninstall"))
    service.add_argument("--dry-run", action="store_true")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        controller = Controller(args.config_dir, args.name)
        with controller.lock():
            if args.action == "configure":
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.host) or not 1 <= args.port <= 65535:
                    raise TunnelError("Use a valid SSH alias and port from 1 to 65535.")
                if (controller.root / "config.json").exists() and controller.connected():
                    raise TunnelError("Run down before changing the tunnel destination.")
                previous = controller.config() if (controller.root / "config.json").exists() else {}
                if previous.get("service_installed"):
                    raise TunnelError("Uninstall service recovery before changing the destination.")
                controller.save({"schema_version": 1, "host": args.host, "port": args.port,
                                 "server": origin(args.server), "enabled": False, "service_installed": False})
                print("Configured. Run up, then check; service install enables automatic recovery.")
            elif args.action == "up":
                controller.start()
                print("Reverse SOCKS available on remote 127.0.0.1:" + str(controller.config()["port"]))
            elif args.action == "down":
                controller.stop()
                print("Tunnel stopped; automatic recovery disabled. Run up to resume.")
            elif args.action == "check":
                print(controller.check())
            elif args.action == "ensure":
                controller.ensure()
            elif args.action == "service":
                if args.operation == "install":
                    print(json.dumps(controller.install_service(args.dry_run), indent=2))
                elif args.dry_run:
                    print(json.dumps({"remove": [str(p) for p in controller.service_paths()]}, indent=2))
                else:
                    controller.uninstall_service()
                    print("Automatic recovery removed; tunnel stopped. Settings retained.")
            else:
                config = controller.config()
                state = controller.state()
                result = {"version": __version__, "profile": args.name, "host": config["host"], "remote_port": config["port"],
                          "enabled": config["enabled"], "connected": controller.connected(),
                          "service_installed": config.get("service_installed", False), "server": config["server"],
                          **{k: state[k] for k in ("last_error", "last_health", "last_health_at", "updated_at", "failures", "next_retry") if k in state}}
                print(json.dumps(result, indent=2) if args.json else "\n".join(str(k) + ": " + str(v) for k, v in result.items()))
        return 0
    except (TunnelError, OSError, ValueError) as error:
        message = str(error) if isinstance(error, TunnelError) else "Local operation failed; check file permissions."
        print("barknotify-tunnel: " + message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
