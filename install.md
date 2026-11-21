# Guided BarkNotify-Plugin setup

Give this file to Codex:

> Follow this guide to set up BarkNotify-Plugin. Reuse my existing installation and settings, do the computer steps, and guide me through entering the push URL privately and verifying the phone notification.

> 请按这份指南配置 BarkNotify-Plugin，复用已有安装和设置，完成电脑端步骤，引导我私密输入推送 URL，并验证手机通知。

## Instructions for the agent

Work in the user's language. Configure only the requested home; launchers sharing `CODEX_HOME` share one installation. Preserve credentials, preferences, unrelated hooks, and the marketplace source. English notifications are the default; use `--language zh` when chosen.

1. Check Git, Python 3.11+, curl, and native Codex plugin management. Inspect `codex plugin list --json` for `barknotify@barknotify-plugin`. Do not print environment keys or raw private settings. Use the local checkout or installed skill's bundled script; a global CLI is optional.
2. If the plugin is missing, reuse an existing barknotify-plugin marketplace. Otherwise register `https://github.com/Jinghaoleven/BarkNotify-Plugin.git`, then run `codex plugin add barknotify@barknotify-plugin`. A local checkout can instead be registered with `codex plugin marketplace add <checkout>`. Do not invent a PyPI package or hosted installer. If disabled, explain its state and enable it only within the requested setup.
3. Run bundled `integrate`, then `status` or `doctor`. Integration refreshes from the existing source and detects hook support, adding compatibility handlers only when needed. For an existing tool-managed installation, retain that method and use its `install` for upgrades.
4. Guide the user to install [Bark from the App Store](https://apps.apple.com/app/bark-custom-notifications/id1403753865), open it, and allow notifications (tap **Enable / 去开启**, or iPhone Settings → Notifications → Bark → Allow Notifications). Keep the default `api.day.app` server. Once a device key is available, use the menu beside **Copy → Copy Address and Key / 复制地址和Key**. Older App versions may show a test URL. For self-hosted Bark, add/select that server in the App first and use its device URL. Have the user run bundled `setup` in their local terminal, where input is hidden; URLs with example message fields/parameters work, but curl commands do not. Never ask for the key or URL in chat, put it in arguments, or feed it through an agent tool transcript. If no local terminal is available, explain that local credential entry remains pending. Reuse valid existing credentials; do not rotate them to fix an unrelated error.
5. Setup sends one test unless `--no-test` was explicitly chosen. Server acceptance does not prove phone display. Ask the user to confirm it appeared; otherwise check notification permission, Focus settings, the target device, and network delivery. Do not repeatedly send tests without a reason. With `--no-test`, report delivery verification as pending. Normal notifications require Allow Notifications; critical-alert permission is optional. Bark can be closed after initial setup. For a new phone, use that phone’s URL; after reinstalling Bark, check whether its address changed.
6. Run `doctor`. Have the user start a new session and review `/hooks`; never grant trust or bypass permission policies. Give a resume prompt: “Use barknotify to finish setup: check status and hook trust, then verify one automatic turn notification.” / “请用 barknotify 继续配置：检查状态及 hook 信任，再验证一次自动回合通知。” A natural turn ending can provide the test; do not induce a risky approval to test its hook.
7. Report configuration, phone delivery, trust, and automatic delivery separately. Claim setup complete only when requested checks are satisfied; name any remaining restart or phone action.

The installed skill contains command and lifecycle guidance. `send` and `test` are real pushes: perform them only for requested setup, verification, or notification. Automatic notifications omit conversation content and return neutral hook JSON.
