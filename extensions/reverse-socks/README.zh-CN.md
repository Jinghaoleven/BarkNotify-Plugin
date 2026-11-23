# 反向 SOCKS 扩展

让受限的 Codex 主机通过另一台 Mac 或 Linux 机器的网络连接 Bark。可选扩展包 **barknotify-tunnel** 使用标准 OpenSSH，独立管理自己的连接，不依赖额外的 shell 转发工具。

[English](README.md)

## 安装与启动

出口机器需要 Python 3.9+ 和 OpenSSH 7.6+。先为 Codex 主机配置 SSH 别名，确认密钥登录无需交互。Codex 主机需要 curl、`ss` 或 `lsof`，并允许 SSH 远程转发。

在出口机器的仓库目录运行：

```bash
python3 -m venv ~/.local/share/barknotify-tunnel/venv
~/.local/share/barknotify-tunnel/venv/bin/pip install ./extensions/reverse-socks
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel configure --host codex-host
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel up
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel check
```

`codex-host` 替换为你的 SSH 别名。默认远端端口为 10808；占用时可在 configure 后加 `--port 10810`。不会改动已有转发。

Codex 主机完成 BarkNotify-Plugin 0.5.0+ 的 integrate 后运行：

```bash
barknotify_script="${CODEX_HOME:-$HOME/.codex}/bark/runtime/scripts/barknotify.py"
python3 "$barknotify_script" proxy --url socks5h://127.0.0.1:10808
python3 "$barknotify_script" network
```

代理 URL 使用你配置的端口。扩展不需要设备 key。

## 自动恢复

在出口机器运行：

```bash
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel service install
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel status
```

这会启用 macOS LaunchAgent 或 Linux 用户 systemd timer。每 30 秒检查连接，失败后退避重试，最长间隔两分钟。服务保存独立运行副本，移动仓库不会影响它。服务运行在用户会话中；Linux 注销后继续运行，需要管理员配置 user lingering。

出口机器应保持唤醒和联网。恢复要等待 SSH 检测断链，无法消除短暂中断、休眠、VPN 故障或服务器限制。中断期间的通知不会排队补发。

## 停止与卸载

```bash
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel down
~/.local/share/barknotify-tunnel/venv/bin/barknotify-tunnel service uninstall
```

`down` 只停止自己的连接，并禁止自动恢复，直到执行 `up`。卸载会删除恢复服务并停止隧道，保留设置。`service install --dry-run` 可预览服务文件。Codex 主机执行 `proxy --clear` 后，Bark 恢复使用原有网络环境。

## 排查与访问范围

`check` 检查远端监听和 Bark `/ping`，不会推送消息。端口占用时会失败，不会抢占；转发被拒绝时检查 sshd 策略。扩展拒绝非回环监听，服务器应保持 `GatewayPorts no`。

SOCKS 端口只在回环地址监听，但不带认证。同一网络命名空间的其他进程也可以使用它，流量会经过出口机器，请只用于可信主机。

多个独立隧道可在子命令前加 `--name <profile>`。设置位于 `~/.config/barknotify-tunnel/<profile>`，也支持 `XDG_CONFIG_HOME`。
