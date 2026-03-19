"""Interactive terminal prompts for the installer."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TypeVar

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

T = TypeVar("T")


def header(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{text}{RESET}")
    print(f"{CYAN}{'━' * 50}{RESET}")


def success(text: str) -> None:
    print(f"  {GREEN}✓{RESET} {text}")


def warn(text: str) -> None:
    print(f"  {YELLOW}!{RESET} {text}")


def error(text: str) -> None:
    print(f"  {RED}✗{RESET} {text}")


def info(text: str) -> None:
    print(f"  {DIM}{text}{RESET}")


def banner() -> None:
    print(f"""
{BOLD}{CYAN}  ╔══════════════════════════════════════╗
  ║     🦫  Beaver Installer             ║
  ║     Self-hosted RAG Platform         ║
  ╚══════════════════════════════════════╝{RESET}
""")


@dataclass
class Choice:
    name: str
    description: str
    default: bool = False


def select_one(
    title: str,
    subtitle: str,
    items: list[T],
    name_fn,
    desc_fn,
    default_fn,
) -> T:
    """Single-select prompt. Returns the selected item."""
    print(f"\n  {BOLD}{title}{RESET}")
    info(subtitle)
    print()

    default_idx = 0
    for i, item in enumerate(items):
        marker = f"{GREEN}*{RESET}" if default_fn(item) else " "
        print(f"  [{marker}] {i + 1}. {BOLD}{name_fn(item)}{RESET}")
        print(f"       {DIM}{desc_fn(item)}{RESET}")
        if default_fn(item):
            default_idx = i

    print()
    while True:
        raw = input(f"  Select (1-{len(items)}) [{default_idx + 1}]: ").strip()
        if not raw:
            return items[default_idx]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx]
        except ValueError:
            pass
        error(f"Please enter a number between 1 and {len(items)}")


def select_many(
    title: str,
    subtitle: str,
    items: list[T],
    name_fn,
    desc_fn,
    default_fn,
) -> list[T]:
    """Multi-select prompt. Returns list of selected items."""
    print(f"\n  {BOLD}{title}{RESET}")
    info(subtitle)
    print()

    defaults = []
    for i, item in enumerate(items):
        marker = f"{GREEN}*{RESET}" if default_fn(item) else " "
        print(f"  [{marker}] {i + 1}. {BOLD}{name_fn(item)}{RESET}")
        print(f"       {DIM}{desc_fn(item)}{RESET}")
        if default_fn(item):
            defaults.append(i)

    default_str = ",".join(str(d + 1) for d in defaults)
    print()
    while True:
        raw = input(f"  Select (comma-separated) [{default_str}]: ").strip()
        if not raw:
            return [items[i] for i in defaults]
        try:
            indices = [int(x.strip()) - 1 for x in raw.split(",")]
            if all(0 <= idx < len(items) for idx in indices):
                return [items[idx] for idx in indices]
        except ValueError:
            pass
        error(f"Please enter numbers between 1 and {len(items)}, comma-separated")


def ask(prompt: str, default: str = "") -> str:
    """Simple text prompt."""
    suffix = f" [{default}]" if default else ""
    val = input(f"  {prompt}{suffix}: ").strip()
    return val or default


def ask_secret(prompt: str) -> str:
    """Prompt for sensitive input (still visible, but labeled)."""
    val = input(f"  {prompt}: ").strip()
    return val


def confirm(prompt: str, default: bool = True) -> bool:
    """Yes/no confirmation."""
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"\n  {prompt} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")
