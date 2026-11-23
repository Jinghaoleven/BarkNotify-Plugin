# Developer guide

User setup is in the [README](../README.md) and [commands](usage.md). Development requirements: Python 3.11+ for the main plugin; Python 3.9+ for the standalone tunnel. Both use only the standard library at runtime, with curl/OpenSSH as external commands.

## Validation

```bash
python3 -m unittest discover -s tests -v
BARKNOTIFY_REQUIRE_NATIVE_TEST=1 python3 tests/native_install.py
BARKNOTIFY_REQUIRE_SSH_TEST=1 python3 tests/ssh_tunnel.py
uv build
uv build extensions/reverse-socks --out-dir dist/tunnel
```

Unit tests use disposable configuration, a mock Bark server and SOCKS server, and fake service managers. Native tests use real Codex in disposable homes without model turns or pushes. Real SSH tests need Linux sshd, ss, curl and permission to run a disposable sshd; CI provides them. A skipped integration test is not a pass.

CI tests Python 3.11/3.13 on Ubuntu/macOS, fresh built wheels outside the checkout, Codex CLI 0.166.0 native integration on both platforms, and real SSH recovery on Linux. Results of new workflow runs must be checked before release; configuring a CI job is not evidence that it has passed.

Local acceptance observations are in [compatibility](compatibility.md). See [releasing](releasing.md) for artifact checks.

## Configuration and delivery

Schema 2 is written by 0.5.0; schema 1 remains readable. Older 0.4.2 rejects schema 2 instead of silently ignoring its proxy. Upgrade runtime and configuration together; do not backport new fields into an old runtime.

Setup stages and tests a destination before saving. A settings lock coordinates writers and hook snapshots; failed writes restore prior configuration/key files. This is rollback across two files, not crash-safe database atomicity. A hook arriving during a settings transaction skips delivery rather than waiting or reading a mixed pair. There is no persistent queue or replay; all delivery remains best effort.

Local history retains 20 summaries (event, outcome, source, timestamp, safe error). Status uses a field whitelist. New diagnostics must not expose credentials, raw server responses or conversation payloads. Registration records the interpreter, runtime version, digest and capabilities; the bundled launcher can re-exec a supported interpreter without consuming hook stdin.

## Standalone tunnel

The extension owns a profile-specific SSH master and short, private control socket. It clears inherited forwards and requests remote loopback SOCKS with OpenSSH reverse dynamic forwarding. It verifies ss/lsof listener addresses and rejects wildcard binding. Mux probes cannot silently create a fallback SSH connection.

The opt-in launchd/systemd user service copies a stable runtime and invokes `ensure` every 30 seconds. SSH heartbeat is 20 seconds × 3; failed starts back off up to 120 seconds. Recovery detects SSH connection loss; Bark health failures alone do not restart SSH. Explicit down disables recovery before closing only the owned master. Service installation rolls back settings, units and runtime on ordinary failures.

No device key belongs on the exit machine. Existing forwarding utilities and system-wide proxy settings are outside the extension's ownership.

## Maintenance

[Compatibility](compatibility.md) covers hook selection and policy limits. [Product review](product-review.md) records documentation references.

README illustrations show Bark notifications on iPhone and a paired Apple Watch using fictional content. Regenerate both with `python3 docs/assets/render_preview.py` after installing Pillow and system fonts (DejaVu Sans and Noto Sans CJK on Linux; system fonts on macOS). Reference images inform the layout; the renderer does not read them. Keep original photographs, private wallpaper, host/project names, keys and image metadata out of published artwork. Retain the [Bark icon attribution and upstream MIT notice](assets/THIRD_PARTY_NOTICES.md) with the documentation assets.
