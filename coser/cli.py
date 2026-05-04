"""CLI entry point for Coser."""

import argparse
import os
import sys

from coser.config import GlobalConfig, Profile, load_global_config, load_profile, list_profiles
from coser.selector import auto_select, check_profile_balance, SelectionError
from coser.balance import BalanceStatus
from coser.tui.select import interactive_select
from coser.say_hi import run_say_hi, install_cron, uninstall_cron


def parse_args(argv):
    """Parse coser-specific flags, separating them from claude passthrough args."""
    parser = argparse.ArgumentParser(
        prog="coser",
        description="Claude Code account switching CLI",
        add_help=False,
    )
    parser.add_argument("--profile", type=str, default=None)
    parser.add_argument("--select", action="store_true")
    parser.add_argument("--list", action="store_true", dest="list_profiles")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--say-hi", action="store_true")
    parser.add_argument("--install-cron", action="store_true")
    parser.add_argument("--uninstall-cron", action="store_true")

    coser_args, passthrough = parser.parse_known_args(argv)
    return coser_args, passthrough


def mask_token(token):
    """Mask a token for display, showing first 6 and last 4 chars."""
    if not token or len(token) <= 10:
        return token or "(默认)"
    return token[:6] + "*" * (len(token) - 10) + token[-4:]


def print_config_info(profile, config, decision_path=""):
    """Print formatted configuration info before launching claude."""
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Claude API 配置 [环境: {profile.name}]")
    if decision_path:
        print(f"  决策路径: {decision_path}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    base_url = profile.env.get("ANTHROPIC_BASE_URL", "")
    print(f"  Base URL:  {base_url or '(默认)'}")

    token = profile.env.get("ANTHROPIC_AUTH_TOKEN", "")
    print(f"  Auth Token: {mask_token(token)}")

    if config.enable_agent_teams:
        print("  Agent Teams: 已启用")

    haiku = profile.env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL")
    if haiku:
        print(f"  Haiku  -> {haiku}")
        print(f"  Sonnet -> {profile.env.get('ANTHROPIC_DEFAULT_SONNET_MODEL', '(默认)')}")
        print(f"  Opus   -> {profile.env.get('ANTHROPIC_DEFAULT_OPUS_MODEL', '(默认)')}")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()


def launch_claude(profile, extra_args, enable_agent_teams=False):
    """Set environment variables and exec claude code."""
    for key, value in profile.env.items():
        os.environ[key] = value

    if enable_agent_teams:
        os.environ["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] = "1"

    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        # Fallback: try PATH
        import shutil
        claude_in_path = shutil.which("claude")
        if claude_in_path:
            claude_path = claude_in_path
        else:
            print("Error: 'claude' binary not found.", file=sys.stderr)
            print("Expected at ~/.local/bin/claude or in PATH.", file=sys.stderr)
            sys.exit(1)

    os.execvp(claude_path, ["claude"] + extra_args)


STATUS_LABELS = {
    BalanceStatus.SUFFICIENT: "充足",
    BalanceStatus.LOW: "不足",
    BalanceStatus.EXHAUSTED: "用完",
    BalanceStatus.UNKNOWN: "查询失败",
}


def cmd_list():
    """List all profiles with balance status."""
    config = load_global_config()
    profile_names = list_profiles()

    if not profile_names:
        print("No profiles found in ~/.coser/profiles/")
        return

    print(f"{'Profile':<16} {'Balance':<12} {'Details'}")
    print("-" * 50)

    for name in profile_names:
        profile = load_profile(name)
        if profile.balance:
            result = check_profile_balance(profile)
            status_label = STATUS_LABELS.get(result.status, "未知")
            print(f"{name:<16} {status_label:<12} {result.display_text}")
        else:
            print(f"{name:<16} {'不支持查询':<12}")


def main():
    """Main entry point."""
    coser_args, passthrough = parse_args(sys.argv[1:])
    config = load_global_config()

    # --list: show all profiles with balance
    if coser_args.list_profiles:
        cmd_list()
        return

    # --select: interactive TUI
    if coser_args.select:
        profile_names = list_profiles()
        if not profile_names:
            print("No profiles found in ~/.coser/profiles/", file=sys.stderr)
            sys.exit(1)
        profiles = [load_profile(n) for n in profile_names]
        selected = interactive_select(profiles)
        if selected is None:
            print("已取消。")
            return
        profile = load_profile(selected)
        print_config_info(profile, config)
        launch_claude(profile, passthrough, config.enable_agent_teams)
        return

    # --say-hi: daily activation
    if coser_args.say_hi:
        run_say_hi()
        return

    # --install-cron / --uninstall-cron
    if coser_args.install_cron:
        install_cron()
        return
    if coser_args.uninstall_cron:
        uninstall_cron()
        return

    # --profile: manual selection, skip balance check
    if coser_args.profile:
        try:
            profile = load_profile(coser_args.profile)
        except FileNotFoundError:
            print(f"Error: Profile '{coser_args.profile}' not found.", file=sys.stderr)
            available = list_profiles()
            if available:
                print(f"Available: {', '.join(available)}", file=sys.stderr)
            sys.exit(1)
        if coser_args.dry_run:
            print(f"决策路径: 手动指定 profile '{coser_args.profile}'")
            print(f"决策结果: 使用 profile {coser_args.profile}")
            print()
            print("(预演模式，未启动 claude code)")
            return
        print_config_info(profile, config)
        launch_claude(profile, passthrough, config.enable_agent_teams)
        return

    # Auto mode or dry-run
    try:
        result = auto_select(dry_run=coser_args.dry_run)
    except SelectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    profile = load_profile(result.profile_name)

    if coser_args.dry_run:
        from coser.selector import get_wifi_ssid, get_router_ip
        wifi_ssid = get_wifi_ssid()
        router_ip = get_router_ip()
        print(f"当前 WiFi: {wifi_ssid or '(未检测到)'}")
        print(f"当前路由器: {router_ip or '(未检测到)'}")
        print(f"决策路径: {result.decision_path}")
        if result.balance_result:
            status_label = STATUS_LABELS.get(result.balance_result.status, "未知")
            print(f"余额状态: {status_label} ({result.balance_result.display_text})")
        if result.warning:
            print(f"警告: {result.warning}")
        print(f"决策结果: 使用 profile {result.profile_name}")
        print()
        print("(预演模式，未启动 claude code)")
        return

    # Auto mode: launch claude
    print_config_info(profile, config, result.decision_path)
    launch_claude(profile, passthrough, config.enable_agent_teams)
