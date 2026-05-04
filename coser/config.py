"""Configuration loading module for Coser.

This module provides data models and functions for loading configuration
from TOML files in ~/.coser/ directory.
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class BalanceConfig:
    """Balance checking configuration for a profile.

    Attributes:
        provider: The provider name (e.g., 'zhipu', 'deepseek')
        api_key_ref: Reference to the environment variable containing the API key
        monitor: Optional monitor configuration dict (e.g., {'type': 'TOKENS_LIMIT', 'unit': 'monthly'})
        exhausted_below: Threshold below which balance is considered exhausted
        low_below: Threshold below which balance is considered low
    """

    provider: str
    api_key_ref: str
    monitor: Optional[Dict] = None
    exhausted_below: float = 0.01
    low_below: float = 0.10


@dataclass
class Profile:
    """A profile configuration containing environment variables and balance settings.

    Attributes:
        name: Profile name (derived from filename)
        env: Dictionary of environment variables
        balance: Optional balance checking configuration
        say_hi_enabled: Whether say_hi is enabled for this profile
    """

    name: str
    env: Dict[str, str] = field(default_factory=dict)
    balance: Optional[BalanceConfig] = None
    say_hi_enabled: bool = False


@dataclass
class GlobalConfig:
    """Global configuration for Coser.

    Attributes:
        default_profile: The default profile to use when no rules match
        enable_agent_teams: Whether to enable agent teams feature
        wifi_mapping: Dictionary mapping WiFi SSIDs to profile names
        fallback_chain: Ordered list of profile names to try as fallback
        say_hi_workdir: Working directory for say_hi feature
    """

    default_profile: str = ""
    enable_agent_teams: bool = False
    wifi_mapping: Dict[str, str] = field(default_factory=dict)
    router_mapping: Dict[str, str] = field(default_factory=dict)
    fallback_chain: List[str] = field(default_factory=list)
    say_hi_workdir: str = "~/.coser/say-hi-workspace"


def _get_coser_dir() -> str:
    """Get the Coser configuration directory path."""
    return os.path.expanduser("~/.coser/")


def _get_config_path() -> str:
    """Get the path to the global config file."""
    return os.path.join(_get_coser_dir(), "config.toml")


def _get_profiles_dir() -> str:
    """Get the path to the profiles directory."""
    return os.path.join(_get_coser_dir(), "profiles/")


def load_global_config() -> GlobalConfig:
    """Load global configuration from ~/.coser/config.toml.

    Returns a GlobalConfig with default values if the file doesn't exist.

    Returns:
        GlobalConfig: The global configuration
    """
    config_path = _get_config_path()

    if not os.path.exists(config_path):
        return GlobalConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    wifi_mapping = dict(data.get("wifi_mapping", {}))
    router_mapping = dict(data.get("router_mapping", {}))

    fallback_chain_data = data.get("fallback_chain", {})
    if isinstance(fallback_chain_data, dict):
        fallback_chain = fallback_chain_data.get("profiles", [])
    elif isinstance(fallback_chain_data, list):
        fallback_chain = fallback_chain_data
    else:
        fallback_chain = []

    say_hi_data = data.get("say_hi", {})
    if isinstance(say_hi_data, dict):
        say_hi_workdir = say_hi_data.get("workdir", "~/.coser/say-hi-workspace")
    else:
        say_hi_workdir = "~/.coser/say-hi-workspace"

    return GlobalConfig(
        default_profile=data.get("default_profile", ""),
        enable_agent_teams=data.get("enable_agent_teams", False),
        wifi_mapping=wifi_mapping,
        router_mapping=router_mapping,
        fallback_chain=fallback_chain,
        say_hi_workdir=say_hi_workdir,
    )


def load_profile(name: str) -> Profile:
    """Load a profile from ~/.coser/profiles/{name}.toml.

    Args:
        name: The profile name (without .toml extension)

    Returns:
        Profile: The loaded profile

    Raises:
        FileNotFoundError: If the profile file doesn't exist
    """
    profiles_dir = _get_profiles_dir()
    profile_path = os.path.join(profiles_dir, f"{name}.toml")

    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"Profile not found: {name}")

    with open(profile_path, "rb") as f:
        data = tomllib.load(f)

    env_data = data.get("env", {})
    env = dict(env_data) if env_data else {}

    balance = None
    if "balance" in data:
        balance_data = data["balance"]
        balance = BalanceConfig(
            provider=balance_data.get("provider", ""),
            api_key_ref=balance_data.get("api_key_ref", ""),
            monitor=balance_data.get("monitor"),
            exhausted_below=balance_data.get("exhausted_below", 0.01),
            low_below=balance_data.get("low_below", 0.10),
        )

    say_hi_enabled = False
    if "say_hi" in data:
        say_hi_data = data["say_hi"]
        if isinstance(say_hi_data, dict):
            say_hi_enabled = say_hi_data.get("enabled", False)
        else:
            say_hi_enabled = bool(say_hi_data)

    return Profile(name=name, env=env, balance=balance, say_hi_enabled=say_hi_enabled)


def list_profiles() -> List[str]:
    """List all available profiles in ~/.coser/profiles/.

    Returns:
        List[str]: List of profile names (without .toml extension)
    """
    profiles_dir = _get_profiles_dir()

    if not os.path.exists(profiles_dir):
        return []

    profiles = []
    for filename in os.listdir(profiles_dir):
        if filename.endswith(".toml"):
            profiles.append(filename[:-5])

    return sorted(profiles)
