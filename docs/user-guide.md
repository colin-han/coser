# Coser 用户手册

## 目录

- [配置](#配置)
  - [Profile 配置](#profile-配置)
  - [自动切换规则](#自动切换规则)
- [命令详解](#命令详解)
  - [自动模式](#自动模式)
  - [手动指定 Profile](#手动指定-profile)
  - [交互式选择](#交互式选择)
  - [列出状态](#列出状态)
  - [预演模式](#预演模式)
  - [每日激活](#每日激活)
- [余额查询 Provider](#余额查询-provider)
- [决策流程](#决策流程)
- [FAQ](#faq)

---

## 配置

配置文件位于 `~/.coser/` 目录下。

### Profile 配置

每个 profile 是 `~/.coser/profiles/` 下的一个 TOML 文件，文件名即为 profile 名称。

#### 最小配置（仅环境变量）

```toml
# ~/.coser/profiles/my_provider.toml

[env]
ANTHROPIC_BASE_URL = "https://api.example.com"
ANTHROPIC_AUTH_TOKEN = "sk-your-token"
```

#### 完整配置

```toml
# ~/.coser/profiles/glm.toml

# 环境变量（启动 claude code 时注入）
[env]
ANTHROPIC_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
ANTHROPIC_AUTH_TOKEN = "your-token-here"
ANTHROPIC_DEFAULT_HAIKU_MODEL = "glm-4-flash"
ANTHROPIC_DEFAULT_SONNET_MODEL = "glm-4-plus"
ANTHROPIC_DEFAULT_OPUS_MODEL = "glm-4"
API_TIMEOUT_MS = "3000000"
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"

# 余额查询（可选）
[balance]
provider = "zhipu"
api_key_ref = "ANTHROPIC_AUTH_TOKEN"
monitor = { type = "TOKENS_LIMIT", unit = "monthly" }
exhausted_below = 0.01
low_below = 0.10

# 每日激活（可选，默认关闭）
[say_hi]
enabled = true
```

#### 支持的环境变量

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_BASE_URL` | API 代理地址，留空则使用官方默认地址 |
| `ANTHROPIC_AUTH_TOKEN` | API 认证 Token |
| `API_TIMEOUT_MS` | 请求超时时间（毫秒） |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 禁用非必要网络请求（推荐第三方代理下开启） |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | 覆盖 Haiku 模型名称 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | 覆盖 Sonnet 模型名称 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | 覆盖 Opus 模型名称 |

#### `[balance]` 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `provider` | 是 | 内置 provider 类型：`zhipu`、`deepseek` |
| `api_key_ref` | 是 | 引用 `[env]` 中哪个字段作为查询 API key |
| `monitor` | 否 | 仅 zhipu：`{ type = "TOKENS_LIMIT"/"TIME_LIMIT", unit = "monthly"/"weekly"/"5h" }` |
| `exhausted_below` | 否 | "用完"阈值，低于此值自动 fallback |
| `low_below` | 否 | "不足"阈值，低于此值提示用户确认 |

不写 `[balance]` 段 = 该 profile 不支持余额查询，自动决策时视为"余额充足"。

#### `[say_hi]` 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `enabled` | 是 | `true` 启用每日激活，`false` 或不写此段 = 关闭 |

### 自动切换规则

编辑 `~/.coser/config.toml`：

```toml
# 默认 profile（所有规则都没匹配时的兜底）
default_profile = "glm"

# 自动启用 Agent Teams（可选，默认关闭）
enable_agent_teams = true

# WiFi SSID → profile 映射（精确匹配 SSID 名称）
[wifi_mapping]
"CompanyWiFi" = "bailian"
"Home-5G" = "glm"

# 按优先级排列的 profile 链
# WiFi 未匹配时，按此顺序检查余额，第一个充足的被选中
[fallback_chain]
profiles = ["glm", "deepseek", "bailian"]

# 每日激活的工作目录
[say_hi]
workdir = "~/.coser/say-hi-workspace"
```

#### `config.toml` 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `default_profile` | 否 | 兜底 profile 名称 |
| `enable_agent_teams` | 否 | `true` 启动时自动注入 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`，默认 `false` |
| `wifi_mapping` | 否 | SSID → profile 映射表 |
| `fallback_chain.profiles` | 否 | 有序 profile 列表，用于余额 fallback |
| `say_hi.workdir` | 否 | say-hi 执行的固定工作目录，默认 `~/.coser/say-hi-workspace` |

---

## 命令详解

### 自动模式

```bash
coser
```

按决策流程自动选择 profile 并启动 claude code。透传所有额外参数给 claude code。

```bash
coser --dangerously-skip-permissions
# 等同于用选定的 profile 启动 claude --dangerously-skip-permissions
```

### 手动指定 Profile

```bash
coser --profile glm
```

直接使用指定 profile，**跳过余额检查**。适用于你明确知道要用哪个账号的场景。

### 交互式选择

```bash
coser --select
```

启动 curses TUI 界面：

```
  glm          余额: 85% ████████░░
> deepseek     余额: ¥12.50
  bailian      余额: 查询中...
  kimi         (不支持查询)

[↑/↓] 切换  [Enter] 确认  [q] 取消
```

- 上下键选择，Enter 确认
- 各 profile 的余额异步查询，实时刷新显示
- 选中后直接使用，跳过余额检查
- 查询超时 5 秒

### 列出状态

```bash
coser --list
```

列出所有 profile 及其余额状态，用于运维查看：

```
Profile         余额状态      详情
glm             充足          85% (TOKENS_LIMIT, monthly)
deepseek        充足          ¥12.50
bailian         不足          ¥3.20 (阈值: ¥5.00)
kimi            不支持查询
```

### 预演模式

```bash
coser --dry-run
```

显示当前环境下的决策结果，但不启动 claude code：

```
当前 WiFi: Home-5G
匹配规则: wifi_mapping → glm
余额状态: 充足 (85%)
决策结果: 使用 profile glm

(预演模式，未启动 claude code)
```

### 每日激活

```bash
coser --say-hi
```

对所有 `[say_hi] enabled = true` 的 profile 执行激活：

1. 在配置的固定工作目录下执行
2. 对每个 profile 加载环境变量后运行 `claude -p "hi" --max-turns 1`
3. 全部成功 → 无输出
4. 有失败 → 发送 macOS 系统通知

#### 安装定时任务

```bash
coser --install-cron    # 安装每日 8:00 的 cron 任务
coser --uninstall-cron  # 移除
```

安装后 crontab 中会增加：

```
0 8 * * * /path/to/coser --say-hi
```

---

## 余额查询 Provider

### zhipu（智谱 / GLM）

| 项目 | 值 |
|------|-----|
| 端点 | `GET https://bigmodel.cn/api/monitor/usage/quota/limit` |
| 认证 | `Authorization: Bearer {api_key}` |
| 度量单位 | 百分比（0~1） |
| `exhausted_below` 含义 | 剩余百分比，如 `0.01` = 剩余 1% 以下视为用完 |
| `low_below` 含义 | 剩余百分比，如 `0.10` = 剩余 10% 以下视为不足 |
| `monitor` | 必填，指定监控维度，如 `{ type = "TOKENS_LIMIT", unit = "monthly" }` |

### deepseek

| 项目 | 值 |
|------|-----|
| 端点 | `GET https://api.deepseek.com/user/balance` |
| 认证 | `Authorization: Bearer {api_key}` |
| 度量单位 | 金额（CNY） |
| `exhausted_below` 含义 | 余额金额，如 `1.0` = 余额低于 ¥1 视为用完 |
| `low_below` 含义 | 余额金额，如 `5.0` = 余额低于 ¥5 视为不足 |

---

## 决策流程

```
coser
 │
 ├─ --profile 指定? → 直接使用，跳过余额检查
 │
 ├─ --select? → 进入交互式选择 TUI
 │
 └─ 自动模式:
     │
     ├─ WiFi SSID 命中 wifi_mapping?
     │   └─ 是 → 检查对应 profile 余额
     │       ├─ 充足 → 使用
     │       ├─ 不足 → 提示确认
     │       └─ 用完 → 自动 fallback 到 fallback_chain
     │
     ├─ WiFi 未命中 → 按 fallback_chain 顺序检查
     │   └─ 第一个充足的 → 使用
     │
     └─ 都没匹配 → 使用 default_profile
```

### 余额状态定义

| 状态 | 判断 | 行为 |
|------|------|------|
| **充足** | 余额 > `low_below` | 直接使用 |
| **不足** | `exhausted_below` ≤ 余额 ≤ `low_below` | 提示用户确认，确认后继续使用 |
| **用完** | 余额 < `exhausted_below` | 自动跳到下一个候选，显示警告 |

---

## FAQ

**Q: 不连接 WiFi（使用有线网络）时会怎样？**

A: WiFi SSID 获取为空，不会命中 `wifi_mapping`，直接走 `fallback_chain` 或 `default_profile`。

**Q: 所有 profile 余额都用完了怎么办？**

A: fallback 链全部跳过后，使用 `default_profile`，并显示警告提示。

**Q: 如何添加新的 provider 支持？**

A: 目前支持 `zhipu` 和 `deepseek`。如需新增，可在项目的 `coser/balance/` 下添加对应的 provider 模块。

**Q: macOS 通知在哪里看？**

A: 系统通知中心。通知标题为 "Coser"，包含失败的 profile 名称和原因。

**Q: 可以在 Linux 上使用吗？**

A: WiFi SSID 检测和 macOS 通知是 macOS 专用的。核心的 profile 切换和余额检查功能可在 Linux 上使用，但需要适配 WiFi 检测逻辑。
