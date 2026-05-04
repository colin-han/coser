"""
Daily activation (say-hi) functionality with cron management.
"""

import os
import shutil
import subprocess
from typing import List

from coser.config import load_global_config, list_profiles, load_profile


CRON_MARKER = "# coser-say-hi"


def send_notification(title: str, message: str) -> None:
    """
    Send a macOS desktop notification.

    Args:
        title: Notification title
        message: Notification message body
    """
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], timeout=5)


def run_say_hi() -> None:
    """
    Run the say-hi activation for all enabled profiles.

    Loads global config, finds profiles with say_hi_enabled=True,
    and runs 'claude -p hi --max-turns 1' for each with their env.
    Sends notification on failure only.
    """
    config = load_global_config()
    profile_names = list_profiles()

    # Filter enabled profiles
    enabled_profiles = []
    for name in profile_names:
        profile = load_profile(name)
        if profile.say_hi_enabled:
            enabled_profiles.append(profile)

    if not enabled_profiles:
        print("No profiles with say-hi enabled.")
        return

    # Create workdir
    workdir = os.path.expanduser(config.say_hi_workdir)
    os.makedirs(workdir, exist_ok=True)

    # Run say-hi for each profile
    failed = []
    for profile in enabled_profiles:
        # Build env dict (copy to avoid polluting current process)
        env_dict = os.environ.copy()
        env_dict.update(profile.env)

        # Expand proxy config
        if profile.proxy and profile.proxy.proxy:
            env_dict["HTTP_PROXY"] = profile.proxy.proxy
            env_dict["HTTPS_PROXY"] = profile.proxy.proxy
            env_dict["http_proxy"] = profile.proxy.proxy
            env_dict["https_proxy"] = profile.proxy.proxy
            if profile.proxy.no_proxy:
                env_dict["NO_PROXY"] = profile.proxy.no_proxy
                env_dict["no_proxy"] = profile.proxy.no_proxy

        print(f"[{profile.name}] sending hi...")
        try:
            result = subprocess.run(
                ["claude", "-p", "hi", "--max-turns", "1"],
                cwd=workdir,
                env=env_dict,
                timeout=60,
                capture_output=True,
                text=True,
            )
            response = result.stdout.strip()
            if response:
                print(f"[{profile.name}] response: {response}")
            else:
                print(f"[{profile.name}] response: (empty)")

            if result.returncode != 0:
                stderr = result.stderr.strip()
                error_detail = f" (stderr: {stderr})" if stderr else ""
                print(f"[{profile.name}] FAILED (exit code {result.returncode}){error_detail}")
                failed.append(profile.name)
            else:
                print(f"[{profile.name}] OK")
        except subprocess.TimeoutExpired:
            print(f"[{profile.name}] TIMEOUT")
            failed.append(f"{profile.name} (timeout)")
        except Exception as e:
            print(f"[{profile.name}] ERROR: {str(e)}")
            failed.append(f"{profile.name} ({str(e)})")
        print()

    # Print summary
    total = len(enabled_profiles)
    success = total - len(failed)
    print(f"Say-hi complete: {success}/{total} succeeded")

    if failed:
        failed_list = ", ".join(failed)
        send_notification("Coser", f"Say-hi 失败: {failed_list}")


def install_cron() -> None:
    """
    Install cron job for daily say-hi activation.

    Reads current crontab, checks for existing entry, and appends
    if not present. Runs daily at 8:00 AM.
    """
    coser_path = shutil.which("coser")
    if not coser_path:
        print("Error: Could not find 'coser' in PATH")
        return

    # Get current crontab
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current_cron = result.stdout if result.returncode == 0 else ""

    # Check if already installed
    if CRON_MARKER in current_cron:
        print("Cron job already installed.")
        return

    # Build new cron entry
    cron_line = f"0 8 * * * {coser_path} --say-hi  {CRON_MARKER}\n"
    new_cron = current_cron.rstrip("\n") + "\n" + cron_line if current_cron else cron_line

    # Write back
    subprocess.run(
        ["crontab", "-"],
        input=new_cron.encode(),
        capture_output=True,
    )

    print(f"Cron job installed: daily at 8:00 AM")
    print(f"Command: {coser_path} --say-hi")


def uninstall_cron() -> None:
    """
    Uninstall the say-hi cron job.

    Reads current crontab and removes lines containing the marker.
    """
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)

    if result.returncode != 0:
        print("No crontab found.")
        return

    current_cron = result.stdout

    if CRON_MARKER not in current_cron:
        print("Cron job not found.")
        return

    # Filter out lines with marker
    new_lines = [
        line for line in current_cron.splitlines()
        if CRON_MARKER not in line
    ]
    new_cron = "\n".join(new_lines) + "\n" if new_lines else ""

    # Write back
    subprocess.run(
        ["crontab", "-"],
        input=new_cron.encode(),
        capture_output=True,
    )

    print("Cron job uninstalled.")
