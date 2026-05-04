"""DeepSeek balance checker."""

import json
import urllib.error
import urllib.request

from coser.balance.base import BalanceChecker, BalanceResult, BalanceStatus


class DeepSeekChecker(BalanceChecker):
    """Balance checker for DeepSeek."""

    API_URL = "https://api.deepseek.com/user/balance"
    TIMEOUT = 10

    def __init__(
        self,
        api_key: str,
        exhausted_below: float = 0.01,
        low_below: float = 0.1,
    ):
        """Initialize the DeepSeek balance checker.

        Args:
            api_key: DeepSeek API key
            exhausted_below: Threshold for exhausted status (in currency, e.g., 0.01 CNY)
            low_below: Threshold for low status (in currency, e.g., 0.1 CNY)
        """
        super().__init__(api_key, exhausted_below, low_below)

    def check(self) -> BalanceResult:
        """Check the current DeepSeek balance.

        Returns:
            BalanceResult with CNY balance amount and formatted display
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        req = urllib.request.Request(
            self.API_URL,
            headers=headers,
            method="GET"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))

            balance_infos = data.get("balance_infos", [])
            if not balance_infos:
                return BalanceResult(
                    status=BalanceStatus.UNKNOWN,
                    raw_value=None,
                    display_text="Unknown",
                    error="No balance_infos in response"
                )

            # Find CNY balance entry
            cny_balance = None
            for info in balance_infos:
                if info.get("currency") == "CNY":
                    cny_balance = info
                    break

            if cny_balance is None:
                return BalanceResult(
                    status=BalanceStatus.UNKNOWN,
                    raw_value=None,
                    display_text="Unknown",
                    error="No CNY balance info found"
                )

            total_balance_str = cny_balance.get("total_balance", "0")
            try:
                balance = float(total_balance_str)
            except ValueError:
                return BalanceResult(
                    status=BalanceStatus.UNKNOWN,
                    raw_value=None,
                    display_text="Unknown",
                    error=f"Invalid balance value: {total_balance_str}"
                )

            # Classify status
            status = self.classify(balance)

            # Display text with CNY symbol and 2 decimal places
            display_text = f"¥{balance:.2f}"

            return BalanceResult(
                status=status,
                raw_value=balance,
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
