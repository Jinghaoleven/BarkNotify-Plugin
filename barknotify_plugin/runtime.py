#!/usr/bin/env python3
"""Private configuration and passive lifecycle notifications for Codex."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
from urllib.parse import unquote, urlsplit


EVENTS = {
    "SessionStart": ("session.started", "Session started", "会话启动"),
    "UserPromptSubmit": ("turn.started", "Working", "开始处理"),
    "PermissionRequest": ("approval.required", "Approval requested", "审批请求"),
    "Stop": ("turn.completed", "Turn ended", "本轮结束"),
    "Interrupt": ("turn.interrupted", "Interrupted", "用户中断"),
    "SessionEnd": ("session.ended", "Session ended", "会话结束"),
}
DEFAULTS = {
    "schema_version": 1,
    "enabled": False,
    "events": ["turn.completed", "approval.required"],
    "server_url": "https://api.day.app",
    "device_key_env": "BARKNOTIFY_DEVICE_KEY",
    "group": "codex",
    "level": "active",
    "timeout_seconds": 5,
    "language": "en",
}


class BarkError(ValueError):
    """An actionable message that never includes a credential or network response."""


def codex_home():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()


def registration():
    try:
        value = json.loads((codex_home() / "bark-install.json").read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def config_dir():
    explicit = os.environ.get("BARKNOTIFY_CONFIG_DIR") or os.environ.get("CODEX_BARK_CONFIG_DIR") or registration().get("config_dir")
    if explicit:
        return Path(explicit).expanduser()
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    current, legacy = base / "barknotify-plugin", base / "codex-bark"
    return legacy if not (current / "config.json").exists() and (legacy / "config.json").exists() else current


def write_private(path, value):
    """Replace atomically, including when configuration is updated concurrently."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".bark-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_config(config, directory=None):
    write_private((directory or config_dir()) / "config.json", json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def validate(config):
    if not isinstance(config, dict):
        raise ValueError("configuration must be an object")
    if config.get("schema_version") != 1 or type(config.get("enabled")) is not bool:
        raise ValueError("invalid configuration version or enabled flag")
    events = config.get("events")
    if not isinstance(events, list) or any(not isinstance(e, str) or e not in {v[0] for v in EVENTS.values()} for e in events):
        raise ValueError("invalid notification events")
    server = config.get("server_url", "")
    if not isinstance(server, str):
        raise ValueError("invalid Bark server")
    parsed = urlsplit(server)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or
            parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Bark server must be an HTTP(S) origin, without the device key or /push")
    # Validate port syntax too; never echo an invalid URL that may include a key.
    try:
        parsed.port
    except ValueError:
        raise ValueError("invalid Bark server port") from None
    env = config.get("device_key_env", "")
    if not isinstance(env, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env):
        raise ValueError("invalid device_key_env")
    if not isinstance(config.get("group"), str) or config.get("level") not in ("active", "passive", "timeSensitive", "critical"):
        raise ValueError("invalid Bark group or level")
    if type(config.get("timeout_seconds")) not in (int, float) or not 0 < config["timeout_seconds"] <= 10:
        raise ValueError("timeout_seconds must be greater than 0 and at most 10")
    if config.get("language", "en") not in ("en", "zh"):
        raise ValueError("language must be en or zh")
    return config


def load_config(directory=None):
    try:
        value = json.loads(((directory or config_dir()) / "config.json").read_text(encoding="utf-8"))
        return {**DEFAULTS, **validate(value)}
    except FileNotFoundError:
        raise BarkError("No configuration found. Run barknotify-plugin setup.") from None
    except OSError:
        raise BarkError("Cannot read Bark configuration. Check its file permissions.") from None
    except ValueError:
        raise BarkError("Invalid Bark configuration. Check config.json or restore its backup.") from None


def initialize(directory=None):
    directory = directory or config_dir()
    if not (directory / "config.json").exists():
        save_config(DEFAULTS, directory)
    return load_config(directory)


def parse_destination(value, server=None):
    """Accept Bark's device or example push URL; discard example message fields."""
    value = value.strip()
    if "://" in value:
        try:
            parsed = urlsplit(value)
            segments = parsed.path.removeprefix("/").rstrip("/").split("/")
            if (parsed.username or parsed.password or parsed.fragment or
                    not 1 <= len(segments) <= 4 or not all(segments)):
                raise ValueError()
            key = unquote(segments[0])
            origin = parsed.scheme + "://" + parsed.netloc
            validate({**DEFAULTS, "server_url": origin})
            if server and server.rstrip("/") != origin.rstrip("/"):
                raise BarkError("The push URL and --server refer to different servers.")
        except BarkError:
            raise
        except ValueError:
            raise BarkError("Use a Bark device URL or example push URL.") from None
    else:
        key, origin = value, server or DEFAULTS["server_url"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise BarkError("Enter a Bark push URL or device key; do not use an APNs token.")
    return origin.rstrip("/"), key


def key_environment(config):
    name = config["device_key_env"]
    if name in ("BARKNOTIFY_DEVICE_KEY", "CODEX_BARK_DEVICE_KEY"):
        for candidate in ("BARKNOTIFY_DEVICE_KEY", "CODEX_BARK_DEVICE_KEY"):
            if os.environ.get(candidate, "").strip():
                return candidate
    return name


def device_key(config):
    key = os.environ.get(key_environment(config), "").strip()
    path = config_dir() / "device-key"
    if not key and path.exists():
        key = path.read_text(encoding="utf-8").strip()
    if not key or not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise BarkError("No valid device key found. Run barknotify-plugin setup locally.")
    return key


def single_line(value, limit=80):
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


def session_name(session_id):
    """Read names only; never fall back to the session's prompt or transcript."""
    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id):
        return ""
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    databases = sorted(home.glob("state_*.sqlite"), key=lambda p: int(re.search(r"state_(\d+)", p.name)[1]) if re.search(r"state_(\d+)", p.name) else -1, reverse=True)
    for database in databases:
        try:
            with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1) as db:
                columns = {row[1] for row in db.execute("PRAGMA table_info(threads)")}
                fields = [field for field in ("name", "title") if field in columns]
                if not fields:
                    continue
                row = db.execute("SELECT " + ", ".join(fields) + " FROM threads WHERE id = ? LIMIT 1", (session_id,)).fetchone()
                if row:
                    name = next((single_line(value) for value in row if single_line(value)), "")
                    if name:
                        return name
        except (sqlite3.Error, OSError):
            continue
    try:
        latest = ""
        with (home / "session_index.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and row.get("id") == session_id:
                        latest = single_line(row.get("thread_name") or row.get("name") or row.get("title")) or latest
                except ValueError:
                    continue
        return latest
    except OSError:
        return ""


def context(event):
    name = session_name(event.get("session_id"))
    if not name and os.environ.get("TMUX"):
        try:
            command = ["tmux", "display-message", "-p"]
            if os.environ.get("TMUX_PANE"):
                command += ["-t", os.environ["TMUX_PANE"]]
            name = single_line(subprocess.run(command + ["#S"], capture_output=True, text=True, timeout=0.2, check=True).stdout)
        except (OSError, subprocess.SubprocessError):
            pass
    cwd = event.get("cwd")
    project = single_line(Path(cwd).name) if isinstance(cwd, str) else ""
    return name or project or "Codex", project


def send(config, title, body, timeout=None):
    """curl honors the host proxy. Secrets go through stdin, never argv or logs."""
    payload = json.dumps({"device_key": device_key(config), "title": title, "body": body,
                          "group": config["group"], "level": config["level"]}, ensure_ascii=False)
    budget = min(config["timeout_seconds"], timeout) if timeout else config["timeout_seconds"]
    try:
        result = subprocess.run([
            "curl", "-q", "--silent", "--show-error", "--fail", "--request", "POST",
            "--header", "Content-Type: application/json; charset=utf-8", "--data-binary", "@-",
            "--connect-timeout", str(min(budget, 2)), "--max-time", str(budget),
            "--write-out", "\n%{http_code}",
            config["server_url"].rstrip("/") + "/push",
        ], input=payload, capture_output=True, text=True, timeout=budget + 0.25, check=True)
        response, _, _status = result.stdout.rpartition("\n")
        if json.loads(response).get("code") != 200:
            raise BarkError("Bark rejected the push. Verify the server and device key with barknotify-plugin setup.")
    except FileNotFoundError:
        raise BarkError("curl is missing. Install curl, then run barknotify-plugin doctor.") from None
    except subprocess.TimeoutExpired:
        raise BarkError("Bark request timed out. Check connectivity and proxy settings.") from None
    except subprocess.CalledProcessError as error:
        if "CONNECT" in (error.stderr or ""):
            match = re.search(r"(?:HTTP code|response) ([1-5]\d{2})", error.stderr or "")
            status = " (CONNECT HTTP " + match[1] + ")" if match else " (CONNECT)"
            raise BarkError("Proxy refused the Bark connection" + status + ". Check HTTPS_PROXY/ALL_PROXY or use a proxy that can reach your Bark server.") from None
        if error.returncode == 22:
            status = (error.stdout or "").rstrip().rsplit("\n", 1)[-1]
            if not re.fullmatch(r"[45]\d{2}", status):
                raise BarkError("Bark returned an HTTP error. Check server access and proxy settings, then verify your device registration in Bark.") from None
            advice = ("Check server access and proxy settings." if status in ("401", "403", "407") else
                      "Wait before retrying; the server is rate limiting requests." if status == "429" else
                      "The Bark server is unavailable; retry later." if status.startswith("5") else
                      "Check the server origin and device registration in Bark, then rerun setup.")
            raise BarkError("Bark returned HTTP " + status + ". " + advice) from None
        raise BarkError("Cannot reach Bark. Check connectivity and proxy settings.") from None
    except (OSError, ValueError, AttributeError) as error:
        if isinstance(error, BarkError):
            raise
        raise BarkError("Bark returned an invalid response. Check the server origin.") from None


def compatibility_enabled(record):
    """The compatibility bridge follows the native user plugin switch and cache."""
    try:
        config = tomllib.loads((codex_home() / "config.toml").read_text())
        enabled = config.get("plugins", {}).get(record["plugin"], {}).get("enabled")
        return enabled is True and Path(record["plugin_root"]).is_dir()
    except (OSError, ValueError, KeyError, TypeError):
        return False


def delivery_status(event, outcome, message=None):
    # Keep only a local diagnostic summary, never the raw hook input or payload.
    if not config_dir().exists():
        return
    result = {"event": event, "outcome": outcome, "timestamp": datetime.now(timezone.utc).isoformat()}
    if message:
        result["message"] = message
    try:
        write_private(config_dir() / "last-delivery.json", json.dumps(result) + "\n")
    except OSError:
        pass


def hook(compat=False):
    # Always emit neutral JSON, including for Stop, which expects JSON on stdout.
    event_name = "unknown"
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return
        hook_name = event.get("hook_event_name")
        if not isinstance(hook_name, str) or hook_name not in EVENTS:
            return
        event_name, english, chinese = EVENTS[hook_name]
        record = registration()
        if compat and (record.get("mode") != "compat" or not compatibility_enabled(record)):
            return
        if not compat and record.get("mode") == "compat":
            # The native bundle may become available after a Codex upgrade. The
            # registered bridge remains the sole sender until install re-detects it.
            return
        config = load_config()
        state = chinese if config["language"] == "zh" else english
        if not config["enabled"] or event_name not in config["events"]:
            return
        if event.get("agent_id") or (hook_name == "SessionStart" and event.get("source") == "compact"):
            return
        name, project = context(event)
        fields = ("状态：", "项目：", "来源：", "模型：", "工具：", "方式：") if config["language"] == "zh" else ("Status: ", "Project: ", "Label: ", "Model: ", "Tool: ", "Source: ")
        body = [fields[0] + state]
        if project:
            body.append(fields[1] + project)
        label = single_line(os.environ.get("BARKNOTIFY_LABEL") or os.environ.get("CODEX_BARK_LABEL"))
        if label:
            body.append(fields[2] + label)
        model = single_line(event.get("model"))
        if model:
            body.append(fields[3] + model)
        if hook_name == "PermissionRequest":
            body.append(fields[4] + (single_line(event.get("tool_name")) or "unknown"))
        if hook_name == "SessionStart" and event.get("source") in ("resume", "fork"):
            body.append(fields[5] + event["source"])
        send(config, name + " · " + state, "\n".join(body), 1.5 if hook_name in ("Interrupt", "SessionEnd") else None)
        delivery_status(event_name, "sent")
    except BarkError as error:
        delivery_status(event_name, "failed", str(error))
    except Exception:
        # No exception, network response, or raw hook payload enters model context.
        delivery_status(event_name, "failed", "Invalid hook input or local configuration.")
    finally:
        print("{}")
