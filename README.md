# BarkNotify-Plugin

Get a phone notification when Codex ends a turn or requests approval. Keep working elsewhere and return when your session needs attention.

[简体中文](README.zh-CN.md) · [Guided setup](install.md) · [CLI reference](docs/usage.md) · [Compatibility](docs/compatibility.md)

```text
my-project · Turn ended
my-project · Approval requested
```

BarkNotify-Plugin is an Apache-2.0-licensed plugin for [Bark](https://github.com/Finb/Bark), with a bundled runtime and setup skill. No account, daemon, or provider-specific launcher is required. English notifications are the default; Chinese is available.

## Quick start

On the computer running Codex, have Git, Python 3.11+, curl, and Codex with native plugin management. macOS and Linux are supported. **Install and set up the Bark App separately on your iPhone.**

### 1. Prepare your iPhone

1. Install [Bark from the App Store](https://apps.apple.com/app/bark-custom-notifications/id1403753865) and open it.
2. Enable notifications when prompted, or tap **Enable** in Bark. If previously denied, open **iPhone Settings → Notifications → Bark → Allow Notifications**, then return to Bark. Critical alerts are optional for our default notifications.
3. Keep the default server, `api.day.app`. Open the menu beside **Copy** and choose **Copy Address and Key**. In older versions, copy the displayed test URL instead. Wait for your device's key to appear before copying.

For a self-hosted Bark server, add and select it **in the Bark App first**, then copy that server's address and key for your phone.

### 2. Install the Codex plugin

```bash
codex plugin marketplace add https://github.com/Jinghaoleven/BarkNotify-Plugin.git
codex plugin add barknotify@barknotify-plugin
```

### 3. Connect your phone

Start a new Codex session, open the plugin's setup entry in `/plugins` if available, or use this prompt:

> Use barknotify to set up Bark notifications. Connect the session hooks and guide me through entering my Bark URL in a local terminal. Use English notifications.

Setup asks for the copied URL **in your local terminal, with input hidden**. Both `https://api.day.app/DEVICE_KEY` and older example URLs with a title/body are accepted; only the server and key are saved. Do not paste the URL into chat or paste a curl command into setup. A global CLI is optional; see [manual setup](docs/usage.md#manual-setup-from-a-checkout).

### 4. Verify delivery

Confirm the **BarkNotify-Plugin · Test** notification appears on your phone. Then restart Codex, review and trust the Bark handlers in `/hooks`, and finish a short turn to check its automatic notification. Server acceptance alone does not confirm phone delivery.

After this one-time phone setup, notifications arrive through iOS; Bark does not need to stay open. Native Codex integration was verified on Linux with CLI 0.166.0; see [compatibility](docs/compatibility.md) for other versions and platforms.

## Everyday use

From a checkout:

```bash
python3 barknotify_plugin/scripts/barknotify.py status
python3 barknotify_plugin/scripts/barknotify.py test
python3 barknotify_plugin/scripts/barknotify.py setup --language zh --no-test
python3 barknotify_plugin/scripts/barknotify.py disable
python3 barknotify_plugin/scripts/barknotify.py enable
```

Or ask Codex to check Bark status, change the language, pause notifications, or send a test. The skill uses the installed bundle, so you do not need to stay in the checkout. For a global `barknotify-plugin` command, see [optional CLI installation](docs/usage.md#optional-cli).

Default events are **Turn ended** and **Approval requested**. Ending a turn includes stopping to ask a question; it does not prove the entire task succeeded. An automatic reviewer may resolve an approval without user input. Starting, interrupting, and ending a session are optional events. See [event meanings](docs/compatibility.md#lifecycle-semantics) and [configuration options](docs/usage.md).

Disabling or removing Bark in `/plugins` stops automatic pushes. Launchers sharing `CODEX_HOME` share one installation; independent homes can be configured separately.

## Update and uninstall

For the recommended Git marketplace installation:

```bash
codex plugin marketplace upgrade barknotify-plugin
codex plugin add barknotify@barknotify-plugin
```

Then ask the installed setup skill to run `integrate`. For a local checkout, update its files, skip marketplace upgrade, and run `python3 barknotify_plugin/scripts/barknotify.py integrate` after plugin add. Integration preserves the marketplace source, credentials, preferences, and unrelated hooks. Review `/hooks` in a new session after updates.

An optional global CLI is updated separately; [usage](docs/usage.md#updates) covers both installation methods. After updating Codex itself, run `integrate` again to detect hook support.

To remove the plugin and compatibility handlers:

```bash
python3 barknotify_plugin/scripts/barknotify.py uninstall
```

Run this before native `/plugins` removal if you rely on the cached bundle for cleanup. If already removed, the checkout or optional CLI can still run `uninstall`. Private settings and the marketplace remain available for reinstallation; repeated cleanup is safe.

## Troubleshooting

| Symptom | Next step |
| --- | --- |
| Key is missing | Run `setup` in a local terminal and enter the URL shown in Bark |
| The App has no device URL or its Copy menu is disabled | Allow notifications, return to Bark, and wait for registration on an active network |
| Test succeeds but the phone is silent | Check Bark notification permission, iPhone Focus settings, and the key's target device |
| Manual test works but automatic notifications do not | Run `doctor`, enable Bark in `/plugins`, review `/hooks`, and start a new session |
| Hooks are missing after an update | Run `integrate` again using the installed bundle or optional CLI |
| Plugin setup entry is unavailable | Use the setup prompt above or the checkout commands |
| `python3` or `curl` is unavailable | Install the dependency on the host running Codex |

`doctor` checks configuration, integration, and hook trust without sending a push or starting a model turn. It cannot determine whether your phone displayed a notification. Project-specific plugin policy limits are documented in [compatibility](docs/compatibility.md).

## Privacy

The push URL is a credential. Settings and the key are separate private files (`0600`) under `${XDG_CONFIG_HOME:-~/.config}/barknotify-plugin`, outside the plugin cache. Environment keys and custom directories are supported; see [credential options](docs/usage.md#credentials).

Automatic notifications include a session name, tmux name, or project basename, plus model/tool metadata. They omit prompts, responses, commands, approval descriptions, full paths, and session IDs. Choose a session name suitable for your phone's lock screen. The package has no analytics and sends payloads only to your configured Bark server. A local delivery record contains a timestamp, event, outcome, and sanitized diagnostic.

Delivery is best effort. Network failures do not affect approvals or session behavior. Force-killed processes and disconnected hosts cannot guarantee a final push.

## Development and distribution

```bash
python3 -m unittest discover -s tests -v
python3 tests/native_install.py
```

Tests use disposable configurations and a local mock Bark server. Native tests never start a model turn or send a real push. CI runs package checks on Ubuntu/macOS with Python 3.11/3.13; native Codex integration is a separate check.

GitHub marketplaces and release artifacts are the distribution path. Under the [current official packaging rules](https://developers.openai.com/plugins/build/plugins), plugins containing lifecycle hooks are **not eligible for the public OpenAI plugin directory**. See the [release guide](docs/releasing.md) and [open-source comparison](docs/product-review.md).
