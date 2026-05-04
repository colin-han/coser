"""Zhipu AI balance checker."""

import json
import urllib.error
import urllib.request
from typing import Optional

from coser.balance.base import BalanceChecker, BalanceResult, BalanceStatus


# Unit codes to Chinese labels
UNIT_LABELS = {
    3: "五小时",
    5: "月",
    6: "周",
}


class ZhipuChecker(BalanceChecker):
    """Balance checker for Zhipu AI (bigmodel.cn)."""

    API_URL = "https://bigmodel.cn/api/monitor/usage/quota/limit"
    TIMEOUT = 10

    def __init__(
        self,
        api_key: str,
        exhausted_below: float = 0.01,
        low_below: float = 0.1,
        monitor_config: Optional[dict] = None,
        monitor: Optional[dict] = None,
    ):
        super().__init__(api_key, exhausted_below, low_below)
        self.monitor_config = monitor_config or monitor or {}

    def check(self) -> BalanceResult:
        """Check all Zhipu limits and return the most restrictive status.

        Returns:
            BalanceResult with the lowest percentage as raw_value,
            and all limits displayed in display_text.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(
            self.API_URL,
            headers=headers,
            method="GET"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))

            if not data.get("success", False):
                return BalanceResult(
                    status=BalanceStatus.UNKNOWN,
                    raw_value=None,
                    display_text="Unknown",
                    error=f"API returned success=False: {data.get('message', 'Unknown error')}"
                )

            limits = data.get("data", {}).get("limits", [])
            if not limits:
                return BalanceResult(
                    status=BalanceStatus.UNKNOWN,
                    raw_value=None,
                    display_text="Unknown",
                    error="No limit data in response"
                )

            # Build display for all limits, find the lowest remaining
            # API returns percentage as usage (0-100 scale), need to compute remaining
            parts = []
            min_remaining = 1.0  # ratio 0-1
            for limit in limits:
                usage_pct = limit.get("percentage")
                if usage_pct is None:
                    continue
                remaining_pct = 100.0 - usage_pct
                if remaining_pct < 0:
                    remaining_pct = 0
                remaining_ratio = remaining_pct / 100.0
                if remaining_ratio < min_remaining:
                    min_remaining = remaining_ratio
                unit_code = limit.get("unit", 0)
                label = UNIT_LABELS.get(unit_code, f"unit={unit_code}")
                parts.append(f"{label}: {remaining_pct:.0f}%")

            display_text = ", ".join(parts) if parts else "无数据"
            status = self.classify(min_remaining)

            return BalanceResult(
                status=status,
                raw_value=min_remaining,
                display_text=display_text,
            )

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP error {e.code}: {e.reason}"
            try:
                error_body = e.read().decode("utf-8")
                error_msg += f" - {error_body}"
            except Exception:
                pass
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="Unknown",
                error=error_msg
            )
        except urllib.error.URLError as e:
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="Unknown",
                error=f"Network error: {e.reason}"
            )
        except json.JSONDecodeError as e:
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="Unknown",
                error=f"Invalid JSON response: {e}"
            )
        except Exception as e:
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text="Unknown",
                error=f"Unexpected error: {e}"
            )
