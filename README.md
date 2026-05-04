# Coser

Claude cOde SwitchER — Claude Code 账户自动切换工具。

根据当前 WiFi 网络、路由器 IP、账户余额等条件自动选择合适的 profile 启动 Claude Code。

## 功能

- **自动切换** — 根据 WiFi SSID / 路由器 IP 自动选择 profile，余额不足时自动 fallback
- **余额监控** — 内置支持智谱 (GLM)、DeepSeek 余额查询，三级状态（充足/不足/用完）
- **交互式选择** — `--select` 提供 fzf 风格的键盘导航，实时显示各 profile 余额
- **代理支持** — profile 中配置代理，自动展开为标准环境变量
- **每日激活** — 定时发送 `hi` 激活限额周期，失败时推送 macOS 系统通知

## 安装

```bash
git clone <repo-url> && cd coser
pip install -e .
```

安装后可选：`alias claude=coser`

## 快速开始

### 1. 初始化配置目录

```bash
mkdir -p ~/.config/coser/profiles
```

### 2. 创建 Profile

在 `~/.config/coser/profiles/` 下创建 TOML 文件，例如 `glm.toml`：

```toml
[env]
ANTHROPIC_BASE_URL = "https://open.bigmodel.cn/api/anthropic"
ANTHROPIC_AUTH_TOKEN = "your-token-here"
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
ANTHROPIC_DEFAULT_HAIKU_MODEL = "glm-4.5-air"
ANTHROPIC_DEFAULT_SONNET_MODEL = "glm-5-turbo"
ANTHROPIC_DEFAULT_OPUS_MODEL = "glm-5"

[proxy]
PROXY = "http://localhost:7890"
NO_PROXY = "localhost,127.0.0.1"

[balance]
provider = "zhipu"
api_key_ref = "ANTHROPIC_AUTH_TOKEN"
exhausted_below = 0.01
low_below = 0.10

[say_hi]
enabled = true
```

### 3. 创建自动切换规则

编辑 `~/.config/coser/config.toml`：

```toml
default_profile = "glm"
enable_agent_teams = true

[wifi_mapping]
"CompanyWiFi" = "bailian"
"Home-5G" = "glm"

[router_mapping]
"192.168.31.1" = "glm"

[fallback_chain]
profiles = ["glm", "deepseek", "bailian"]

[say_hi]
workdir = "~/.config/coser/say-hi-workspace"
```

### 4. 使用

```bash
coser                    # 自动选择 profile 并启动 claude code
```

## 用法

```
coser                         # 自动模式：按决策流程选择 profile
coser --profile <name>        # 手动指定 profile（跳过余额检查）
coser --select                # 交互式选择（键盘上下键 + 余额实时显示）
coser --list                  # 列出所有 profile 及余额状态
coser --dry-run               # 显示决策结果，不启动 claude
coser --say-hi                # 对启用的 profile 执行每日激活
coser --install-cron          # 安装每日 8:00 的 cron 任务
coser --uninstall-cron        # 移除 cron 任务
coser [其他参数]               # 透传给 claude code
```

## 文档

- [需求文档](docs/requirement.md)
- [用户手册](docs/user-guide.md)
