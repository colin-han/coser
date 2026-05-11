"""Claude Code OAuth usage balance checker.

Reads OAuth access token from macOS Keychain (preferred) or
``~/.claude/.credentials.json`` (fallback), then queries the
``/api/oauth/usage`` endpoint for current subscription quota usage.
"""

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Optional, Tuple

from coser.balance.base import BalanceChecker, BalanceResult, BalanceStatus


CREDENTIALS_FILE = "~/.claude/.credentials.json"
KEYCHAIN_SERVICE = "Claude Code-credentials"

# Windows returned by /api/oauth/usage and their short display labels.
WINDOW_LABELS: Tuple[Tuple[str, str], ...] = (
    ("five_hour", "5h"),
    ("seven_day", "7d"),
    ("seven_day_opus", "7d-Opus"),
    ("seven_day_sonnet", "7d-Sonnet"),
)


class ClaudeChecker(BalanceChecker):
    """Balance checker for Claude Code OAuth subscriptions."""

    API_URL = "https://api.anthropic.com/api/oauth/usage"
    TIMEOUT = 10

    def __init__(
        self,
        api_key: str = "",
        exhausted_below: float = 0.01,
        low_below: float = 0.10,
        proxy: Optional[str] = None,
    ):
        super().__init__(api_key, exhausted_below, low_below)
        self.proxy = proxy or None

    @staticmethod
    def _parse_token(raw: str) -> str:
        data = json.loads(raw)
        oauth = data.get("claudeAiOauth") or {}
        token = oauth.get("accessToken")
        if not token:
            raise RuntimeError("凭证中未找到 accessToken")
        return token

    def _read_token(self) -> str:
        # macOS Keychain preferred
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return self._parse_token(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        creds_path = os.path.expanduser(CREDENTIALS_FILE)
        if not os.path.exists(creds_path):
            raise RuntimeError(
                f"未找到 Claude Code 登录凭证（Keychain 不可访问且 {creds_path} 不存在）"
            )
        with open(creds_path, "r", encoding="utf-8") as f:
            return self._parse_token(f.read())

    def _build_opener(self) -> urllib.request.OpenerDirector:
        if self.proxy:
            handler = urllib.request.ProxyHandler({
                "http": self.proxy,
                "https": self.proxy,
            })
            return urllib.request.build_opener(handler)
        return urllib.request.build_opener()

    def check(self) -> BalanceResult:
        try:
            token = self._read_token()
        except Exception as e:
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="无凭证",
                error=str(e),
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(self.API_URL, headers=headers, method="GET")
        opener = self._build_opener()

        try:
            with opener.open(req, timeout=self.TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))

            parts = []
            min_remaining = 1.0
            for key, label in WINDOW_LABELS:
                window = data.get(key)
                if not window:
                    continue
                util = window.get("utilization")
                if util is None:
                    continue
                remaining_pct = max(0.0, 100.0 - float(util))
                remaining_ratio = remaining_pct / 100.0
                if remaining_ratio < min_remaining:
                    min_remaining = remaining_ratio
                parts.append(f"{label}: {remaining_pct:.0f}%")

            if not parts:
                return BalanceResult(
                    status=BalanceStatus.UNKNOWN,
                    raw_value=None,
                    display_text="无配额数据",
                )

            status = self.classify(min_remaining)
            return BalanceResult(
                status=status,
                raw_value=min_remaining,
                display_text=", ".join(parts),
            )

        except urllib.error.HTTPError as e:
            if e.code == 401:
                error_msg = "OAuth token 已过期，请重新运行 claude 登录"
            else:
                error_msg = f"HTTP {e.code}: {e.reason}"
                try:
                    error_msg += f" - {e.read().decode('utf-8')}"
                except Exception:
                    pass
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="查询失败",
                error=error_msg,
            )
        except urllib.error.URLError as e:
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="网络错误",
                error=str(e.reason),
            )
        except json.JSONDecodeError as e:
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="解析失败",
                error=str(e),
            )
        except Exception as e:
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="未知错误",
                error=str(e),
            )
