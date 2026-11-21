# CLI and configuration

Every command is available through the installed bundle's `scripts/barknotify.py`. From a checkout use `python3 barknotify_plugin/scripts/barknotify.py`; examples below use the optional global `barknotify-plugin` command for brevity.

## Optional CLI

Clone the private repository with an authorized GitHub account:

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

Use `setup` to enter a URL or key locally with hidden input. Use the Bark device key, not an APNs token. A full URL selects its server; `--server` accepts an origin without a key or `/push` path.

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
