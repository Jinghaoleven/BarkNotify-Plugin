# CLI and configuration

Every command is available through the installed bundle's `scripts/barknotify.py`. No checkout or global CLI is needed for a marketplace installation; use the steps below. Later examples use the optional global `barknotify-plugin` command for brevity.

## Manual setup from the installed plugin

Follow the [iPhone preparation steps](../README.md#quick-start), and register the marketplace as described there. In a terminal on the **host running Codex**, install or refresh the plugin and discover its script from Codex's JSON response:

```bash
barknotify_script="$(codex plugin add barknotify@barknotify-plugin --json |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["installedPath"] + "/scripts/barknotify.py")')"
python3 "$barknotify_script" integrate
barknotify_script="${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py"
python3 "$barknotify_script" setup
python3 "$barknotify_script" doctor
```

Integration creates the stable per-home script used by the last three commands. Avoid hardcoding a versioned cache path: plugin refreshes can replace it. Once integrated, you can run this from any working directory:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py" setup
```

For SSH, containers, or remote workspaces, open a separate terminal in that same environment, with the same user and `CODEX_HOME`. Configuring your laptop's Codex does not configure a remote host. Copy **Address and Key** from Bark on your iPhone, transfer it privately to that terminal, and paste it only at setup's hidden input prompt. Never paste it into an agent tool transcript or chat. Add `--language zh` for Chinese notifications.

Confirm **BarkNotify-Plugin · Test** appears on the phone. Then start a new Codex session using the same home and review Bark in `/hooks`. Integration registers six lifecycle handlers; only turn completion and approval requests send notifications by default. `doctor` reports a missing key and disabled delivery before setup, and untrusted hooks until your review; these are pending setup steps. Do not enable delivery alone to resolve a missing key. A successful `doctor` does not verify phone display.

## Optional CLI

Clone the repository:

```bash
git clone https://github.com/Jinghaoleven/BarkNotify-Plugin.git
cd BarkNotify-Plugin
uv tool install .
```

Alternatively use `pipx install .`. Either tool can also install a downloaded release wheel. There is no published PyPI package yet. Installing the CLI alone does not connect session hooks.

For an already installed marketplace plugin:

```bash
barknotify-plugin setup --integrate
barknotify-plugin doctor
```

For a standalone tool-managed installation:

```bash
barknotify-plugin install
barknotify-plugin setup
barknotify-plugin doctor
```

`install` creates a local marketplace from the tool's bundle. `integrate` refreshes an already installed plugin from its existing marketplace and connects hooks without replacing that source. `install` refuses to overwrite an existing native marketplace installation; use `integrate` for it.

## Manual setup from a checkout

Follow the [iPhone preparation steps](../README.md#quick-start), then register/install the plugin as described there. From a checkout, configure without installing a global CLI:

```bash
python3 barknotify_plugin/scripts/barknotify.py setup --integrate
python3 barknotify_plugin/scripts/barknotify.py doctor
```

Use `setup --integrate --language zh` for Chinese notifications. Copy **Address and Key** from the Bark App's Copy menu and enter it in the local terminal. Older example push URLs are accepted too; example titles, bodies, and query parameters are discarded. A curl command or JSON example is not a push URL.

## Network and proxy troubleshooting

Check connectivity from the same terminal that runs setup. This check uses no device key and sends no notification:

```bash
curl -q -sS -o /dev/null -w 'HTTP %{http_code}\n' \
  --connect-timeout 3 --max-time 8 https://api.day.app/ping
```

A reachable default Bark server returns HTTP 200. `Received HTTP code 403 from proxy after CONNECT`, or `Proxy refused the Bark connection (CONNECT HTTP 403)`, means the proxy refused the connection before it reached Bark. Keep the saved key; configure a proxy that can reach `api.day.app:443`, or arrange access through your host's network. Unsetting proxy variables helps only when direct access works. For a self-hosted server, check that server's origin instead.

The runtime uses curl's `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` environment settings. Make the working network configuration available to both setup and the Codex process that runs hooks; setting it only for a one-off test is insufficient for automatic notifications. Keep proxy passwords out of chat, command arguments, and tracked files.

Once connectivity works, rerun `setup` and press Enter at its hidden prompt to keep the saved key. Confirm the phone test before restarting Codex and reviewing `/hooks`. HTTP 400/404 may require checking the server origin and the device address in Bark; HTTP 429 means wait before retrying, and HTTP 5xx indicates a server failure. Error output reports only status and recovery guidance, never server response bodies.

## Preferences

```bash
barknotify-plugin events
barknotify-plugin setup --events turn.completed,approval.required,turn.interrupted --no-test
barknotify-plugin setup --language zh --no-test
barknotify-plugin setup --group codex --level timeSensitive --no-test
barknotify-plugin status --json
barknotify-plugin doctor --json
```

Preference changes reuse the key. `--no-test` saves and enables without a verification push. Interruption levels are `active`, `passive`, `timeSensitive`, and `critical`; actual presentation depends on iOS permissions. `test` checks delivery even while automatic notifications are disabled. `enable` and `disable` control automatic delivery.

Requested one-off notification:

```bash
barknotify-plugin send --title "Build finished" --body "Your build is ready to review."
```

## Independent Codex homes

Native marketplace registration and plugin installation apply to the current `CODEX_HOME`. Register and install Bark in each desired home before connecting them:

```bash
barknotify-plugin integrate --codex-home ~/.codex-alpha --codex-home ~/.codex-beta
```

For tool-managed installations use `install` with the same repeated options. `uninstall` also accepts multiple homes. Other commands take one `--codex-home`. Launchers sharing a home need one installation regardless of provider.

`--codex-bin` selects the executable for install, integrate, setup integration, and diagnostics. `--config-dir` or `BARKNOTIFY_CONFIG_DIR` selects private settings. Otherwise commands discover the directory recorded in the selected Codex home, then fall back to `${XDG_CONFIG_HOME:-~/.config}/barknotify-plugin`. Use separate directories for different keys or preferences.

`install --dry-run`, `integrate --dry-run`, and `uninstall --dry-run` preview changes. Integration uses a stable per-home runtime for compatibility handlers. Changed host configuration gets private backups. Install/integrate restore host files and owned caches if they fail.

## Credentials

Use `setup` to enter a URL or key locally with hidden input, after preparing the Bark App on your phone. Use the Bark device key, not an APNs token. A full URL selects its server; `--server` accepts an origin without a key or `/push` path.

`setup --key-stdin` supports a local password-manager pipe. The variable named by `device_key_env` (default `BARKNOTIFY_DEVICE_KEY`) overrides a saved key. Setup reports a conflicting environment key before replacing saved credentials. Keys never enter arguments, status output, or hook output. Do not share credentials or unredacted URLs in issues.

Legacy `CODEX_BARK_CONFIG_DIR`, `CODEX_BARK_DEVICE_KEY`, and `CODEX_BARK_LABEL` remain accepted; their `BARKNOTIFY_*` equivalents take precedence. Existing recorded config directories and `~/.config/codex-bark` settings are reused when no new directory is selected. Keys are not copied into plugin caches. Custom `device_key_env` names retain their exact behavior.

## Updates

| Installation | Update sequence |
| --- | --- |
| Checkout marketplace | Update checkout → `codex plugin add barknotify@barknotify-plugin` → bundled `integrate` |
| Git marketplace | `codex plugin marketplace upgrade barknotify-plugin` → `codex plugin add barknotify@barknotify-plugin` → bundled `integrate` |
| Tool-managed plugin | Update checkout/wheel → refresh CLI → `barknotify-plugin install` |

Refresh a checkout-installed tool with `uv tool install --force .` or `pipx install --force .` from the updated checkout. Marketplace upgrades do not update a separate CLI; CLI updates do not refresh Git marketplace bundles.

`status` reports the executing runtime version and integrated plugin version separately, plus the installation method. `--version` reports only the executing runtime.

Restart Codex and review `/hooks` after changes. After updating Codex itself run `integrate` for marketplace installations or `install` for tool-managed installations. Private credentials and preferences survive. Managed 0.1 installations migrate through `install` while preserving settings.

## Removal

Run bundled `uninstall` or `barknotify-plugin uninstall` before native removal if you rely on the cache for cleanup. It removes the plugin, owned compatibility handlers, and per-home runtime, preserving settings and marketplace registration. After native removal use the checkout or CLI to finish cleanup.

Remove an optional CLI with `uv tool uninstall barknotify-plugin` or `pipx uninstall barknotify-plugin`. Remove the marketplace with `codex plugin marketplace remove barknotify-plugin` after cleanup. Delete private settings separately only if you intend to forget the key and preferences.
