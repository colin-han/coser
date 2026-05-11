"""Profile selection module for Coser.

This module provides automatic profile selection based on WiFi SSID,
balance checking, and fallback chain logic.
"""

import sys
from dataclasses import dataclass
from typing import Optional

from coser.balance import BalanceStatus, BalanceResult, create_checker
from coser.config import GlobalConfig, Profile, load_global_config, load_profile


@dataclass
class SelectionResult:
    """Result of the automatic profile selection process.

    Attributes:
        profile_name: The selected profile name
        decision_path: Description of how the selection was made
        balance_result: The balance check result (if applicable)
        warning: Optional warning message
    """

    profile_name: str
    decision_path: str
    balance_result: Optional[BalanceResult] = None
    warning: Optional[str] = None


class SelectionError(Exception):
    """Raised when profile selection fails."""

    pass


def get_wifi_ssid() -> Optional[str]:
    """Get the current WiFi SSID on macOS.

    Tries networksetup first, then falls back to CoreWLAN via Swift.

    Returns:
        The WiFi SSID if connected, None otherwise
    """
    if sys.platform != "darwin":
        return None

    import subprocess

    # Method 1: networksetup (requires Location Services for the terminal app)
    try:
        result = subprocess.run(
            ["networksetup", "-getairportnetwork", "en0"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip()
        if "Current Wi-Fi Network:" in output:
            return output.split(":", 1)[1].strip()
    except Exception:
        pass

    # Method 2: CoreWLAN via Swift (also requires Location Services, but may
    # work for different apps)
    try:
        swift_code = '''
import CoreWLAN
if let iface = CWWiFiClient.shared().interface(), let ssid = iface.ssid() {
    print(ssid)
}
'''
        result = subprocess.run(
            ["swift", "-e", swift_code],
            capture_output=True, text=True, timeout=10
        )
        ssid = result.stdout.strip()
        if ssid:
            return ssid
    except Exception:
        pass

    return None


def get_router_ip() -> Optional[str]:
    """Get the default gateway/router IP address.

    Returns:
        Router IP address string, or None if unavailable
    """
    import subprocess

    try:
        result = subprocess.run(
            ["ipconfig", "getpacket", "en0"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "router (ip_mult):" in line:
                # Extract IP from: router (ip_mult): {192.168.31.1}
                start = line.index("{") + 1
                end = line.index("}")
                return line[start:end]
    except Exception:
        pass
    return None


def _match_network_mapping(config: GlobalConfig) -> Optional[str]:
    """Try to match current network to a profile using all available methods.

    Tries in order:
    1. WiFi SSID → config.wifi_mapping
    2. Router IP → config.router_mapping (fallback)

    Returns:
        Matched profile name, or None
    """
    # Try WiFi SSID
    ssid = get_wifi_ssid()
    if ssid and ssid in config.wifi_mapping:
        return config.wifi_mapping[ssid]

    # Fallback to router IP
    router_ip = get_router_ip()
    if router_ip and router_ip in config.router_mapping:
        return config.router_mapping[router_ip]

    return None


def check_profile_balance(profile: Profile) -> BalanceResult:
    """Check the balance status of a profile.

    If the profile has no balance configuration, returns UNKNOWN status
    (treated as sufficient for selection purposes).

    Args:
        profile: The profile to check

    Returns:
        BalanceResult with the status and details
    """
    if profile.balance is None:
        return BalanceResult(
            status=BalanceStatus.UNKNOWN,
            raw_value=None,
            display_text="Balance checking not configured",
        )

    provider = profile.balance.provider.lower()

    # Claude provider reads OAuth token from keychain, no api_key_ref required.
    api_key = ""
    if provider != "claude":
        api_key = profile.env.get(profile.balance.api_key_ref) or ""
        if not api_key:
            return BalanceResult(
                status=BalanceStatus.UNKNOWN,
                raw_value=None,
                display_text=f"API key not found: {profile.balance.api_key_ref}",
                error=f"Environment variable '{profile.balance.api_key_ref}' not set in profile",
            )

    # Create checker and perform balance check
    try:
        kwargs = {}
        if profile.balance.monitor:
            kwargs["monitor"] = profile.balance.monitor
        if provider == "claude" and profile.proxy and profile.proxy.proxy:
            kwargs["proxy"] = profile.proxy.proxy

        checker = create_checker(
            provider=profile.balance.provider,
            api_key=api_key,
            exhausted_below=profile.balance.exhausted_below,
            low_below=profile.balance.low_below,
            **kwargs,
        )
        return checker.check()
    except Exception as e:
        return BalanceResult(
            status=BalanceStatus.UNKNOWN,
            raw_value=None,
            display_text=f"Balance check failed: {str(e)}",
            error=str(e),
        )


def auto_select(dry_run: bool = False) -> SelectionResult:
    """Automatically select a profile based on WiFi and balance status.

    Decision flow:
    1. Get WiFi SSID and match against wifi_mapping
    2. If WiFi matched: check balance and return if sufficient
    3. If no WiFi match or balance exhausted: try fallback_chain
    4. If all fallbacks exhausted: use default_profile with warning
    5. If no default: raise SelectionError

    Args:
        dry_run: If True, don't prompt for user confirmation on low balance

    Returns:
        SelectionResult with the selected profile and decision details

    Raises:
        SelectionError: If no profile can be selected
    """
    config = load_global_config()

    # Step 1: Try network-based selection (SSID or router IP)
    matched_profile = _match_network_mapping(config)
    if matched_profile:
        profile_name = matched_profile
        try:
            profile = load_profile(profile_name)
            balance_result = check_profile_balance(profile)

            # Build decision path with detection method info
            ssid = get_wifi_ssid()
            if ssid:
                decision_path = f"WiFi SSID '{ssid}' matched to profile '{profile_name}'"
            else:
                router_ip = get_router_ip()
                decision_path = f"Router IP '{router_ip}' matched to profile '{profile_name}'"

            if balance_result.status == BalanceStatus.SUFFICIENT:
                return SelectionResult(
                    profile_name=profile_name,
                    decision_path=decision_path,
                    balance_result=balance_result,
                )
            elif balance_result.status == BalanceStatus.LOW:
                if dry_run:
                    return SelectionResult(
                        profile_name=profile_name,
                        decision_path=f"{decision_path} (balance low)",
                        balance_result=balance_result,
                        warning=f"Profile '{profile_name}' balance is low: {balance_result.display_text}",
                    )
                else:
                    # Prompt user for confirmation
                    response = input(
                        f"Profile '{profile_name}' balance is low ({balance_result.display_text}). Continue? [y/N]: "
                    )
                    if response.lower() == "y":
                        return SelectionResult(
                            profile_name=profile_name,
                            decision_path=f"{decision_path} (user confirmed despite low balance)",
                            balance_result=balance_result,
                        )
                    else:
                        print(f"User declined low balance profile '{profile_name}', trying fallback...")
            elif balance_result.status == BalanceStatus.EXHAUSTED:
                print(
                    f"[Warning] Profile '{profile_name}' from WiFi match is exhausted: {balance_result.display_text}",
                    file=sys.stderr,
                )
            else:  # UNKNOWN
                # Treat as sufficient
                return SelectionResult(
                    profile_name=profile_name,
                    decision_path=decision_path,
                    balance_result=balance_result,
                    warning=f"Balance check returned unknown status: {balance_result.display_text}",
                )
        except FileNotFoundError:
            # Profile in wifi_mapping doesn't exist, skip to fallback
            pass

    # Step 2: Try fallback chain
    for profile_name in config.fallback_chain:
        try:
            profile = load_profile(profile_name)
            balance_result = check_profile_balance(profile)

            decision_path = f"Fallback chain matched to profile '{profile_name}'"

            if balance_result.status == BalanceStatus.SUFFICIENT:
                return SelectionResult(
                    profile_name=profile_name,
                    decision_path=decision_path,
                    balance_result=balance_result,
                )
            elif balance_result.status == BalanceStatus.LOW:
                if dry_run:
                    return SelectionResult(
                        profile_name=profile_name,
                        decision_path=f"{decision_path} (balance low)",
                        balance_result=balance_result,
                        warning=f"Profile '{profile_name}' balance is low: {balance_result.display_text}",
                    )
                else:
                    response = input(
                        f"Profile '{profile_name}' balance is low ({balance_result.display_text}). Continue? [y/N]: "
                    )
                    if response.lower() == "y":
                        return SelectionResult(
                            profile_name=profile_name,
                            decision_path=f"{decision_path} (user confirmed despite low balance)",
                            balance_result=balance_result,
                        )
                    else:
                        print(f"User declined low balance profile '{profile_name}', trying next...")
            elif balance_result.status == BalanceStatus.EXHAUSTED:
                print(
                    f"[Warning] Profile '{profile_name}' in fallback chain is exhausted: {balance_result.display_text}",
                    file=sys.stderr,
                )
            else:  # UNKNOWN
                # Treat as sufficient
                return SelectionResult(
                    profile_name=profile_name,
                    decision_path=decision_path,
                    balance_result=balance_result,
                    warning=f"Balance check returned unknown status: {balance_result.display_text}",
                )
        except FileNotFoundError:
            # Profile in fallback_chain doesn't exist, try next
            continue

    # Step 3: Fall back to default_profile
    if config.default_profile:
        try:
            profile = load_profile(config.default_profile)
            balance_result = check_profile_balance(profile)

            return SelectionResult(
                profile_name=config.default_profile,
                decision_path=f"Using default profile '{config.default_profile}'",
                balance_result=balance_result,
                warning="All fallback profiles exhausted, using default",
            )
        except FileNotFoundError:
            raise SelectionError(
                f"Default profile '{config.default_profile}' not found"
            )

    raise SelectionError("No profile could be selected - no matching WiFi, fallback chain exhausted, and no default profile configured")
