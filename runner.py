"""Safe shell-command execution with timeout and output capping.

Security note
-------------
Commands are executed with ``shell=True`` because GitHub Copilot CLI returns
complete shell command strings (including pipes, redirects, and substitutions)
that cannot be split into an argv list without the shell.  Access is restricted
to users listed in ``config.ALLOWED_USERS``; the caller (bot.py) enforces this
before reaching this module.  Do NOT expose this module to untrusted input.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Tuple

import config

logger = logging.getLogger(__name__)


def _run_sync(command: str) -> Tuple[str, int]:
    """Run *command* in a shell and return (output, returncode).

    stdout and stderr are merged; output is capped at ``config.MAX_OUTPUT_LENGTH``.
    """
    if not command or not command.strip():
        return "❌ Empty command.", 1

    try:
        result = subprocess.run(
            command,
            shell=True,  # noqa: S602 — intentional; see module docstring
            capture_output=True,
            text=True,
            timeout=config.COMMAND_TIMEOUT,
            cwd=config.WORK_DIR,
        )
        output = (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return f"⏰ Command timed out after {config.COMMAND_TIMEOUT}s.", 124
    except Exception as exc:
        return f"❌ Execution error: {exc}", 1

    if not output:
        output = "(no output)"

    if len(output) > config.MAX_OUTPUT_LENGTH:
        output = output[: config.MAX_OUTPUT_LENGTH] + "\n… (output truncated)"

    return output, result.returncode


async def execute_command(command: str) -> Tuple[str, int]:
    """Async wrapper around ``_run_sync``."""
    logger.info("Executing: %s", command[:200])
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_sync, command)
