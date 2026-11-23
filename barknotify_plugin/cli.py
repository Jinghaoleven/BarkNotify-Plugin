"""A single public entry point for installing and managing BarkNotify-Plugin."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from . import __version__, installer, runtime
from .rpc import inspect_hooks


def parser():
    root = argparse.ArgumentParser(prog="barknotify-plugin", description="Bark push notifications for Codex sessions.")
    root.add_argument("--version", action="version", version="barknotify-plugin " + __version__)
    commands = root.add_subparsers(dest="action", required=True)
    for action, description in {
        "install": "Install or upgrade the Codex plugin",
        "integrate": "Connect an installed plugin, preserving its marketplace source",
        "uninstall": "Remove the plugin and compatibility hooks; keep private settings",
        "setup": "Configure Bark locally and send a verification push",
        "configure": "Alias for setup",
        "status": "Show configuration and installation status without credentials",
        "doctor": "Check dependencies, installation, configuration, and hook trust",
        "proxy": "Set or clear the Bark-only proxy without sending a push",
        "preferences": "Change preferences without enabling notifications or sending a push",
        "network": "Check Bark connectivity without sending a notification",
        "events": "List supported notification events",
        "enable": "Enable automatic notifications",
        "disable": "Disable automatic notifications",
        "test": "Send one verification push",
        "send": "Send a requested push",
        "init": "Create disabled default settings without sending a push",
        "hook": argparse.SUPPRESS,
    }.items():
        command = commands.add_parser(action, **({"help": description} if description != argparse.SUPPRESS else {}))
        command.add_argument("--config-dir", help="Private Bark configuration directory")
        command.add_argument("--codex-home", action="append" if action in ("install", "integrate", "uninstall") else "store",
                             help="Target Codex home (repeat for install/integrate/uninstall)")
        if action in ("install", "integrate", "uninstall", "doctor", "setup", "configure"):
            command.add_argument("--codex-bin", help="Path to the Codex executable")
        if action in ("install", "integrate", "uninstall"):
            command.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
        if action in ("install", "integrate", "setup", "configure"):
            command.add_argument("--mode", choices=("auto", "native", "compat"), default="auto",
                                 help="Use bundled hooks when exposed by Codex (default: auto)")
        if action in ("setup", "configure"):
            command.add_argument("--integrate", action="store_true", help="Connect the installed marketplace plugin before setup")
            command.add_argument("--server", help="Bark server origin; full push URLs are entered privately")
            command.add_argument("--key-stdin", action="store_true", help="Read a push URL or key from stdin")
            command.add_argument("--events", help="Comma-separated event names; use 'events' to list them")
            command.add_argument("--language", choices=("en", "zh"), help="Notification language (default: en)")
            command.add_argument("--group", help="Bark notification group")
            command.add_argument("--level", choices=("active", "passive", "timeSensitive", "critical"))
            command.add_argument("--no-test", action="store_true", help="Save without a push; preserve the existing enabled state")
        if action == "preferences":
            command.add_argument("--language", choices=("en", "zh"))
            command.add_argument("--events", help="Comma-separated event names")
            command.add_argument("--group")
            command.add_argument("--level", choices=("active", "passive", "timeSensitive", "critical"))
        if action in ("status", "doctor"):
            command.add_argument("--json", action="store_true", help="Output machine-readable JSON")
        if action == "doctor":
            command.add_argument("--network", action="store_true", help="Probe Bark through the configured route; no push")
            command.add_argument("--strict", action="store_true", help="Return failure for warnings as well as errors")
        if action == "proxy":
            proxy = command.add_mutually_exclusive_group(required=True)
            proxy.add_argument("--url", help="HTTP(S) or SOCKS5 proxy URL with a port, without credentials")
            proxy.add_argument("--clear", action="store_true", help="Return to the host's proxy environment")
        if action == "send":
            command.add_argument("--title", required=True)
            command.add_argument("--body", required=True)
        if action == "hook":
            command.add_argument("--compat", action="store_true", help=argparse.SUPPRESS)
    return root


def settings_status():
    config = runtime.load_config()
    record = runtime.registration()
    try:
        runtime.device_key(config)
        available = True
    except (runtime.BarkError, OSError):
        available = False
    installed = bool(record) and Path(record.get("plugin_root", "/nonexistent")).is_dir()
    enabled = runtime.compatibility_enabled(record) if record else None
    result = {"version": __version__, "plugin_version": record.get("version"),
              "config_dir": str(runtime.config_dir()), "codex_home": str(runtime.codex_home()),
              "installed": installed, "mode": record.get("mode", "unmanaged"),
              "distribution": record.get("distribution", "tool" if record else "unmanaged"), "plugin_enabled": enabled,
              "device_key_status": "available" if available else "missing",
              "python_executable": str(Path(sys.executable).resolve()),
              "runtime_version": record.get("runtime_version"),
              "capabilities": record.get("capabilities", []),
              **{field: config.get(field, default) for field, default in runtime.DEFAULTS.items()}}
    last = runtime.config_dir() / "last-delivery.json"
    if last.exists():
        try:
            item = json.loads(last.read_text())
            if isinstance(item, dict):
                result["last_delivery"] = {field: item[field] for field in ("event", "outcome", "timestamp", "source") if field in item}
        except (OSError, ValueError):
            result["last_delivery"] = {"outcome": "unavailable"}
    return result


def setup(args):
    if args.integrate:
        installer.integrate([runtime.codex_home()], runtime.config_dir(), args.codex_bin, args.mode)
    config = runtime.initialize()
    for field, value in (("server_url", args.server), ("language", args.language), ("group", args.group), ("level", args.level)):
        if value is not None:
            config[field] = value
    if args.events is not None:
        config["events"] = [event.strip() for event in args.events.split(",") if event.strip()]
    try:
        runtime.validate(config)
    except ValueError as error:
        raise runtime.BarkError(str(error)) from None
    try:
        runtime.device_key(config)
        available = True
    except (runtime.BarkError, OSError):
        available = False
    changed = any(value is not None for value in (args.server, args.events, args.language, args.group, args.level))
    if args.key_stdin:
        entered = sys.stdin.read().strip()
    elif not available or not changed:
        if not sys.stdin.isatty():
            raise runtime.BarkError("Setup needs private input. Run it in a terminal, or pipe the push URL using --key-stdin.")
        import getpass
        entered = getpass.getpass("Bark push URL or device key (hidden" + ("; Enter to keep current" if available else "") + "): ")
    else:
        entered = ""
    if entered:
        # A full URL chooses its own origin; a bare key keeps the current origin.
        origin, key = runtime.parse_destination(entered, args.server if "://" in entered else config["server_url"])
        environment_name = runtime.key_environment(config)
        override = os.environ.get(environment_name, "").strip()
        if override and override != key:
            raise runtime.BarkError("The environment key overrides saved credentials. Unset " + environment_name + " before changing the key.")
        config["server_url"] = origin
        candidate_key = key
    elif args.key_stdin or not available:
        raise runtime.BarkError("The device key is empty. Enter the push URL shown by Bark.")
    candidate_key = candidate_key if entered else runtime.device_key(config)
    # Initial setup enables delivery; changing an existing destination/preferences
    # preserves the user's enabled flag. No candidate files are saved before test.
    if not available:
        config["enabled"] = True
    if not args.no_test:
        try:
            runtime.send(config, "BarkNotify-Plugin · Test", "If you see this on your phone, Bark delivery is working." if config["language"] == "en"
                         else "如果你在手机上看到这条消息，说明 Bark 推送已送达。", key=candidate_key)
        except runtime.BarkError as error:
            runtime.delivery_status("test", "failed", str(error), "manual")
            raise
        runtime.delivery_status("test", "sent", source="manual")
        print("Bark server accepted the test push. Check that it appears on your phone.")
    runtime.commit_settings(config, candidate_key if entered else None)
    print("BarkNotify-Plugin configured (" + config["language"] + "); notifications " + ("enabled." if config["enabled"] else "paused."))
    if runtime.registration():
        print("Review Bark in /hooks. If hooks are missing after installation/upgrade, restart or resume Codex.")
    else:
        print("Connect an installed plugin with integrate, or use install for a standalone tool installation.")


def doctor(args):
    checks = []

    def check(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    check("python", "ok", "Python " + sys.version.split()[0])
    check("curl", "ok" if shutil.which("curl") else "error", "curl is available" if shutil.which("curl") else "Install curl")
    try:
        state = settings_status()
        check("configuration", "ok", "Private settings are valid")
        check("proxy", "configured", ("Bark-only proxy: " + state["proxy_url"] + " (connectivity not tested)")
              if state["proxy_url"] else "Using the host's proxy environment (connectivity not tested)")
        check("device_key", "ok" if state["device_key_status"] == "available" else "error", "Key available" if state["device_key_status"] == "available" else "Run barknotify-plugin setup")
        check("installation", "ok" if state["installed"] else "error", "Mode: " + state["mode"] if state["installed"] else "Run integrate for an installed plugin, or install for a standalone tool")
        if state["installed"]:
            check("runtime", "ok" if state["runtime_version"] == __version__ else "warning",
                  "Recorded runtime: " + str(state["runtime_version"] or "unknown") + "; current command: " + __version__ +
                  ("" if state["runtime_version"] == __version__ else ". Refresh integration with the updated plugin"))
        if state["installed"] and not state["plugin_enabled"]:
            check("plugin", "warning", "Bark is disabled in Codex. Enable it in /plugins")
        if not state["enabled"]:
            check("notifications", "warning", "Delivery is disabled. Run barknotify-plugin enable")
        if state.get("last_delivery", {}).get("outcome") == "failed":
            check("last_delivery", "warning", "The latest push failed; run network to check the route")
        if args.network:
            try:
                check("network", "ok", runtime.network_check(runtime.load_config()))
            except runtime.BarkError as error:
                check("network", "error", str(error))
    except runtime.BarkError as error:
        check("configuration", "error", str(error))
    record = runtime.registration()
    try:
        binary = installer.resolve_binary(args.codex_bin or record.get("codex_bin"))
        check("codex", "ok", "Native plugin management is available")
        if record:
            hooks = inspect_hooks(binary, runtime.codex_home())
            matching = [hook for hook in hooks if (record.get("mode") == "native" and hook.get("pluginId") == installer.SELECTOR) or
                        (record.get("mode") == "compat" and hook.get("command") == record.get("command"))]
            if len(matching) != 6:
                check("hooks", "error", "Hook registrations are incomplete. Run " + ("integrate" if record.get("distribution") == "marketplace" else "install"))
            else:
                untrusted = sum(hook.get("trustStatus") not in ("trusted", "managed") for hook in matching)
                check("hook_trust", "warning" if untrusted else "ok", "Review Bark in /hooks" if untrusted else "Bark hooks are trusted")
    except (runtime.BarkError, OSError, ValueError) as error:
        check("codex", "warning", str(error))
    if args.json:
        print(json.dumps({"checks": checks, "ready": not any(c["status"] in ("error", "warning") for c in checks),
                          "network_checked": args.network, "scope": "selected Codex home; phone display not verified"}, indent=2))
    else:
        for item in checks:
            print(item["status"].upper() + "  " + item["check"] + ": " + item["detail"])
        print("Doctor does not send a push or grant hook trust. Use barknotify-plugin test to check delivery.")
    return 1 if any(item["status"] == "error" or (args.strict and item["status"] == "warning") for item in checks) else 0


def main(argv=None):
    args = parser().parse_args(argv)
    selected_home = (args.codex_home[0] if len(args.codex_home) == 1 else None) if isinstance(args.codex_home, list) else args.codex_home
    if selected_home:
        os.environ["CODEX_HOME"] = str(Path(selected_home).expanduser().resolve())
    if args.config_dir:
        os.environ["BARKNOTIFY_CONFIG_DIR"] = str(Path(args.config_dir).expanduser().resolve())
    if args.action == "hook":
        runtime.hook(args.compat)
        return 0
    try:
        if args.action in ("install", "integrate", "uninstall"):
            homes = args.codex_home or [runtime.codex_home()]
            config = runtime.config_dir()
            if args.action == "install":
                installer.install(homes, config, args.codex_bin, args.mode, args.dry_run)
            elif args.action == "integrate":
                installer.integrate(homes, config, args.codex_bin, args.mode, args.dry_run)
            else:
                installer.uninstall(homes, config, args.codex_bin, args.dry_run)
        elif args.action in ("setup", "configure"):
            with runtime.settings_lock():
                setup(args)
        elif args.action == "init":
            runtime.initialize()
            print("Disabled default settings created in " + str(runtime.config_dir()) + ".")
        elif args.action == "events":
            for name, english, _ in runtime.EVENTS.values():
                print(name.ljust(22) + english + (" (default)" if name in runtime.DEFAULTS["events"] else ""))
        elif args.action == "doctor":
            return doctor(args)
        elif args.action == "status":
            result = settings_status()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print("BarkNotify-Plugin " + __version__ + " · " + ("enabled" if result["enabled"] else "disabled"))
                print("Plugin version: " + (result["plugin_version"] or "unintegrated") + " · " + result["distribution"])
                print("Installation: " + result["mode"] + " · key " + result["device_key_status"])
                print("Codex plugin: " + ("enabled" if result["plugin_enabled"] else "disabled or uninstalled"))
                print("Server: " + result["server_url"] + " · language " + result["language"])
                print("Proxy: " + (result["proxy_url"] or "host environment"))
                print("Python: " + result["python_executable"])
                print("Events: " + ", ".join(result["events"]))
                if result.get("last_delivery"):
                    last = result["last_delivery"]
                    print("Last delivery: " + last.get("outcome", "unknown") + " · " + last.get("source", "hook") + " · " + last.get("timestamp", "unknown"))
                print("For hook trust and readiness: doctor --network --strict")
        else:
            config = runtime.load_config()
            if args.action == "network":
                print(runtime.network_check(config))
            elif args.action == "preferences":
                values = {field: getattr(args, field) for field in ("language", "events", "group", "level") if getattr(args, field) is not None}
                if not values:
                    raise runtime.BarkError("Specify at least one preference to change.")
                if "events" in values:
                    values["events"] = [event.strip() for event in values["events"].split(",") if event.strip()]
                with runtime.settings_lock():
                    config = {**runtime.load_config(), **values}
                    try:
                        runtime.validate(config)
                    except ValueError as error:
                        raise runtime.BarkError(str(error)) from None
                    runtime.save_config(config)
                print("Preferences saved; notifications " + ("enabled." if config["enabled"] else "paused."))
            elif args.action == "proxy":
                record = runtime.registration()
                if args.url and record and "bark-proxy" not in record.get("capabilities", []):
                    raise runtime.BarkError("The registered runtime does not declare Bark proxy support. Upgrade the plugin to 0.5.0+ and run integrate first.")
                config["proxy_url"] = None if args.clear else args.url
                try:
                    runtime.validate(config)
                except ValueError as error:
                    raise runtime.BarkError(str(error)) from None
                with runtime.settings_lock():
                    current = runtime.load_config()
                    current["proxy_url"] = config["proxy_url"]
                    runtime.save_config(current)
                print("Bark proxy: " + (config["proxy_url"] or "host environment") + ". Notification settings preserved; no push sent.")
            elif args.action in ("enable", "disable"):
                if args.action == "enable":
                    runtime.device_key(config)
                config["enabled"] = args.action == "enable"
                with runtime.settings_lock():
                    current = runtime.load_config()
                    current["enabled"] = config["enabled"]
                    runtime.save_config(current)
                print("Bark notifications " + ("enabled." if config["enabled"] else "disabled."))
            else:
                try:
                    with runtime.settings_lock():
                        config = runtime.load_config()
                        key = runtime.device_key(config)
                    runtime.send(config, "BarkNotify-Plugin · Test" if args.action == "test" else args.title,
                             ("If you see this on your phone, Bark delivery is working." if config["language"] == "en"
                              else "如果你在手机上看到这条消息，说明 Bark 推送已送达。") if args.action == "test" else args.body, key=key)
                except runtime.BarkError as error:
                    runtime.delivery_status(args.action, "failed", str(error), "manual")
                    raise
                runtime.delivery_status(args.action, "sent", source="manual")
                print("Bark server accepted the push. Check that it appears on your phone.")
        return 0
    except runtime.BarkError as error:
        print("barknotify-plugin: " + str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, subprocess.SubprocessError):
        print("barknotify-plugin: Operation failed. Check file permissions and run barknotify-plugin doctor.", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Setup cancelled.", file=sys.stderr)
        return 130
