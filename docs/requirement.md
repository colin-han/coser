# Coser - Claude Code 账户切换服务

## 概述

Coser 是一个 Claude Code 账户自动切换工具，能够根据当前环境（WiFi 网络、路由器 IP、账户余额等）自动选择合适的 profile 启动 Claude Code。

## 技术选型

- **语言**: Python
- **形式**: 独立 CLI 命令（`coser`）
- **部署**: 通过 `pip install -e .` 安装

## 配置结构

### 目录布局

```
~/.coser/
├── profiles/           # 各 provider 的 profile 配置
│   ├── glm.toml
│   ├── deepseek.toml
│   ├── bailian.toml
│   └── kimi.toml
└── config.toml         # 自动切换规则、默认 profile 等
```

### Profile 配置格式

每个 profile 使用 TOML 格式，包含 `[env]`、`[proxy]`、`[balance]`、`[say_hi]` 四个段落。

#### `[env]` — 环境变量（白名单）

仅允许以下变量：

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_BASE_URL` | API 代理地址 |
| `ANTHROPIC_AUTH_TOKEN` | API 认证 Token |
| `API_TIMEOUT_MS` | 请求超时时间（毫秒） |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 禁用非必要网络请求 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | 覆盖 Haiku 模型名称 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | 覆盖 Sonnet 模型名称 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | 覆盖 Opus 模型名称 |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | 自动压缩的上下文窗口大小（毫秒） |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | 自动压缩触发的百分比阈值 |

> **注意**：`CLAUDE_PROFILE` 环境变量由程序自动设置，标识当前使用的 profile 名称。启用 agent teams 时值为 `"{name} (with agent teams)"`，否则为 `"{name}"`。 |

不在白名单中的变量会被忽略并打印警告，不会导致加载报错。

#### `[proxy]` — 代理配置（可选）

只需配置 `PROXY` 和 `NO_PROXY`，程序自动展开为 `HTTP_PROXY`、`HTTPS_PROXY`、`http_proxy`、`https_proxy`、`NO_PROXY`、`no_proxy`。

```toml
[proxy]
PROXY = "http://localhost:7890"
NO_PROXY = "localhost,127.0.0.1"
```

#### `[balance]` — 余额查询（可选）

```toml
[balance]
provider = "zhipu"                    # 内置 provider 类型
api_key_ref = "ANTHROPIC_AUTH_TOKEN"   # 引用 [env] 中的哪个字段作为查询 key
monitor = { type = "TOKENS_LIMIT", unit = "monthly" }  # GLM 专用：监控维度
exhausted_below = 0.01                # 剩余 < 1% → 视为用完
low_below = 0.10                      # 剩余 < 10% → 视为不足
```

不写 `[balance]` 段 = 不支持余额查询，视为"余额充足"。

#### `[say_hi]` — 每日激活（可选，默认关闭）

```toml
[say_hi]
enabled = true
```

#### 完整示例

```toml
# ~/.coser/profiles/glm.toml

[env]
ANTHROPIC_BASE_URL = "https://open.bigmodel.cn/api/anthropic"
ANTHROPIC_AUTH_TOKEN = "your-token"
API_TIMEOUT_MS = "3000000"
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
ANTHROPIC_DEFAULT_HAIKU_MODEL = "glm-4.5-air"
ANTHROPIC_DEFAULT_SONNET_MODEL = "glm-5-turbo"
ANTHROPIC_DEFAULT_OPUS_MODEL = "glm-5"
CLAUDE_CODE_AUTO_COMPACT_WINDOW = "180000"
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE = "90"

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

### Auto-switch 配置格式

```toml
# ~/.coser/config.toml

# 默认 profile（所有规则都没匹配时的兜底）
default_profile = "glm"

# 自动启用 Agent Teams（默认关闭）
enable_agent_teams = true
# 启用后会注入两个环境变量：
#   - CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
#   - CLAUDE_PROFILE="{profile_name} (with agent teams)"

# 绕过所有权限确认（危险模式，默认关闭）
# dangerously_skip_permissions = false
# 启用后会传递 --dangerously-skip-permissions 参数给 claude

# WiFi SSID → profile 映射（需要终端有定位权限）
[wifi_mapping]
"CompanyWiFi" = "bailian"
"Home-5G" = "glm"

# 路由器 IP → profile 映射（SSID 不可用时的备用方案）
[router_mapping]
"192.168.31.1" = "glm"

# 按优先级排列的 profile 链（用于余额检查 fallback）
[fallback_chain]
profiles = ["glm", "deepseek", "bailian"]

# Say-hi 功能配置
[say_hi]
workdir = "~/.coser/say-hi-workspace"
```

## 余额查询机制

### 内置 Provider

| Provider | 端点 | 度量单位 | 显示内容 |
|----------|------|---------|---------|
| **zhipu** (GLM) | `GET bigmodel.cn/api/monitor/usage/quota/limit` | 百分比 | 显示所有限额（五小时/周/月），取最低值做决策 |
| **deepseek** | `GET api.deepseek.com/user/balance` | 金额 (CNY) | 显示 ¥余额 |

