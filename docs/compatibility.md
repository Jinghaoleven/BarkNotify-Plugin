# Codex compatibility

The package includes a standard `plugin.json`, an onboarding skill, and bundled command hooks. The repository marketplace exposes `barknotify@barknotify-plugin`. No provider name, developer home directory, or user credential is part of the package.

The product is BarkNotify-Plugin; the package/command is `barknotify-plugin` and Python module is `barknotify_plugin`. Legacy `bark@codex-bark` and `bark@codex-bark-local` registrations are removed during installation/integration after the new plugin is installed, preventing duplicate senders. Private settings, legacy environment aliases, and the `bark-install.json` registry filename remain compatible. Old marketplace registrations are retained; remove them separately when unused.

The recommended path uses native marketplace registration and `codex plugin add`, followed by bundled `integrate` (or `setup --integrate`). Integration refreshes the bundle from the existing source without changing marketplace registration. It copies a stable per-home compatibility runtime outside versioned caches. The optional tool-managed `barknotify-plugin install` instead creates a private local marketplace; it refuses to overwrite an existing native marketplace installation.

Both paths inspect `hooks/list` through a temporary local app-server without starting a model turn. If all six bundled events are exposed, they select `native` mode. Otherwise they select `compat` mode and merge only their own command handlers into the target home's `hooks.json`. `--mode native` requires successful discovery; `--mode compat` explicitly selects the bridge.

Codex CLI 0.166.0 was tested on Linux. In the tested environment, the native plugin and skill loaded, while bundled hook metadata was absent; the compatibility registrations were visible and required normal hook trust. This is an observation about that runtime, not a claim that every 0.166.0 environment behaves identically. Other releases and macOS still need native integration validation; the transport and configuration code uses Python's standard library and curl.

The selected mode, installed cache path, settings directory, and owned compatibility command are recorded in the target home's `bark-install.json`. The bridge checks the native user plugin's enabled state in `config.toml` and the presence of its installed cache before sending. Disabling or uninstalling Bark through `/plugins` therefore stops compatibility pushes. Use `barknotify-plugin uninstall` to remove the bridge registrations too.

Compatibility mode follows the **user-level** plugin switch. Project config and per-invocation profile overrides do not reliably appear in hook input, so the bridge cannot reproduce every project-specific plugin policy. Use `barknotify-plugin disable` to stop delivery consistently, or use separate Codex homes/configurations when different projects require independent preferences. In native mode Codex controls hook selection directly.

If a Codex update begins loading bundled hooks while compatibility registrations exist, the native handler remains passive until integration re-detects the mode. This prevents two senders for one event. Run `integrate` for marketplace installations or `install` for tool-managed installations after upgrading Codex.

Codex requires review and trust before non-managed hooks run. Installation never grants trust or uses a trust bypass. After installation or script upgrades, review Bark in `/hooks` in a new session. Existing sessions may retain their previous hook configuration until restarted or resumed.

## Lifecycle semantics

| Event | Hook | Default | Meaning |
| --- | --- | --- | --- |
| `turn.completed` | Stop | Yes | The model stopped this turn, possibly to ask a question |
| `approval.required` | PermissionRequest | Yes | Approval handling began, before an automatic reviewer may resolve it |
| `session.started` | SessionStart | No | Startup, resume, fork, or clear; excludes compaction |
| `turn.started` | UserPromptSubmit | No | A user prompt was submitted |
| `turn.interrupted` | Interrupt | No | The user interrupted an active main-thread turn |
| `session.ended` | SessionEnd | No | The main session ended according to runtime lifecycle rules |

Stop does not prove task success. Other Stop hooks can continue the turn. SessionEnd can occur after the CLI client disconnects because a shared server keeps the conversation alive; official rules include ending a session after 30 minutes idle without connected clients. There is no reliable final notification for a force-killed process or an offline host.

Ordinary hooks run in the background. Interrupt and SessionEnd have a short synchronous budget, with delivery capped at 1.5 seconds. Codex can cancel unfinished background hooks when a session ends. Every Bark handler returns neutral JSON and never approves, denies, or continues a turn.

Official references: [Plugin packaging](https://developers.openai.com/plugins/build/plugins), [Codex hooks](https://developers.openai.com/codex/hooks), [Plugin management](https://developers.openai.com/codex/plugins/).
