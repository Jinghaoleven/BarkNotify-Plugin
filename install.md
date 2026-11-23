# Agent-assisted setup

Install the repository marketplace as shown in [README](README.md), then ask Codex:

> Set up BarkNotify-Plugin and guide me through entering my Bark URL privately in a terminal.

中文：

> 请配置 BarkNotify-Plugin，使用中文通知，并引导我在终端私密输入 Bark 地址。

The bundled [barknotify skill](barknotify_plugin/skills/barknotify/SKILL.md) handles integration, private credential entry, and verification. A global Python CLI is optional. For direct terminal use, see [manual setup](docs/usage.md#manual-setup).

Keep the address/key out of chat. Setup must run on the Codex host with the same user and `CODEX_HOME`. Confirm phone display and review `/hooks`; restart or resume only when the hooks are missing or stale.
