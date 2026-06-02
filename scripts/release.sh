#!/usr/bin/env bash
#
# 发布脚本：更新版本号 -> 提交 -> 打 tag -> 推送 -> 重装本地版本
#
# 用法:
#   scripts/release.sh <major|minor|patch>
#
# 说明:
#   - 依据语义化版本规则递增 pyproject.toml 中的 version
#   - 自动生成发布提交、带注释的 tag，并推送 main 与 tag 到 origin
#   - 通过 coser 的 pipx venv 重装本地版本（等同 pipx install . --force）
#
set -euo pipefail

# --- 定位项目根目录 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PYPROJECT="$ROOT_DIR/pyproject.toml"

# --- 校验参数 ---
BUMP="${1:-}"
case "$BUMP" in
  major|minor|patch) ;;
  *)
    echo "错误: 需要一个参数 major|minor|patch" >&2
    echo "用法: scripts/release.sh <major|minor|patch>" >&2
    exit 1
    ;;
esac

# --- 校验工作区干净 ---
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "错误: 工作区存在未提交的改动，请先提交或暂存。" >&2
  git status --short >&2
  exit 1
fi

# --- 读取当前版本 ---
CURRENT="$(grep -E '^version\s*=' "$PYPROJECT" | head -1 | sed -E 's/.*"([^"]+)".*/\1/')"
if [[ ! "$CURRENT" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "错误: 无法从 pyproject.toml 解析版本号 (得到: '$CURRENT')" >&2
  exit 1
fi

IFS='.' read -r MAJOR MINOR PATCH <<<"$CURRENT"
case "$BUMP" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
esac
NEW="$MAJOR.$MINOR.$PATCH"
TAG="v$NEW"

echo "版本: $CURRENT -> $NEW ($BUMP)"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "错误: tag $TAG 已存在。" >&2
  exit 1
fi

# --- 更新 pyproject.toml ---
# 仅替换以 version = 开头的行（[project] 段的版本号），不影响依赖中的版本约束
sed -i.bak -E "s/^version = \"[^\"]+\"/version = \"$NEW\"/" "$PYPROJECT"
rm -f "$PYPROJECT.bak"

# 校验替换成功
if ! grep -qE "^version = \"$NEW\"" "$PYPROJECT"; then
  echo "错误: 更新版本号失败。" >&2
  git checkout -- "$PYPROJECT"
  exit 1
fi

# --- 提交 ---
git add "$PYPROJECT"
git commit -m "chore: 发布 $TAG

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"

# --- 打 tag ---
git tag -a "$TAG" -m "发布 $TAG"

# --- 推送 ---
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git push origin "$BRANCH"
git push origin "$TAG"

# --- 重装本地版本 ---
COSER_PY="$HOME/.local/pipx/venvs/coser/bin/python"
if command -v pipx >/dev/null 2>&1; then
  pipx install . --force
elif [[ -x "$COSER_PY" ]]; then
  echo "未找到 pipx 命令，回退到使用 coser 的 venv pip 重装。"
  "$COSER_PY" -m pip install --force-reinstall --no-deps "$ROOT_DIR"
else
  echo "警告: 既未找到 pipx，也未找到 coser 的 venv ($COSER_PY)，跳过本地安装。" >&2
fi

# --- 验证 ---
echo "---"
if command -v coser >/dev/null 2>&1; then
  echo "已安装版本: $(coser --version 2>/dev/null | head -1)"
fi
echo "发布完成: $TAG"
