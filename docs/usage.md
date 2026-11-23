# Commands

Run on the Codex host, with the same user and `CODEX_HOME` as your sessions. Use **Python 3.11+**. The bundled launcher also finds a supported interpreter saved at integration time or available as `python3.11`–`python3.14`; `BARKNOTIFY_PYTHON` can select one explicitly.

## Manual setup

After installing the marketplace plugin:

```bash
barknotify_script="$(codex plugin add barknotify@barknotify-plugin --json |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["installedPath"] + "/scripts/barknotify.py")')"
python3.11 "$barknotify_script" integrate
barknotify_script="${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py"
python3 "$barknotify_script" setup --language zh
```

Replace `python3.11` with your installed Python 3.11+ interpreter if needed. Paste the device address at the hidden prompt, never into chat or command arguments. Confirm the test on your phone, review `/hooks`, and verify a natural turn-ending notification. Restart/resume only if the hooks are missing or stale.

## Everyday commands

Use the stable script after integration:

```bash
barknotify_script="${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py"
python3 "$barknotify_script" status
python3 "$barknotify_script" doctor --network --strict
python3 "$barknotify_script" test
python3 "$barknotify_script" disable
python3 "$barknotify_script" enable
```

`test` sends a real push, including while paused. `status` shows settings and the latest delivery; `doctor` checks the selected home, not what an already-open session has loaded. `--strict` exits unsuccessfully for unresolved warnings such as untrusted hooks. It never grants trust or verifies phone display.

## Preferences

```bash
python3 "$barknotify_script" preferences --language zh
python3 "$barknotify_script" preferences --events turn.completed,approval.required,turn.interrupted
python3 "$barknotify_script" preferences --group codex --level timeSensitive
```

These commands preserve pause state and credentials, and send no push. Changes apply to subsequent notifications without restarting.

| Event | Default | Meaning |
| --- | --- | --- |
| `turn.completed` | On | A turn ended, possibly awaiting your reply |
| `approval.required` | On | Approval requested; automatic review may resolve it |
| `session.started` | Off | Started or resumed |
| `turn.started` | Off | Prompt submitted |
| `turn.interrupted` | Off | User interrupted |
| `session.ended` | Off | Session ended according to runtime lifetime |

Levels: `active`, `passive`, `timeSensitive`, `critical`. iOS controls presentation; critical alerts require additional Bark permission.

## Network

```bash
python3 "$barknotify_script" network
python3 "$barknotify_script" proxy --url socks5h://127.0.0.1:10808
python3 "$barknotify_script" network
python3 "$barknotify_script" proxy --clear
```

`network` checks the configured server's `/ping` through the **same route as pushes**, without a key or notification. A dedicated proxy overrides environment proxy and `NO_PROXY` settings for Bark only. Supported schemes: `http`, `https`, `socks5`, `socks5h`, with a port and no credentials. `socks5h` resolves the server through the proxy; `--clear` uses the host's environment again.

CONNECT 403 is a proxy access failure; keep your key and fix the route. HTTP 429 requires waiting; retry HTTP 5xx after server recovery. For restricted hosts, use the [standalone tunnel extension](../extensions/reverse-socks/README.md). Once the route works, run one `test` and confirm phone display.

## Device and settings

Run `setup` to change the receiving device. The candidate destination is tested before replacing saved settings; failure preserves the previous destination and pause state. `setup --no-test` deliberately skips verification. Initial setup enables delivery; later setup preserves the current enabled flag.

Settings default to `${XDG_CONFIG_HOME:-~/.config}/barknotify-plugin`. The key is separate from configuration. `--config-dir` selects another directory; `BARKNOTIFY_DEVICE_KEY` overrides the saved key. Separate Codex homes can use independent settings.

## Updates

```bash
codex plugin marketplace upgrade barknotify-plugin
codex plugin add barknotify@barknotify-plugin
python3 "$barknotify_script" integrate
```

Review `/hooks` after updates. Restart/resume if the current session has stale hooks. Run `integrate` again after upgrading Codex. For a local marketplace, update its checkout and skip the first command.

## Removal

```bash
python3 "$barknotify_script" uninstall
```

If removed through `/plugins` first, the stable script can still finish cleanup. A checkout or optional installed CLI can also run `uninstall`. Saved settings remain. Remove the marketplace separately with `codex plugin marketplace remove barknotify-plugin`.
