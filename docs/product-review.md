# Open-source installation review

Reviewed GitHub README/install documentation against BarkNotify-Plugin's installation and product flow. These are design references, not dependencies or executed installers.

| Reference | Useful pattern | Applied to BarkNotify-Plugin |
| --- | --- | --- |
| [openai/plugins](https://github.com/openai/plugins) | Repository marketplace and native plugin discovery | Keep the standard marketplace and self-contained bundle |
| [gptaku-plugins-codex](https://github.com/fivetaku/gptaku-plugins-codex) | Native marketplace install first; clear restart and upgrade steps | Native quick start; separate source refresh from plugin integration |
| [ntfyx-agent-plugins](https://github.com/KaylaONeal/ntfyx-agent-plugins) and its [guided installation](https://github.com/KaylaONeal/ntfyx-agent-plugins/blob/main/install.md) | Agent-guided setup, reuse existing integration, distinguish server acknowledgement from phone display | `install.md`, bundled setup guidance, private credential entry, explicit verification checkpoints |
| [agent-ding](https://github.com/YunHerry/agent-ding) | Concise notification benefit, language link, prerequisites and troubleshooting | Short product introduction, equivalent English/Chinese flow, troubleshooting table |
| [rgotify](https://github.com/dinglebear-ai/rgotify) | Short primary path, optional installation choices, health diagnostics | Optional global CLI and dedicated command reference |

Ntfyx's plugin is open source but its companion CLI, phone app, and relay are separate products; its architecture is not a requirement for Bark. Rgotify's native plugin example targets Claude Code, while its Codex example uses MCP. It is a product-documentation reference, not evidence of native Codex plugin support.

Some agent-ding documentation describes enabling the experimental `plugin_hooks` feature. That flag is removed in the tested Codex CLI 0.166.0; we detect actual hook exposure instead of copying the toggle. Codex's standalone distribution also means Node/npm are not universal prerequisites.

The [official plugin packaging documentation](https://developers.openai.com/plugins/build/plugins) says lifecycle hooks are supported for manually installed desktop plugins and plugins containing them are not eligible for the public directory. BarkNotify-Plugin targets repository marketplaces and releases; Linux CLI integration uses a detected compatibility bridge where necessary. Its documented Git URL is the distribution repository; user instructions describe the final open-source installation flow.

Bark onboarding was checked against the [official README](https://github.com/Finb/Bark#usage), [homepage actions](https://github.com/Finb/Bark/blob/master/Controller/HomeViewController.swift), and [server registration](https://github.com/Finb/Bark/blob/master/Common/ServerManager.swift). The current App provides **Copy Address and Key** in the Copy menu; its main Copy button can copy a curl example. Notification permission and device registration must precede copying a usable address. A self-hosted server must first be added in the App. Setup accepts older URL examples while discarding their message fields and query parameters. This is a documentation/source check, not a claim of a physical iPhone delivery test.
