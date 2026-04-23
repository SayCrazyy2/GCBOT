"""GCBOT — GitHub Copilot CLI in Telegram.

Receive a task from Telegram → forward to ``gh copilot suggest`` →
optionally execute the suggested command → return the result.
"""

from __future__ import annotations

import logging
import textwrap
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from copilot import get_suggestion
from runner import execute_command

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── helpers ───────────────────────────────────────────────────────────────────

HELP_TEXT = textwrap.dedent(
    """
    🤖 *GCBOT* — GitHub Copilot CLI in Telegram

    Send any natural-language task and I'll ask GitHub Copilot CLI for a command suggestion.

    *Commands*
    `/suggest <task>` — Get a shell command suggestion (no execution)
    `/run <task>`     — Suggest *and* execute the command
    `/git <task>`     — Suggest a git command (no execution)
    `/gh <task>`      — Suggest a gh CLI command (no execution)
    `/help`           — Show this message

    *Sending a plain message* gives you a suggestion with an inline *▶ Run* button.
    """
).strip()


def _is_authorized(user_id: int) -> bool:
    if not config.ALLOWED_USERS:
        return True
    return str(user_id) in config.ALLOWED_USERS


def _md_code(text: str) -> str:
    """Wrap *text* in a Markdown v2 code block (escapes back-ticks)."""
    escaped = text.replace("`", "\\`")
    return f"```\n{escaped}\n```"


def _suggestion_text(suggestion: str) -> str:
    return f"💡 *Copilot Suggestion*\n{_md_code(suggestion)}"


def _store_suggestion(context: ContextTypes.DEFAULT_TYPE, suggestion: str) -> str:
    """Store suggestion in user_data and return a short lookup key."""
    key = uuid.uuid4().hex[:12]
    if context.user_data is None:
        return key
    context.user_data.setdefault("suggestions", {})[key] = suggestion
    return key


def _load_suggestion(context: ContextTypes.DEFAULT_TYPE, key: str) -> str | None:
    if context.user_data is None:
        return None
    return context.user_data.get("suggestions", {}).get(key)


def _run_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("▶ Run", callback_data=f"run:{key}"),
                InlineKeyboardButton("✖ Cancel", callback_data="cancel"),
            ]
        ]
    )


# ── core flow ─────────────────────────────────────────────────────────────────

async def _handle_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    task: str,
    target: str = "shell",
    auto_run: bool = False,
) -> None:
    assert update.message is not None

    status = await update.message.reply_text("⏳ Asking Copilot…")

    suggestion = await get_suggestion(task, target=target)

    if not suggestion:
        await status.edit_text("❌ Copilot returned no suggestion. Is `gh copilot` installed?")
        return

    text = _suggestion_text(suggestion)

    if auto_run:
        await status.edit_text(text + "\n\n⚙️ Running…", parse_mode=ParseMode.MARKDOWN)
        output, rc = await execute_command(suggestion)
        rc_emoji = "✅" if rc == 0 else "⚠️"
        result_text = f"{text}\n\n{rc_emoji} *Output* (exit {rc})\n{_md_code(output)}"
        await status.edit_text(result_text, parse_mode=ParseMode.MARKDOWN)
    else:
        key = _store_suggestion(context, suggestion)
        await status.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_run_keyboard(key),
        )


# ── command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    task = " ".join(context.args or [])
    if not task:
        await update.message.reply_text("Usage: /suggest <task>")
        return
    await _handle_task(update, context, task, target="shell", auto_run=False)


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    task = " ".join(context.args or [])
    if not task:
        await update.message.reply_text("Usage: /run <task>")
        return
    await _handle_task(update, context, task, target="shell", auto_run=True)


async def cmd_git(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    task = " ".join(context.args or [])
    if not task:
        await update.message.reply_text("Usage: /git <task>")
        return
    await _handle_task(update, context, task, target="git", auto_run=False)


async def cmd_gh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    task = " ".join(context.args or [])
    if not task:
        await update.message.reply_text("Usage: /gh <task>")
        return
    await _handle_task(update, context, task, target="gh", auto_run=False)


# ── message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    task = update.message.text or ""
    if task:
        await _handle_task(update, context, task, target="shell", auto_run=False)


# ── inline keyboard callback ──────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()

    if query.data == "cancel":
        # Remove the keyboard; keep the suggestion text.
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if query.data and query.data.startswith("run:"):
        key = query.data[4:]
        suggestion = _load_suggestion(context, key)
        if not suggestion:
            await query.edit_message_text("❌ Suggestion expired — please re-send your task.")
            return

        await query.edit_message_text(
            _suggestion_text(suggestion) + "\n\n⚙️ Running…",
            parse_mode=ParseMode.MARKDOWN,
        )

        output, rc = await execute_command(suggestion)
        rc_emoji = "✅" if rc == 0 else "⚠️"
        await query.edit_message_text(
            _suggestion_text(suggestion) + f"\n\n{rc_emoji} *Output* (exit {rc})\n{_md_code(output)}",
            parse_mode=ParseMode.MARKDOWN,
        )


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not config.TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not set. Copy .env.example to .env and fill it in.")

    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("suggest", cmd_suggest))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("git", cmd_git))
    app.add_handler(CommandHandler("gh", cmd_gh))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("GCBOT starting — polling for updates…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
