# BarkNotify-Plugin

Get a phone notification when Codex ends a turn or requests approval. Keep working elsewhere and return when your session needs attention.

[简体中文](README.zh-CN.md) · [Guided setup](install.md) · [CLI reference](docs/usage.md) · [Compatibility](docs/compatibility.md)

```text
my-project · Turn ended
my-project · Approval requested
```

BarkNotify-Plugin is an Apache-2.0-licensed plugin for [Bark](https://github.com/Finb/Bark), with a bundled runtime and setup skill. No account, daemon, or provider-specific launcher is required. English notifications are the default; Chinese is available.

## Quick start

You need an iPhone with Bark installed and notifications allowed, Python 3.11+, curl, and Codex with native plugin management on macOS or Linux. The computer running Codex must be able to reach your Bark server.

Install directly from the private GitHub repository using an account with access. Set up GitHub authentication on this computer first; Codex uses Git to fetch the marketplace.

```bash
codex plugin marketplace add https://github.com/Jinghaoleven/BarkNotify-Plugin.git
codex plugin add barknotify@barknotify-plugin
```

Start a new Codex session and use the setup prompt below. The bundled skill connects the plugin and guides private Bark configuration. To configure manually from a checkout, use `codex plugin marketplace add .`, install the plugin, then run `python3 barknotify_plugin/scripts/barknotify.py setup --integrate` and `python3 barknotify_plugin/scripts/barknotify.py doctor`. A PyPI package and hosted installer have not been published.

Setup asks for the **Bark push URL or device key in your terminal**, with input hidden. A URL such as `https://api.day.app/DEVICE_KEY/` selects its server automatically; self-hosted Bark works the same way. Do not paste the URL or key into a Codex conversation.

The test result means the Bark server accepted the push. **Check that the notification appears on your phone.** Then start a new Codex session, open `/hooks`, and review and trust the Bark handlers. Run a short turn and check that its automatic notification arrives. Setup cannot grant hook trust or confirm phone delivery for you.

Native plugin loading and integration were verified on Linux with Codex CLI 0.166.0. Other versions and macOS native integration still need validation; see [compatibility](docs/compatibility.md).

## Let Codex guide setup

After installing the plugin, start a new session and open its setup entry in `/plugins`, when available. You can also use this prompt:

> Use the Bark plugin's barknotify skill to finish setup. Reuse my existing marketplace and settings, connect the session hooks, and guide me through entering my Bark URL privately in a local terminal. Check delivery and hook trust. Use English notifications.

The [guided setup](install.md) also works from a checkout. The installed plugin carries everything needed to run its commands; an additional CLI installation is optional.

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
