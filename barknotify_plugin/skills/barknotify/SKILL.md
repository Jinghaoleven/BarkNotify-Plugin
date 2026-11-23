---
name: barknotify
description: Set up or troubleshoot BarkNotify-Plugin, change notification preferences, or send a Bark push when requested. Automatic session alerts run through hooks.
---

Use the bundled `../../scripts/barknotify.py` relative to this skill directory. Invoke with Python 3.11+ for first integration; afterward its bootstrap can find the recorded interpreter. A separate global CLI is optional.

For setup, inspect `status` without printing raw private settings or environment keys. If the marketplace plugin lacks integration, run bundled `integrate`; preserve its source, credentials, and existing tool-managed installation method. After integration, the stable script is `${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py`.

Guide the user to install Bark on iPhone, allow notifications, and use **Copy → Copy Address and Key** (the main Copy button may copy a curl example). For self-hosted Bark, select that server first. Have the user run `setup` in a separate terminal on the Codex host, with the same user and home. Input is hidden. Never ask for the key/URL in chat, put it in arguments, or pass it through logged tools. Existing working credentials can be reused; `--key-stdin` is for a user's private password-manager pipe.

`setup` tests a candidate destination before saving it. Failure keeps the old destination. Initial setup enables notifications; later setup preserves the enabled/paused flag. `--no-test` skips verification when explicitly chosen. Server acceptance does not prove phone display: confirm with the user, then review `/hooks` and verify one natural turn-end notification. Never grant trust or bypass policies. Restart/resume only if the session's hooks are missing or stale.

Use `preferences --language en|zh`, `--events <comma-separated-events>`, `--group`, or `--level` for changes without a push or re-enabling. `enable` and `disable` toggle automatic notifications. `test` and `send --title <title> --body <body>` send real pushes, only for requested setup, verification, or notification. Do not repeatedly send tests without a reason.

Use `network` or `doctor --network --strict` before retrying after network failures. These use the same proxy as delivery, send no key/push, and never start a model turn. A CONNECT refusal is a routing problem; keep the key. `proxy --url socks5h://127.0.0.1:<port>` configures a Bark-only proxy; `--clear` restores the environment route. The optional standalone network extension runs on an exit machine and is installed separately; do not change global proxies or other SSH forwards to fix Bark.

For Git updates: marketplace upgrade → plugin add → bundled integrate. For local sources, update the checkout and skip marketplace upgrade. For tool-managed installations use `install`. The bridge follows the user plugin switch; disabling/removing it in `/plugins` stops delivery. `uninstall` removes owned bridge registrations and keeps settings.

Default events: `turn.completed`, `approval.required`. `events` lists others. Stop means the turn stopped, including awaiting a reply; it does not prove success. Approval requests may be resolved automatically. Delivery is best effort; unavailable hosts and force-killed sessions may never notify. Hooks return neutral JSON and do not decide approvals. Automatic pushes omit conversation content, commands, full paths, and session IDs; project/session names and model/tool metadata can appear on the lock screen.

Report configuration, network, phone display, hook trust, and automatic delivery according to observed evidence. Settings are discovered from the integration record or `BARKNOTIFY_CONFIG_DIR`; separate homes may use independent settings. Environment keys override the saved key.
