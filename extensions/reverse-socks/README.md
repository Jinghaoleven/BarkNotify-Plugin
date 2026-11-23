# Reverse SOCKS extension

Route a restricted Codex host's Bark requests through another Mac or Linux machine using OpenSSH. This optional **barknotify-tunnel** package owns its SSH connection and works independently of shell forwarding tools.

[简体中文](README.zh-CN.md)

## Install and start

On the machine with working Bark access, install Python 3.9+ and OpenSSH 7.6+. Configure an SSH alias for the Codex host and verify key-based, noninteractive login first. The Codex host needs curl, `ss` or `lsof`, and SSH remote forwarding enabled.

From a repository checkout:

```bash
python3 -m venv ~/.local/share/barknotify-tunnel/venv
~/.local/share/barknotify-tunnel/venv/bin/pip install ./extensions/reverse-socks
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel configure --host codex-host
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel up
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel check
```

`codex-host` is your SSH alias. Add `--port 10810` if the default remote port 10808 is occupied. Existing forwards remain untouched.

On the Codex host, after integrating BarkNotify-Plugin 0.5.0+:

```bash
barknotify_script="${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py"
python3 "$barknotify_script" proxy --url socks5h://127.0.0.1:10808
python3 "$barknotify_script" network
```

Use the configured port in the proxy URL. No device key is needed by the extension.

## Automatic recovery

On the exit machine:

```bash
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel service install
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel status
```

This enables a macOS LaunchAgent or Linux user systemd timer, with connection checks every 30 seconds and retry backoff up to two minutes. The service keeps its own runtime copy, so moving the checkout does not break it. It runs in your user session; Linux persistence after logout requires user lingering configured by your administrator.

Keep the exit machine awake and connected. Recovery starts after SSH detects failure; it does not eliminate brief outages, machine sleep, VPN failures, or server-side restrictions. In-flight notifications are not queued or replayed.

## Stop or remove

```bash
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel down
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel service uninstall
```

`down` stops only the owned connection and disables recovery until `up`. Uninstall removes recovery and stops the tunnel; settings remain. Use `service install --dry-run` to preview service files. On the Codex host, `proxy --clear` returns Bark to its usual route.

## Troubleshooting and access

`check` verifies the remote listener and Bark `/ping`; it sends no push. A busy port fails without taking it over. Forwarding denial requires checking sshd policy. Wildcard listeners are rejected: keep server `GatewayPorts no`.

The SOCKS endpoint is loopback-only but has no authentication. Other processes sharing the Codex host's network namespace can use it. It routes their traffic through the exit machine; use only a host you trust.

For multiple independent tunnels, put `--name <profile>` before the command. Settings are in `~/.config/barknotify-tunnel/<profile>` (or `XDG_CONFIG_HOME`).
