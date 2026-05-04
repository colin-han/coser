"""
TUI interactive selection for profile selection.
Uses curses for terminal-based UI with balance status display.
"""

import curses
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Dict, List, Optional

from coser.config import Profile
from coser.balance import BalanceResult, BalanceStatus
from coser.selector import check_profile_balance


class BalanceChecker:
    """Manages background balance checking for profiles."""

    def __init__(self, profiles: List[Profile], timeout: float = 5.0):
        self.profiles = profiles
        self.timeout = timeout
        self.results: Dict[str, BalanceResult] = {}
        self.pending: set = set()
        self.timed_out: set = set()
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=10)

    def start(self):
        """Start balance checking in background threads."""
        for profile in self.profiles:
            if profile.balance is not None:
                with self.lock:
                    self.pending.add(profile.name)
                future = self.executor.submit(self._check_with_timeout, profile)
                future.add_done_callback(lambda f, p=profile.name: self._on_complete(p, f))

    def _check_with_timeout(self, profile: Profile) -> Optional[BalanceResult]:
        """Check balance with timeout."""
        try:
            return check_profile_balance(profile)
        except Exception:
            return None

    def _on_complete(self, profile_name: str, future):
        """Handle balance check completion."""
        try:
            result = future.result(timeout=self.timeout)
            with self.lock:
                self.pending.discard(profile_name)
                if result is not None:
                    self.results[profile_name] = result
                else:
                    self.timed_out.add(profile_name)
        except FutureTimeoutError:
            with self.lock:
                self.pending.discard(profile_name)
                self.timed_out.add(profile_name)
        except Exception:
            with self.lock:
                self.pending.discard(profile_name)
                self.timed_out.add(profile_name)

    def get_status(self, profile: Profile) -> tuple:
        """Get display string and color hint for profile balance status.

        Returns:
            (display_text, is_warning) tuple
        """
        with self.lock:
            if profile.balance is None:
                return ("(不支持查询)", False)
            if profile.name in self.pending:
                return ("查询中...", False)
            if profile.name in self.timed_out:
                return ("查询超时", True)
            if profile.name not in self.results:
                return ("查询中...", False)

            result = self.results[profile.name]
            if result.status == BalanceStatus.SUFFICIENT:
                return (f"余额: {result.display_text}", False)
            elif result.status == BalanceStatus.LOW:
                return (f"余额: {result.display_text} (不足)", True)
            elif result.status == BalanceStatus.EXHAUSTED:
                return ("余额: 已耗尽", True)
            else:  # UNKNOWN
                return (result.display_text, False)

    def shutdown(self):
        """Shutdown the executor."""
        self.executor.shutdown(wait=False)


def interactive_select(profiles: List[Profile]) -> Optional[str]:
    """
    Interactive curses TUI for profile selection.

    Args:
        profiles: List of Profile objects to choose from

    Returns:
        Selected profile name, or None if cancelled
    """
    if not profiles:
        return None

    selected_index = 0

    def main(stdscr):
        nonlocal selected_index

        # Setup curses
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(False)

        # Colors
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Selected

        # Start balance checker
        checker = BalanceChecker(profiles)
        checker.start()

        try:
            while True:
                stdscr.clear()
                height, width = stdscr.getmaxyx()

                # Title
                title = "选择配置文件"
                stdscr.addstr(1, (width - len(title.encode('utf-8'))) // 2, title)

                # Profiles list
                max_name_len = max(len(p.name) for p in profiles) if profiles else 10

                for i, profile in enumerate(profiles):
                    row = i + 3
                    if row >= height - 3:
                        break

                    prefix = "> " if i == selected_index else "  "
                    name_display = f"{profile.name:<{max_name_len}}"

                    if i == selected_index:
                        stdscr.addstr(row, 2, prefix, curses.color_pair(5))
                        stdscr.addstr(row, 4, name_display, curses.color_pair(5))
                    else:
                        stdscr.addstr(row, 2, prefix)
                        stdscr.addstr(row, 4, name_display)

                    # Balance status
                    status_text, is_warning = checker.get_status(profile)
                    status_col = 4 + max_name_len + 2

                    if i == selected_index:
                        stdscr.addstr(row, status_col, status_text, curses.color_pair(5))
                    elif is_warning:
                        stdscr.addstr(row, status_col, status_text, curses.color_pair(3))
                    else:
                        stdscr.addstr(row, status_col, status_text, curses.color_pair(4))

                # Footer
                footer = "[↑/↓] 切换  [Enter] 确认  [q] 取消"
                footer_y = height - 2
                stdscr.addstr(footer_y, (width - len(footer.encode('utf-8'))) // 2, footer)

                stdscr.refresh()

                # Input handling
                stdscr.timeout(200)  # 200ms refresh
                key = stdscr.getch()

                if key == curses.KEY_UP:
                    selected_index = (selected_index - 1) % len(profiles)
                elif key == curses.KEY_DOWN:
                    selected_index = (selected_index + 1) % len(profiles)
                elif key == ord('q') or key == ord('Q'):
                    return None
                elif key == ord('\n') or key == curses.KEY_ENTER:
                    return profiles[selected_index].name

        finally:
            checker.shutdown()

    return curses.wrapper(main)
