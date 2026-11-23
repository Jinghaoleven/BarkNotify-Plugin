# BarkNotify-Plugin

Receive remote Codex CLI session alerts on your iPhone through [Bark](https://github.com/Finb/Bark). By default, it notifies you when a turn ends or approval is requested. English and Chinese notifications are supported.

[简体中文](README.zh-CN.md) · [Commands](docs/usage.md) · [Network extension](extensions/reverse-socks/README.md)

<p align="center">
  <img src="docs/assets/notification-preview.png" alt="Bark notifications on iPhone and a paired Apple Watch" width="720">
</p>

## Get started

Requires macOS or Linux, Codex plugin management, Git, curl, and **Python 3.11+** on the Codex host.

1. Install [Bark on your iPhone](https://apps.apple.com/app/bark-custom-notifications/id1403753865), open it, and allow notifications. Keep the default server. Use **Copy → Copy Address and Key** when the device address appears.
2. Install on the host where Codex runs:

   ```bash
   codex plugin marketplace add https://github.com/Jinghaoleven/BarkNotify-Plugin.git
   codex plugin add barknotify@barknotify-plugin
   ```

3. Open a Codex session and ask:

   > Set up BarkNotify-Plugin and guide me through entering my Bark URL privately in a terminal.

   Run the setup command Codex provides in a separate terminal **on the same host**. Paste the address at the hidden prompt. **Keep the address and key out of chat.** Add “Use Chinese notifications” if preferred. [Manual setup](docs/usage.md#manual-setup) is also available.
4. Confirm **BarkNotify-Plugin · Test** appears on your phone. Review and trust Bark in `/hooks`. If the hooks are missing after installation, restart or resume Codex and review them again. Finish a short turn to verify automatic delivery.

Bark can be closed after setup. On a paired Apple Watch, enable Bark notification mirroring in the Watch app. Launchers sharing `CODEX_HOME` use one installation.

## Everyday use

Ask Codex to check status, change the language, pause or resume notifications, or send a test. Preference changes preserve your paused/enabled state. You can also disable Bark in `/plugins`.

A turn-end alert can mean Codex is waiting for your reply; it does not guarantee the whole task succeeded. Delivery is best effort. Android is outside the current support scope.

## Update or remove

```bash
codex plugin marketplace upgrade barknotify-plugin
codex plugin add barknotify@barknotify-plugin
```

Then ask Codex to finish updating BarkNotify-Plugin and review `/hooks`. Restart or resume if the session still has the old hooks. Saved credentials and preferences are kept.

To remove it, ask Codex to uninstall BarkNotify-Plugin, or follow [removal commands](docs/usage.md#removal). Saved settings are retained.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Bark has no device address | Allow notifications, return to Bark, and wait while online |
| Test accepted, but absent on phone | Check iOS notification permissions, Focus, and the receiving device address |
| Manual test works; automatic alerts do not | Check `/plugins`, paused state, and `/hooks`; reload the session if hooks are missing or stale |
| Host cannot reach Bark | Run the [network check](docs/usage.md#network). Keep your key; use a working proxy or the optional [standalone SSH tunnel](extensions/reverse-socks/README.md) |
| New phone or self-hosted server | Select the server in Bark and run setup with that device's address |

## Privacy

Automatic pushes include session/project names, status, and optional model/tool names. Prompts, responses, commands, full paths, and session IDs are omitted. Choose names suitable for your lock screen. Credentials stay privately on the Codex host, outside the plugin cache. Pushes go to your selected Bark server; there is no analytics.

[Apache-2.0](LICENSE) · [Developer guide](docs/development.md) · [Security](SECURITY.md)
