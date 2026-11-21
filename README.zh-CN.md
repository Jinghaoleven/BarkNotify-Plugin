# BarkNotify-Plugin

当 Codex 结束一轮处理或请求审批时，在手机上收到通知。离开终端后，也能知道何时需要回来查看。

[English](README.md) · [引导安装](install.md) · [命令参考](docs/usage.md) · [兼容说明](docs/compatibility.md)

```text
my-project · 本轮结束
my-project · 审批请求
```

这是一个 Apache-2.0 开源的 [Bark](https://github.com/Finb/Bark) 插件，自带运行脚本和配置 skill，无需账户、后台服务或特定 provider 启动器。通知默认使用英文，可切换为中文。

## 快速开始

运行 Codex 的电脑需要 Git、Python 3.11+、curl，以及支持原生插件管理的 Codex，支持 macOS 和 Linux。**Bark App 需要你另行在 iPhone 上安装并设置。**

### 1. 准备手机

1. 从 [App Store 安装 Bark](https://apps.apple.com/app/bark-custom-notifications/id1403753865)，并首次打开 App。
2. 按提示允许通知，或点 Bark 的“**去开启**”。如果此前拒绝过，进入 **iPhone 设置 → 通知 → Bark → 允许通知**，再回到 Bark。默认通知不要求开启“重要警告”。
3. 使用默认服务器 `api.day.app`。等首页出现该设备的 key 后，打开“**复制**”旁的菜单，选择“**复制地址和Key**”；旧版本可复制页面显示的测试推送 URL。

使用自建 Bark 服务器时，先**在 Bark App 中添加并选择该服务器**，再复制它为这台手机生成的地址和 key。

### 2. 安装 Codex 插件

```bash
codex plugin marketplace add https://github.com/Jinghaoleven/BarkNotify-Plugin.git
codex plugin add barknotify@barknotify-plugin
```

### 3. 连接手机

启动新的 Codex 会话，打开 `/plugins` 中的插件 setup 入口（若当前版本提供），或发送：

> 请用 barknotify 配置 Bark 通知，接入会话 hooks，引导我在本机终端输入 Bark URL，通知使用中文。

setup 会要求你在**本机终端隐藏输入**刚复制的地址。`https://api.day.app/DEVICE_KEY` 和带示例标题、正文的旧版测试 URL 都能识别，只保存服务器和 key。不要把地址发到聊天中，也不要向 setup 粘贴整段 curl 命令。全局 CLI 是可选项，[手动配置方法](docs/usage.md#manual-setup-from-a-checkout)见命令参考。

### 4. 验证通知

确认手机实际收到 **BarkNotify-Plugin · Test**。随后重启 Codex，在 `/hooks` 中审阅并信任 Bark handlers，再完成一个简短回合，确认自动通知送达。服务器接受推送不等于手机已经显示通知。

手机端只需完成这次设置，之后通过 iOS 接收通知，Bark 无需一直开着。已在 Linux、Codex CLI 0.166.0 上验证原生集成，其他版本和平台见 [兼容说明](docs/compatibility.md)。

## 日常使用

从 checkout 运行：

```bash
python3 barknotify_plugin/scripts/barknotify.py status
python3 barknotify_plugin/scripts/barknotify.py test
python3 barknotify_plugin/scripts/barknotify.py setup --language en --no-test
python3 barknotify_plugin/scripts/barknotify.py disable
python3 barknotify_plugin/scripts/barknotify.py enable
```

也可以让 Codex 检查状态、切换语言、暂停通知或发测试推送。skill 使用已安装的脚本，不要求终端停留在 checkout。全局 `barknotify-plugin` 命令见 [可选 CLI 安装](docs/usage.md#optional-cli)。

默认通知为“本轮结束”和“审批请求”。本轮结束包含向用户提问后停止，不代表整个任务成功；自动 reviewer 可能自行处理审批。会话启动、处理开始、中断和会话结束通知可选，见 [事件语义](docs/compatibility.md#lifecycle-semantics) 和 [配置选项](docs/usage.md)。

在 `/plugins` 中禁用或移除 Bark 会停止自动通知。共享 `CODEX_HOME` 的启动器只需安装一次；独立配置目录可分别接入。

## 更新与卸载

推荐的 Git marketplace 安装方式更新如下：

```bash
codex plugin marketplace upgrade barknotify-plugin
codex plugin add barknotify@barknotify-plugin
```

然后让已安装的配置 skill 运行 `integrate`。本地 checkout 更新文件后跳过 marketplace upgrade，在 plugin add 后运行 `python3 barknotify_plugin/scripts/barknotify.py integrate`。接入保留 marketplace 来源、key、偏好及其他 hooks。更新后在新会话中重新检查 `/hooks`。

可选全局 CLI 需单独更新，两种方式见 [使用说明](docs/usage.md#updates)。更新 Codex 本身后，也应重新运行 `integrate` 检测 hook 支持。

完整卸载插件及兼容 handlers：

```bash
python3 barknotify_plugin/scripts/barknotify.py uninstall
```

如果依赖缓存内脚本清理，请先执行该命令，再移除原生插件。若已通过 `/plugins` 移除，仍可从 checkout 或全局 CLI 运行 `uninstall`。卸载保留私有设置及 marketplace，便于重装；重复清理是安全的。

## 排查问题

| 现象 | 下一步 |
| --- | --- |
| 找不到 key | 在本机终端运行 `setup`，输入 Bark 显示的 URL |
| App 没有设备地址，或复制菜单不可用 | 开启通知后回到 Bark，保持联网，等待注册完成 |
| 测试成功，手机没有通知 | 检查 Bark 通知权限、iPhone 专注模式及 key 对应的设备 |
| 手动测试正常，自动通知不工作 | 运行 `doctor`，在 `/plugins` 启用，在 `/hooks` 审阅，再启动新会话 |
| 更新后缺少 hooks | 用已安装脚本或 CLI 重新运行 `integrate` |
| 没有插件 setup 入口 | 使用上面的提示词或 checkout 命令 |
| 缺少 `python3` 或 `curl` | 在运行 Codex 的主机上安装依赖 |

`doctor` 不发推送、不启动模型回合，也无法验证手机是否显示通知。项目级插件策略的限制见 [兼容说明](docs/compatibility.md)。

## 隐私

推送 URL 属于凭据。设置与 key 分开保存为 `0600` 私有文件，默认目录 `${XDG_CONFIG_HOME:-~/.config}/barknotify-plugin`，位于插件缓存之外。环境变量 key 和自定义目录见 [凭据选项](docs/usage.md#credentials)。

自动通知包含会话名、tmux 名或项目目录名，以及 model/tool 元信息；不会发送 prompt、回复、命令、审批描述、完整路径或会话 ID。请使用适合手机锁屏展示的会话名。插件没有统计上报，仅向配置的 Bark 服务器发送推送。本地记录只保存时间、事件、结果和脱敏诊断。

推送尽力送达，网络失败不会影响审批和会话行为。强制杀进程或主机断网时，无法保证最后一条通知。

## 开发与分发

```bash
python3 -m unittest discover -s tests -v
python3 tests/native_install.py
```

测试使用临时配置和本地模拟 Bark 服务；原生测试不启动模型、不发送真实推送。CI 配置 Ubuntu/macOS、Python 3.11/3.13 的包检查，原生 Codex 集成需独立验证。

正式分发采用 GitHub marketplace 和 release 产物。[当前官方规范](https://developers.openai.com/plugins/build/plugins) 明确：**包含 lifecycle hooks 的插件不符合公共 OpenAI 插件目录的收录条件**。详见 [发布指南](docs/releasing.md) 和 [开源项目对照](docs/product-review.md)。
