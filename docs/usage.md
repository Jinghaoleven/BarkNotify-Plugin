# Command reference

Run these commands on the host where you use Codex. For SSH or containers, open a terminal in that same environment.

## Manual setup from the installed plugin

First [prepare your iPhone and install the plugin](../README.md#install). Then run:

```bash
barknotify_script="$(codex plugin add barknotify@barknotify-plugin --json |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["installedPath"] + "/scripts/barknotify.py")')"
python3 "$barknotify_script" integrate
barknotify_script="${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py"
python3 "$barknotify_script" setup
python3 "$barknotify_script" doctor
```

At the hidden input prompt, paste the device address from Bark's **Copy → Copy Address and Key** menu. Older test URLs work too. Do not paste a curl command or send your address in chat. To use Chinese notifications, add `--language zh` to the setup command.

Confirm **BarkNotify-Plugin · Test** appears on your iPhone, then restart Codex and trust Bark in `/hooks`. Finish a short turn to verify automatic notifications.

## Everyday commands

After setup, use these commands from any directory:

```bash
barknotify_script="${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py"
python3 "$barknotify_script" status
python3 "$barknotify_script" test
python3 "$barknotify_script" disable
python3 "$barknotify_script" enable
```

`test` sends a real notification. `status` shows settings; `doctor` checks setup. A successful check does not confirm the phone displayed a notification.

## Preferences

Change language without sending another test:

```bash
python3 "$barknotify_script" setup --language zh --no-test
python3 "$barknotify_script" setup --language en --no-test
```

Choose notification events:

```bash
python3 "$barknotify_script" setup --events turn.completed,approval.required,turn.interrupted --no-test
```

| Event | Default | Notification |
| --- | --- | --- |
| `turn.completed` | On | A turn ended, including when Codex waits for your reply |
| `approval.required` | On | Approval was requested; it may be resolved automatically |
| `session.started` | Off | A session started or resumed |
| `turn.started` | Off | Codex received a prompt |
| `turn.interrupted` | Off | A turn was interrupted |
| `session.ended` | Off | A session ended; delivery may be delayed |

Choose a notification group and presentation level:

```bash
python3 "$barknotify_script" setup --group codex --level timeSensitive --no-test
```

Levels are `active` (default), `passive`, `timeSensitive`, and `critical`. Presentation depends on iOS settings; `critical` requires additional permission in Bark. Preference changes keep your saved key. `--no-test` enables notifications without sending a test.

## Network and proxy troubleshooting

Check access without sending a notification:

```bash
curl -q -sS -o /dev/null -w 'HTTP %{http_code}\n' \
  --connect-timeout 3 --max-time 8 https://api.day.app/ping
```

HTTP 200 means the default Bark server is reachable. CONNECT 403 means the proxy refused access: ask your network administrator to allow `api.day.app:443`, or configure a working proxy in the terminal used to launch Codex. Keep your saved key. GitHub access alone does not confirm Bark access.

Once access works, run `setup` again and press Enter to keep the key. Confirm the phone test. For HTTP 429, wait before retrying; for HTTP 5xx, retry when the Bark server recovers.

## Phone address and settings

To change phones, run `setup` and enter the new phone's address. For a self-hosted Bark server, add and select it in the App before copying the address.

Settings are stored under `${XDG_CONFIG_HOME:-~/.config}/barknotify-plugin`. Use `--config-dir` to choose another settings directory. `BARKNOTIFY_DEVICE_KEY` can supply a key through your local environment; keep it out of chat and tracked files.

Provider launchers sharing `CODEX_HOME` use one installation. If you use separate Codex homes, install and configure the plugin in each one.

## Updates

```bash
codex plugin marketplace upgrade barknotify-plugin
codex plugin add barknotify@barknotify-plugin
python3 "${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py" integrate
```

Restart Codex and review `/hooks`. Your phone address and preferences are kept. Run the last command again after updating Codex itself.

## Removal

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py" uninstall
```

Settings are kept for reinstallation. If already removed through `/plugins`, run `python3 barknotify_plugin/scripts/barknotify.py uninstall` from a repository checkout to finish cleanup.

To remove the marketplace too:

```bash
codex plugin marketplace remove barknotify-plugin
```
