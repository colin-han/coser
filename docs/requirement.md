# Coser - Claude Code 账户切换服务

## 概述

Coser 是一个 Claude Code 账户自动切换工具，能够根据当前环境（WiFi 网络、账户余额等）自动选择合适的 profile 启动 Claude Code。

## 技术选型

- **语言**: Python
- **形式**: 独立 CLI 命令（`coser`）
- **部署**: 通过 pip install 或直接放入 PATH

## 配置结构

### 目录布局

```
~/.coser/
├── profiles/           # 各 provider 的 profile 配置
│   ├── glm.toml
│   ├── deepseek.toml
│   ├── bailian.toml
│   ├── kimi.toml
│   └── claude_official.toml
└── config.toml         # 自动切换规则、默认 profile 等
```

### Profile 配置格式

每个 profile 使用 TOML 格式，包含 env、balance、say_hi 三个段落：

```toml
# ~/.coser/profiles/glm.toml

[env]
ANTHROPIC_BASE_URL = "https://..."
ANTHROPIC_AUTH_TOKEN = "sk-..."
ANTHROPIC_DEFAULT_HAIKU_MODEL = "model-name"
ANTHROPIC_DEFAULT_SONNET_MODEL = "model-name"
ANTHROPIC_DEFAULT_OPUS_MODEL = "model-name"
API_TIMEOUT_MS = "3000000"
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"

[balance]
provider = "zhipu"                    # 内置 provider 类型
api_key_ref = "ANTHROPIC_AUTH_TOKEN"   # 引用 [env] 中的哪个字段作为查询 key
monitor = { type = "TOKENS_LIMIT", unit = "monthly" }  # GLM 专用：监控维度
exhausted_below = 0.01                # 剩余 < 1% → 视为用完
low_below = 0.10                      # 剩余 < 10% → 视为不足

# 每日 say-hi 激活（默认关闭，需要显式启用）
[say_hi]
enabled = true
```

```toml
# ~/.coser/profiles/deepseek.toml

[env]
ANTHROPIC_BASE_URL = "https://..."
ANTHROPIC_AUTH_TOKEN = "sk-..."

[balance]
provider = "deepseek"
api_key_ref = "ANTHROPIC_AUTH_TOKEN"
exhausted_below = 1.0     # 余额 < ¥1 → 视为用完
low_below = 5.0           # 余额 < ¥5 → 视为不足
```

```toml
# ~/.coser/profiles/kimi.toml

[env]
ANTHROPIC_BASE_URL = "https://..."
ANTHROPIC_AUTH_TOKEN = "sk-..."

# 不写 [balance] 段 = 不支持余额查询
# 不写 [say_hi] 段 = 不参与每日激活（默认关闭）
```

### Auto-switch 配置格式

```toml
# ~/.coser/config.toml

# 默认 profile（所有规则都没匹配时的兜底）
default_profile = "glm"

# 自动启用 Agent Teams（默认关闭）
enable_agent_teams = true

# WiFi SSID → profile 映射（精确匹配）
[wifi_mapping]
"CompanyWiFi" = "bailian"
"Home-5G" = "glm"

# 按优先级排列的 profile 链（用于余额检查 fallback）
[fallback_chain]
profiles = ["glm", "deepseek", "bailian"]

# Say-hi 功能配置
[say_hi]
workdir = "~/.coser/say-hi-workspace"   # 固定工作目录
```

## 余额查询机制

### 内置 Provider

| Provider | 端点 | 认证 | 响应结构 | 度量单位 |
|----------|------|------|---------|---------|
| **zhipu** (GLM) | `GET bigmodel.cn/api/monitor/usage/quota/limit` | Bearer token | `data.limits[]` 数组，含 type/unit/remaining/percentage | 百分比 (0~1) |
| **deepseek** | `GET api.deepseek.com/user/balance` | Bearer token | `balance_infos[0].total_balance` | 金额 (CNY) |
| **anthropic** | 无程序化 API | — | 仅能通过 `/cost` 命令交互查看 | — |

### 阈值语义

`exhausted_below` 和 `low_below` 的含义由内置 provider 逻辑解释：
- zhipu: 解释为百分比（0~1）
- deepseek: 解释为金额（CNY）

### 余额状态与行为

| 状态 | 判断条件 | 行为 |
|------|---------|------|
| **充足** | 余额 > low_below 阈值 | 直接使用 |
| **不足** | exhausted_below ≤ 余额 ≤ low_below | 提示用户确认，确认后继续使用 |
| **用完** | 余额 < exhausted_below | 自动 fallback + 显示明显警告，无需确认 |

不写 `[balance]` 段的 profile（如 kimi）不参与余额检查，视为"余额充足"。

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

### 交互式选择 (`--select`)

使用 curses 实现 fzf 风格的键盘导航，同时异步查询各 profile 余额：

