"""Interface to the GitHub Copilot CLI (``gh copilot suggest``).

Uses ``pexpect`` to drive the interactive CLI non-interactively:
 1. Spawn ``gh copilot suggest --target <target> <prompt>``
 2. Wait for the "Suggestion:" header in the output.
 3. Capture everything up to the "Select an option" prompt.
 4. Strip ANSI escape codes and blank / decorative lines to get the bare command.
 5. Exit the interactive menu cleanly.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import pexpect

import config

logger = logging.getLogger(__name__)

# Matches all ANSI / VT-100 escape sequences.
_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _extract_command(raw: str) -> str:
    """Return the command text from the raw block between 'Suggestion:' and the menu."""
    clean = _strip_ansi(raw)
    lines: list[str] = []
    for line in clean.splitlines():
        stripped = line.strip()
        # Skip empty lines and UI decoration lines (?, >, arrows, spinner chars).
        if not stripped:
            continue
        if stripped.startswith(("?", ">", "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def _suggest_sync(prompt: str, target: str) -> Optional[str]:
    """Blocking helper — runs in a thread-pool executor."""
    # Use a list to avoid any shell-injection risk; pexpect accepts lists directly.
    cmd = ["gh", "copilot", "suggest", "--target", target, prompt]
    logger.info("Spawning: %s", cmd)

    child = None
    try:
        child = pexpect.spawn(cmd[0], args=cmd[1:], timeout=config.COPILOT_TIMEOUT, encoding="utf-8")

        # gh copilot prints its suggestion after this header.
        idx = child.expect(
            ["Suggestion:", "Sorry", "error", pexpect.TIMEOUT, pexpect.EOF],
            timeout=config.COPILOT_TIMEOUT,
        )

        if idx != 0:
            logger.warning("No suggestion produced (expect index=%d)", idx)
            child.close(force=True)
            return None

        # Consume everything up to the interactive selection menu.
        child.expect(
            [r"Select an option", pexpect.TIMEOUT, pexpect.EOF],
            timeout=10,
        )
        raw_suggestion = child.before or ""

        # Navigate the menu to "Exit" (5th item) — Down ×4 then Enter.
        try:
            child.send("\x1b[B\x1b[B\x1b[B\x1b[B\r")
            child.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=5)
        except Exception:
            pass
        finally:
            child.close(force=True)

        suggestion = _extract_command(raw_suggestion)
        logger.info("Extracted suggestion: %s", suggestion[:120])
        return suggestion or None

    except Exception as exc:
        logger.error("Copilot error: %s", exc, exc_info=True)
        if child is not None:
            try:
                child.close(force=True)
            except Exception:
                pass
        return None


async def get_suggestion(prompt: str, target: str = "shell") -> Optional[str]:
    """Async wrapper around ``_suggest_sync``."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _suggest_sync, prompt, target)
