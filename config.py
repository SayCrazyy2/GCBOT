"""Configuration loaded from environment variables (or a .env file)."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Required ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.environ.get("TELEGRAM_TOKEN", "")

# ── Optional ──────────────────────────────────────────────────────────────────
# Comma-separated Telegram user IDs that are allowed to use the bot.
# Leave empty to allow everyone (NOT recommended for public bots).
_raw_users = os.environ.get("ALLOWED_USERS", "")
ALLOWED_USERS: set[str] = set(filter(None, _raw_users.split(",")))

# Root workspace directory — the AI has full read/write/delete access here.
# All file-management commands (ls, cat, rm, mkdir, cd, upload, download) are
# confined to this directory to prevent accidental access outside it.
WORKSPACE_DIR: str = os.environ.get(
    "WORKSPACE_DIR", os.path.join(os.path.expanduser("~"), "gcbot-workspace")
)

# Directory used as the working directory for executed commands.
# When a user runs /cd inside the workspace this is updated per-session.
WORK_DIR: str = os.environ.get("WORK_DIR", WORKSPACE_DIR)

# Maximum characters returned to Telegram for a single command output.
MAX_OUTPUT_LENGTH: int = int(os.environ.get("MAX_OUTPUT_LENGTH", "3500"))

# Maximum file size (bytes) that /download will send via Telegram (default 20 MB).
MAX_DOWNLOAD_SIZE: int = int(os.environ.get("MAX_DOWNLOAD_SIZE", str(20 * 1024 * 1024)))

# Seconds before a shell command is forcefully killed.
COMMAND_TIMEOUT: int = int(os.environ.get("COMMAND_TIMEOUT", "120"))

# Seconds to wait for gh copilot to produce a suggestion.
COPILOT_TIMEOUT: int = int(os.environ.get("COPILOT_TIMEOUT", "60"))
