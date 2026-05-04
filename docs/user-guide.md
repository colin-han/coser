# Coser 用户手册

## 目录

- [配置](#配置)
  - [Profile 配置](#profile-配置)
  - [自动切换规则](#自动切换规则)
- [命令详解](#命令详解)
- [余额查询 Provider](#余额查询-provider)
- [决策流程](#决策流程)
- [FAQ](#faq)

---

## 配置

配置文件位于 `~/.coser/` 目录下。

### Profile 配置

每个 profile 是 `~/.coser/profiles/` 下的一个 TOML 文件，文件名即为 profile 名称。

#### `[env]` — 环境变量（白名单制）

仅允许以下变量，其他变量会导致加载报错：

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_BASE_URL` | API 代理地址，留空则使用官方默认地址 |
| `ANTHROPIC_AUTH_TOKEN` | API 认证 Token |
| `API_TIMEOUT_MS` | 请求超时时间（毫秒） |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 禁用非必要网络请求（推荐第三方代理下开启） |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | 覆盖 Haiku 模型名称 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | 覆盖 Sonnet 模型名称 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | 覆盖 Opus 模型名称 |

#### `[proxy]` — 代理配置（可选）

只需配置两个变量，程序自动展开为标准代理环境变量：

| 配置项 | 展开为 |
|--------|--------|
| `PROXY` | `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`, `https_proxy` |
| `NO_PROXY` | `NO_PROXY`, `no_proxy` |

```toml
[proxy]
PROXY = "http://localhost:7890"
NO_PROXY = "localhost,127.0.0.1"
```

#### `[balance]` — 余额查询（可选）

| 字段 | 必填 | 说明 |
|------|------|------|
| `provider` | 是 | 内置 provider 类型：`zhipu`、`deepseek` |
| `api_key_ref` | 是 | 引用 `[env]` 中哪个字段作为查询 API key |
| `monitor` | 否 | 仅 zhipu：`{ type, unit }` |
| `exhausted_below` | 否 | "用完"阈值，低于此值自动 fallback |
| `low_below` | 否 | "不足"阈值，低于此值提示用户确认 |

不写 `[balance]` 段 = 不支持余额查询，视为"余额充足"。

#### `[say_hi]` — 每日激活（可选，默认关闭）

| 字段 | 必填 | 说明 |
|------|------|------|
| `enabled` | 是 | `true` 启用，`false` 或不写此段 = 关闭 |

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

### 自动切换规则

编辑 `~/.coser/config.toml`：

```toml
default_profile = "glm"
enable_agent_teams = true

# WiFi SSID → profile 映射（需要终端有定位权限）
[wifi_mapping]
"CompanyWiFi" = "bailian"
"Home-5G" = "glm"

# 路由器 IP → profile 映射（SSID 不可用时的备用方案）
[router_mapping]
"192.168.31.1" = "glm"
"10.0.0.1" = "bailian"

[fallback_chain]
profiles = ["glm", "deepseek", "bailian"]

[say_hi]
workdir = "~/.coser/say-hi-workspace"
```

#### `config.toml` 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `default_profile` | 否 | 兜底 profile 名称 |
| `enable_agent_teams` | 否 | `true` 启动时自动注入 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| `wifi_mapping` | 否 | SSID → profile 映射表（需要定位权限） |
| `router_mapping` | 否 | 路由器 IP → profile 映射表（无需额外权限） |
| `fallback_chain.profiles` | 否 | 有序 profile 列表，用于余额 fallback |
| `say_hi.workdir` | 否 | say-hi 执行的固定工作目录 |

---

## 命令详解

### 自动模式

```bash
coser                    # 自动选择 profile 并启动 claude code
coser --some-claude-flag # 自动选择 profile，额外参数透传给 claude
```

### 手动指定 Profile

```bash
coser --profile glm      # 直接使用 glm，跳过余额检查
```

### 交互式选择

```bash
coser --select
```

启动 curses TUI 界面：

```
  glm          余额: 五小时: 54%, 周: 81%, 月: 99%
> deepseek     余额: ¥4.54 (不足)
  bailian      (不支持查询)
  kimi         (不支持查询)

[↑/↓] 切换  [Enter] 确认  [q] 取消
```

- 各 profile 余额异步查询，实时刷新显示
- 上下键选择，Enter 确认，q 取消
- 查询超时 5 秒

### 列出状态

```bash
coser --list
```

```
Profile          Balance      Details
--------------------------------------------------
glm              充足         五小时: 54%, 周: 81%, 月: 99%
deepseek         不足         ¥4.54
bailian          不支持查询
kimi             不支持查询
```

### 预演模式

```bash
coser --dry-run
```

```
当前 WiFi: (未检测到)
当前路由器: 192.168.31.1
决策路径: Router IP '192.168.31.1' matched to profile 'glm'
余额状态: 充足 (五小时: 54%, 周: 81%, 月: 99%)
决策结果: 使用 profile glm

(预演模式，未启动 claude code)
```

### 每日激活

```bash
coser --say-hi
```

对每个启用 say_hi 的 profile 逐个执行并显示结果：

```
[glm] sending hi...
[glm] response: Hello! How can I help you today?
[glm] OK

Say-hi complete: 1/1 succeeded
```

有失败时推送 macOS 通知中心告警。

```bash
coser --install-cron      # 安装每日 8:00 cron 任务
coser --uninstall-cron    # 移除
```

---

## 余额查询 Provider

### zhipu（智谱 / GLM）

| 项目 | 值 |
|------|-----|
| 端点 | `GET https://bigmodel.cn/api/monitor/usage/quota/limit` |
| 认证 | `Authorization: Bearer {api_key}` |
| 度量单位 | 百分比（0~1） |
| 显示 | 所有限额维度（五小时/周/月），取最低值做决策 |
| `exhausted_below` 含义 | 剩余百分比，如 `0.01` = 剩余 1% 以下视为用完 |
| `low_below` 含义 | 剩余百分比，如 `0.10` = 剩余 10% 以下视为不足 |

### deepseek

| 项目 | 值 |
|------|-----|
| 端点 | `GET https://api.deepseek.com/user/balance` |
| 认证 | `Authorization: Bearer {api_key}` |
| 度量单位 | 金额（CNY） |
| 显示 | ¥余额 |
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
     ├─ 网络检测（SSID 优先 → 路由器 IP 备用）
     │   └─ 命中 → 检查余额
     │       ├─ 充足 → 使用
     │       ├─ 不足 → 提示确认
     │       └─ 用完 → 自动 fallback
     │
     ├─ 未命中 → 按 fallback_chain 顺序检查
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

**Q: WiFi SSID 显示"未检测到"？**

A: macOS 需要定位权限才能读取 SSID。在 **系统设置 → 隐私与安全性 → 定位服务** 中为终端应用开启权限。如果不方便授权，使用 `router_mapping`（路由器 IP 匹配）作为替代方案。

**Q: 如何知道当前路由器 IP？**

A: 运行 `coser --dry-run`，会显示当前检测到的路由器 IP。将这个 IP 添加到 `config.toml` 的 `[router_mapping]` 中即可。

**Q: 所有 profile 余额都用完了怎么办？**

A: fallback 链全部跳过后，使用 `default_profile`，并显示警告。

**Q: `[env]` 中配置了不在白名单中的变量会怎样？**

A: 加载 profile 时会报错，列出允许的变量名。

**Q: 代理配置怎么用？**

A: 在 profile 中添加 `[proxy]` 段，只需配置 `PROXY`。程序会自动设置 `HTTP_PROXY`、`HTTPS_PROXY` 等所有标准代理环境变量。

**Q: 可以在 Linux 上使用吗？**

A: 核心的 profile 切换和余额查询功能可跨平台使用。WiFi SSID 检测和 macOS 通知是 macOS 专用的。