- 所有余额查询并发发起（asyncio）
- 结果返回后原地刷新显示余额信息
- 超时（5秒）未返回的显示"查询超时"
- 用户随时可用上下键选择 + Enter 确认，不必等所有查询完成
- 不支持余额查询的 profile 显示"(不支持查询)"

## 决策流程

```
用户执行 coser
  │
  ├─ 指定了 --profile xxx？
  │    └─ 是 → 直接使用该 profile，跳过余额检查
  │
  ├─ 检查 WiFi SSID
  │    └─ 命中 wifi_mapping → 检查对应 profile 余额 → 根据余额状态决定使用或 fallback
  │
  ├─ WiFi 未命中 → 按 fallback_chain 顺序检查余额
  │    └─ 找到第一个余额充足的 profile → 使用
  │
  └─ 所有规则都没匹配 → 使用 default_profile
```

余额检查在每个候选 profile 上执行：
1. **用完** → 自动跳到下一个候选，显示警告
2. **不足** → 提示用户确认（继续使用 / 切换到下一个）
3. **充足** → 直接使用

## Say-hi 每日激活

### 目的

每天早上 8:00 对启用 say_hi 的 profile 各发送一次 `hi`，激活 Claude 的 5 小时限额周期，确保下午 13:00 前限额重置，最大化利用率。

### Profile 配置

在 profile 的 `[say_hi]` 段中启用（默认关闭）：

```toml
[say_hi]
enabled = true
```

不写 `[say_hi]` 段或 `enabled = false` 的 profile 不参与每日激活。

### 执行逻辑 (`coser --say-hi`)

1. 扫描所有 profile，筛选 `say_hi.enabled = true` 的
2. 在配置的固定工作目录（`config.toml` 中的 `say_hi.workdir`）下
3. 对每个 profile：加载 env → 执行 `claude -p "hi" --max-turns 1` → 记录成功/失败
4. 全部成功时无通知（不打扰）
5. 有失败时通过 `osascript` 发送 macOS 系统通知，确保用户上班时能看到

### 调度

通过 cron 执行，提供辅助命令：

```bash
coser --install-cron      # 自动写入 crontab: 0 8 * * * /path/to/coser --say-hi
coser --uninstall-cron    # 移除
```

## 已确认的设计决策

1. **语言**: Python（零额外依赖、可维护性好）
2. **调用方式**: 独立 CLI 命令，可通过 `alias claude=coser` 替代
3. **配置格式**: TOML（profile 文件 + 独立的 config.toml）
4. **余额查询**: 内置 provider 类型（zhipu/deepseek/anthropic），不写 [balance] = 不支持
5. **WiFi 匹配**: 匹配到的 profile 也会检查余额，不足时走 fallback
6. **余额状态**: 三级（充足/不足/用完），不足需确认，用完自动 fallback
7. **手动指定 profile**: `--profile` 跳过余额检查，直接使用
8. **交互式选择**: `--select` 触发 curses TUI，异步显示余额，支持键盘导航

## 项目结构

```
coser/
├── pyproject.toml
├── docs/
│   └── requirement.md
└── coser/
    ├── __init__.py
    ├── __main__.py       # 入口: python -m coser
    ├── cli.py            # 参数解析、主流程编排
    ├── config.py         # 读取 config.toml 和 profiles/*.toml
    ├── selector.py       # 自动决策逻辑（WiFi/fallback/余额检查）
    ├── say_hi.py         # 每日激活逻辑
    ├── balance/
    │   ├── __init__.py
    │   ├── base.py       # BalanceChecker 基类
    │   ├── zhipu.py      # 智谱余额查询
    │   └── deepseek.py   # DeepSeek 余额查询
    └── tui/
        ├── __init__.py
        └── select.py     # curses 交互式选择
```

## 安装

```bash
pip install -e .    # 开发模式
pip install .       # 正式安装
```

安装后可选：`alias claude=coser`

## 已确认的设计决策

1. **语言**: Python（零额外依赖）
2. **调用方式**: 独立 CLI 命令，可通过 `alias claude=coser` 替代
3. **配置格式**: TOML（profile 文件 + 独立的 config.toml）
4. **余额查询**: 内置 provider 类型（zhipu/deepseek/anthropic），不写 [balance] = 不支持
5. **WiFi 匹配**: 匹配到的 profile 也会检查余额，不足时走 fallback
6. **余额状态**: 三级（充足/不足/用完），不足需确认，用完自动 fallback
7. **手动指定 profile**: `--profile` 跳过余额检查，直接使用
8. **交互式选择**: `--select` 触发 curses TUI，异步显示余额，支持键盘导航
9. **项目结构**: 扁平 layout（coser/ 直接在项目根目录下）
10. **安装方式**: pip install -e . (开发) / pip install . (正式)
11. **Say-hi**: 每日激活功能，默认关闭，profile 中显式启用；失败时发 macOS 系统通知
