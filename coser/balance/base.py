"""Balance checking base classes and factory."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BalanceStatus(Enum):
    """Balance status classification."""
    SUFFICIENT = "sufficient"
    LOW = "low"
    EXHAUSTED = "exhausted"
    UNKNOWN = "unknown"


@dataclass
class BalanceResult:
    """Result of a balance check operation."""
    status: BalanceStatus
    raw_value: Optional[float]
    display_text: str
    error: Optional[str] = None


class BalanceChecker:
    """Base class for balance checking implementations.

    Subclasses must implement the check() method to query the appropriate API.
    """

    def __init__(
        self,
        api_key: str,
        exhausted_below: float = 0.01,
        low_below: float = 0.1
    ):
        """Initialize the balance checker.

        Args:
            api_key: API key for authentication
            exhausted_below: Threshold below which balance is considered exhausted (inclusive)
            low_below: Threshold below which balance is considered low (inclusive)
        """
        self.api_key = api_key
        self.exhausted_below = exhausted_below
        self.low_below = low_below

    def check(self) -> BalanceResult:
        """Check the current balance.

        Subclasses must implement this method to query the appropriate API.

        Returns:
            BalanceResult with status, raw value, display text, and optional error
        """
        raise NotImplementedError("Subclasses must implement check()")

    def classify(self, value: float) -> BalanceStatus:
        """Classify a balance value into a status category.

        Args:
            value: Numeric balance value (typically 0-1 for percentages, or absolute amounts)

        Returns:
            BalanceStatus classification
        """
        if value <= self.exhausted_below:
            return BalanceStatus.EXHAUSTED
        elif value <= self.low_below:
            return BalanceStatus.LOW
        else:
            return BalanceStatus.SUFFICIENT


def create_checker(
    provider: str,
    api_key: str,
    exhausted_below: float = 0.01,
    low_below: float = 0.1,
    **kwargs
) -> BalanceChecker:
    """Factory function to create a BalanceChecker for the specified provider.

    Args:
        provider: Provider name ('zhipu' or 'deepseek')
        api_key: API key for authentication
        exhausted_below: Threshold for exhausted status
        low_below: Threshold for low status
        **kwargs: Additional provider-specific arguments (e.g., monitor config for zhipu)

    Returns:
        BalanceChecker instance for the specified provider

    Raises:
        ValueError: If provider is not supported
    """
    provider_lower = provider.lower()

    if provider_lower == "zhipu":
        from coser.balance.zhipu import ZhipuChecker
        return ZhipuChecker(
            api_key=api_key,
            exhausted_below=exhausted_below,
            low_below=low_below,
            **kwargs
        )
    elif provider_lower == "deepseek":
        from coser.balance.deepseek import DeepSeekChecker
        return DeepSeekChecker(
            api_key=api_key,
            exhausted_below=exhausted_below,
            low_below=low_below,
            **kwargs
        )
    elif provider_lower == "claude":
        from coser.balance.claude import ClaudeChecker
        return ClaudeChecker(
            api_key=api_key,
            exhausted_below=exhausted_below,
            low_below=low_below,
            **kwargs
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported: 'zhipu', 'deepseek', 'claude'")