### 阈值语义

- zhipu: `exhausted_below`/`low_below` 解释为剩余百分比（0~1）
- deepseek: 解释为金额（CNY）

### 余额状态与行为

| 状态 | 判断条件 | 行为 |
|------|---------|------|
| **充足** | 余额 > low_below 阈值 | 直接使用 |
| **不足** | exhausted_below ≤ 余额 ≤ low_below | 提示用户确认，确认后继续使用 |
| **用完** | 余额 < exhausted_below | 自动 fallback + 显示明显警告，无需确认 |

## CLI 接口

```
coser                         # 自动模式：按决策流程自动选择 profile
coser --profile glm           # 手动指定 profile（跳过余额检查）
coser --select                # 交互式选择 profile（curses TUI，支持键盘上下键）
coser --list                  # 列出所有可用 profile 及其余额状态
coser --dry-run               # 显示当前配置和决策结果（不启动 claude）
coser --say-hi                # 对所有启用 say_hi 的 profile 执行激活
coser --install-cron          # 安装每日 8:00 执行 --say-hi 的 cron 任务
coser --uninstall-cron        # 移除 cron 任务
coser [其他参数]               # 透传给 claude code
```

## 决策流程

```
用户执行 coser
  │
  ├─ 指定了 --profile xxx？
  │    └─ 是 → 直接使用该 profile，跳过余额检查
  │
  ├─ 网络检测（SSID 优先，路由器 IP 备用）
  │    └─ 命中 mapping → 检查对应 profile 余额 → 根据余额状态决定使用或 fallback
  │
  ├─ 未命中 → 按 fallback_chain 顺序检查余额
  │    └─ 找到第一个余额充足的 profile → 使用
  │
  └─ 所有规则都没匹配 → 使用 default_profile
```

### 网络检测优先级

1. **WiFi SSID**（`wifi_mapping`）— 需要终端有定位权限
2. **路由器 IP**（`router_mapping`）— 通过 `ipconfig` 获取，无需额外权限

SSID 获取失败时自动 fallback 到路由器 IP 匹配。

## Say-hi 每日激活

### 目的

每天早上 8:00 对启用 say_hi 的 profile 各发送一次 `hi`，激活 Claude 的 5 小时限额周期，确保下午 13:00 前限额重置。

### 执行逻辑 (`coser --say-hi`)

1. 扫描所有 profile，筛选 `say_hi.enabled = true` 的
2. 在固定工作目录下对每个 profile 执行 `claude -p "hi" --max-turns 1`
3. 逐个显示 profile 名称、response 内容和执行结果
4. 全部成功时无系统通知
5. 有失败时通过 macOS 通知中心推送告警

### 调度

```bash
coser --install-cron      # 自动写入 crontab: 0 8 * * * /path/to/coser --say-hi
coser --uninstall-cron    # 移除
```

## 项目结构

```
coser/
├── pyproject.toml
├── docs/
│   ├── requirement.md
│   └── user-guide.md
└── coser/
    ├── __init__.py
    ├── __main__.py       # 入口: python -m coser
    ├── cli.py            # 参数解析、主流程编排
    ├── config.py         # 读取 config.toml 和 profiles/*.toml（含白名单校验）
    ├── selector.py       # 自动决策逻辑（WiFi/路由器IP/fallback/余额检查）
    ├── say_hi.py         # 每日激活 + cron 管理
    ├── balance/
    │   ├── __init__.py
    │   ├── base.py       # BalanceChecker 基类 + 工厂
    │   ├── zhipu.py      # 智谱余额查询（显示所有限额维度）
    │   └── deepseek.py   # DeepSeek 余额查询
    └── tui/
        ├── __init__.py
        └── select.py     # curses 交互式选择
```

## 安装

```bash
pip install -e .    # 开发模式
```

安装后 `coser` 命令全局可用，可选 `alias claude=coser`。

## 设计决策

1. **语言**: Python（依赖 `tomli` for Python < 3.11）
2. **调用方式**: 独立 CLI 命令
3. **配置格式**: TOML，profile 的 `[env]` 段使用白名单校验
4. **代理**: `[proxy]` 段只需配置 PROXY 和 NO_PROXY，自动展开为标准环境变量
5. **余额查询**: 内置 provider 类型，显示所有限额维度，取最低值做决策
6. **网络检测**: SSID 优先，路由器 IP 备用（无需额外权限）
7. **余额状态**: 三级（充足/不足/用完），不足需确认，用完自动 fallback
8. **手动指定 profile**: `--profile` 跳过余额检查
9. **交互式选择**: `--select` 触发 curses TUI，异步显示余额
10. **Say-hi**: 默认关闭，profile 中显式启用；失败时发 macOS 通知
11. **安装方式**: pip install -e .
