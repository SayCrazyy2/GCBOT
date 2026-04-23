"""GCBOT — GitHub Copilot CLI in Telegram.

Receive a task from Telegram → forward to ``gh copilot suggest`` →
optionally execute the suggested command → return the result.

Workspace commands give the AI (and the user) full read/write/delete access
to a dedicated workspace directory on the host machine.
"""

from __future__ import annotations

import asyncio
import logging
import os
import textwrap
import uuid
from pathlib import Path

from telegram import Document, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
from copilot import get_suggestion
from runner import execute_command
from workspace import (
    WorkspaceError,
    delete_path,
    ensure_workspace,
    list_dir,
    make_dir,
    read_file,
    rel_display,
    safe_path,
    workspace_info,
    write_file,
)

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Conversation state for the two-step /write command
_WRITE_CONTENT = 1

# ── helpers ───────────────────────────────────────────────────────────────────

HELP_TEXT = textwrap.dedent(
    """
    🤖 *GCBOT* — GitHub Copilot CLI in Telegram

    Send any natural-language task and I'll ask GitHub Copilot CLI for a command suggestion.

    *Copilot commands*
    `/suggest <task>` — Shell command suggestion (no execution)
    `/run <task>`     — Suggest *and* execute the command
    `/git <task>`     — Suggest a git command
    `/gh <task>`      — Suggest a gh CLI command
    `/exec <cmd>`     — Run a shell command directly (no Copilot)

    *Workspace commands* _(all paths are relative to your workspace)_
    `/workspace`      — Show workspace path, size, and top-level items
    `/new <project>`  — Create and switch into a new project directory
    `/cd <dir>`       — Change session directory (use `.` to go back to root)
    `/pwd`            — Show current session directory
    `/ls [path]`      — List files and directories
    `/cat <file>`     — Print file contents
    `/write <file>`   — Write text to a file (bot asks for content next)
    `/mkdir <dir>`    — Create a directory
    `/rm <path>`      — Delete a file or directory tree
    `/upload`         — Send a file from Telegram into the workspace
    `/download <file>`— Send a workspace file back to you via Telegram

    *Sending a plain message* gives you a Copilot suggestion with an inline *▶ Run* button.
    """
).strip()


def _is_authorized(user_id: int) -> bool:
    if not config.ALLOWED_USERS:
        return True
    return str(user_id) in config.ALLOWED_USERS


def _md_code(text: str) -> str:
    """Wrap *text* in a Markdown code block (escapes back-ticks)."""
    escaped = text.replace("`", "\\`")
    return f"```\n{escaped}\n```"


def _suggestion_text(suggestion: str) -> str:
    return f"💡 *Copilot Suggestion*\n{_md_code(suggestion)}"


def _get_session_cwd(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Return the user's current workspace directory (persisted in user_data)."""
    if context.user_data is None:
        return config.WORKSPACE_DIR
    return context.user_data.get("cwd", config.WORKSPACE_DIR)


def _set_session_cwd(context: ContextTypes.DEFAULT_TYPE, path: str) -> None:
    if context.user_data is not None:
        context.user_data["cwd"] = path


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


# ── core Copilot flow ─────────────────────────────────────────────────────────

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
    cwd = _get_session_cwd(context)

    if auto_run:
        await status.edit_text(text + "\n\n⚙️ Running…", parse_mode=ParseMode.MARKDOWN)
        output, rc = await execute_command(suggestion, cwd=cwd)
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


# ── Copilot command handlers ──────────────────────────────────────────────────

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


async def cmd_exec(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Directly execute a shell command without asking Copilot."""
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    command = " ".join(context.args or [])
    if not command:
        await update.message.reply_text("Usage: /exec <shell command>")
        return

    cwd = _get_session_cwd(context)
    status = await update.message.reply_text(f"⚙️ Running in `{rel_display(cwd) or '/'}`…",
                                              parse_mode=ParseMode.MARKDOWN)
    output, rc = await execute_command(command, cwd=cwd)
    rc_emoji = "✅" if rc == 0 else "⚠️"
    await status.edit_text(
        f"⚙️ `{command}`\n\n{rc_emoji} *Output* (exit {rc})\n{_md_code(output)}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── workspace command handlers ────────────────────────────────────────────────

async def cmd_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    try:
        info = workspace_info()
    except Exception as exc:
        await update.message.reply_text(f"❌ {exc}")
        return
    await update.message.reply_text(info, parse_mode=ParseMode.MARKDOWN)


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a new project subdirectory and switch the session into it."""
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    name = " ".join(context.args or []).strip()
    if not name:
        await update.message.reply_text("Usage: /new <project-name>")
        return
    try:
        path = make_dir(name)
        _set_session_cwd(context, str(path))
        await update.message.reply_text(
            f"📁 Created and switched to `{rel_display(str(path))}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except WorkspaceError as exc:
        await update.message.reply_text(f"❌ {exc}")


async def cmd_cd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Change the session's working directory within the workspace."""
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    target = " ".join(context.args or []).strip() or "."
    if target == "/":
        _set_session_cwd(context, config.WORKSPACE_DIR)
        await update.message.reply_text("📂 Switched to workspace root.")
        return
    cwd = _get_session_cwd(context)
    try:
        path = safe_path(target, base=cwd)
        if not path.is_dir():
            await update.message.reply_text(f"❌ `{target}` is not a directory.",
                                            parse_mode=ParseMode.MARKDOWN)
            return
        _set_session_cwd(context, str(path))
        await update.message.reply_text(
            f"📂 Switched to `{rel_display(str(path)) or '/'}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except WorkspaceError as exc:
        await update.message.reply_text(f"❌ {exc}")


async def cmd_pwd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    cwd = _get_session_cwd(context)
    display = rel_display(cwd) or "/"
    await update.message.reply_text(
        f"📂 `{display}`", parse_mode=ParseMode.MARKDOWN
    )


async def cmd_ls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    target = " ".join(context.args or []).strip() or "."
    cwd = _get_session_cwd(context)
    try:
        listing = list_dir(target, base=cwd)
        display = rel_display(str(safe_path(target, base=cwd))) or "/"
        await update.message.reply_text(
            f"📂 `{display}`\n\n{listing}", parse_mode=ParseMode.MARKDOWN
        )
    except WorkspaceError as exc:
        await update.message.reply_text(f"❌ {exc}")


async def cmd_cat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    filename = " ".join(context.args or []).strip()
    if not filename:
        await update.message.reply_text("Usage: /cat <file>")
        return
    cwd = _get_session_cwd(context)
    try:
        content = read_file(filename, base=cwd)
        if len(content) > config.MAX_OUTPUT_LENGTH:
            content = content[: config.MAX_OUTPUT_LENGTH] + "\n… (truncated)"
        await update.message.reply_text(
            f"📄 `{filename}`\n{_md_code(content)}", parse_mode=ParseMode.MARKDOWN
        )
    except WorkspaceError as exc:
        await update.message.reply_text(f"❌ {exc}")


async def cmd_write_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Step 1 of the /write conversation: record the filename, ask for content."""
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return ConversationHandler.END
    filename = " ".join(context.args or []).strip()
    if not filename:
        await update.message.reply_text("Usage: /write <file>")
        return ConversationHandler.END
    if context.user_data is not None:
        context.user_data["write_filename"] = filename
    await update.message.reply_text(
        f"✏️ Send the content for `{filename}` (or /cancel to abort).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return _WRITE_CONTENT


async def cmd_write_content(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Step 2 of the /write conversation: receive content and write the file."""
    assert update.message is not None
    content = update.message.text or ""
    filename = (context.user_data or {}).get("write_filename", "")
    if not filename:
        await update.message.reply_text("❌ Lost track of the filename. Please /write again.")
        return ConversationHandler.END
    cwd = _get_session_cwd(context)
    try:
        path = write_file(filename, content, base=cwd)
        await update.message.reply_text(
            f"✅ Written `{rel_display(str(path))}`", parse_mode=ParseMode.MARKDOWN
        )
    except WorkspaceError as exc:
        await update.message.reply_text(f"❌ {exc}")
    return ConversationHandler.END


async def cmd_write_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert update.message is not None
    await update.message.reply_text("✖ Write cancelled.")
    return ConversationHandler.END


async def cmd_mkdir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    dirname = " ".join(context.args or []).strip()
    if not dirname:
        await update.message.reply_text("Usage: /mkdir <dir>")
        return
    cwd = _get_session_cwd(context)
    try:
        path = make_dir(dirname, base=cwd)
        await update.message.reply_text(
            f"📁 Created `{rel_display(str(path))}`", parse_mode=ParseMode.MARKDOWN
        )
    except WorkspaceError as exc:
        await update.message.reply_text(f"❌ {exc}")


async def cmd_rm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    target = " ".join(context.args or []).strip()
    if not target:
        await update.message.reply_text("Usage: /rm <file-or-dir>")
        return
    cwd = _get_session_cwd(context)
    try:
        delete_path(target, base=cwd)
        await update.message.reply_text(f"🗑️ Deleted `{target}`", parse_mode=ParseMode.MARKDOWN)
    except WorkspaceError as exc:
        await update.message.reply_text(f"❌ {exc}")


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a file sent directly to the bot — saves it into the workspace."""
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return

    doc: Document | None = update.message.document
    if doc is None:
        await update.message.reply_text(
            "📎 Send a file as a document (attachment) to upload it to the workspace.\n"
            "You can also use the command *before* sending the file as a caption.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    cwd = _get_session_cwd(context)
    filename = doc.file_name or f"upload_{doc.file_unique_id}"
    dest = safe_path(filename, base=cwd)
    dest.parent.mkdir(parents=True, exist_ok=True)

    status = await update.message.reply_text(f"⬇️ Downloading `{filename}`…",
                                              parse_mode=ParseMode.MARKDOWN)
    try:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(str(dest))
        await status.edit_text(
            f"✅ Saved to `{rel_display(str(dest))}`", parse_mode=ParseMode.MARKDOWN
        )
    except WorkspaceError as exc:
        await status.edit_text(f"❌ {exc}")
    except Exception as exc:
        await status.edit_text(f"❌ Download failed: {exc}")


async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a workspace file back to the user via Telegram."""
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return
    filename = " ".join(context.args or []).strip()
    if not filename:
        await update.message.reply_text("Usage: /download <file>")
        return
    cwd = _get_session_cwd(context)
    try:
        path = safe_path(filename, base=cwd)
        if not path.is_file():
            await update.message.reply_text(f"❌ `{filename}` is not a file.",
                                            parse_mode=ParseMode.MARKDOWN)
            return
        size = path.stat().st_size
        if size > config.MAX_DOWNLOAD_SIZE:
            await update.message.reply_text(
                f"❌ File is {size // (1024*1024)} MB — exceeds the "
                f"{config.MAX_DOWNLOAD_SIZE // (1024*1024)} MB download limit."
            )
            return
        with open(str(path), "rb") as fh:
            await update.message.reply_document(document=fh, filename=path.name)
    except WorkspaceError as exc:
        await update.message.reply_text(f"❌ {exc}")
    except Exception as exc:
        await update.message.reply_text(f"❌ {exc}")


# ── message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    if not _is_authorized(update.effective_user.id):  # type: ignore[union-attr]
        return

    # Document uploads without a command → treat as /upload
    if update.message.document:
        await cmd_upload(update, context)
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
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if query.data and query.data.startswith("run:"):
        key = query.data[4:]
        suggestion = _load_suggestion(context, key)
        if not suggestion:
            await query.edit_message_text("❌ Suggestion expired — please re-send your task.")
            return

        cwd = _get_session_cwd(context)
        await query.edit_message_text(
            _suggestion_text(suggestion) + "\n\n⚙️ Running…",
            parse_mode=ParseMode.MARKDOWN,
        )

        output, rc = await execute_command(suggestion, cwd=cwd)
        rc_emoji = "✅" if rc == 0 else "⚠️"
        await query.edit_message_text(
            _suggestion_text(suggestion) + f"\n\n{rc_emoji} *Output* (exit {rc})\n{_md_code(output)}",
            parse_mode=ParseMode.MARKDOWN,
        )


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not config.TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is not set. Copy .env.example to .env and fill it in.")

    ensure_workspace()
    logger.info("Workspace: %s", config.WORKSPACE_DIR)

    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Two-step /write conversation
    write_conv = ConversationHandler(
        entry_points=[CommandHandler("write", cmd_write_start)],
        states={_WRITE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_write_content)]},
        fallbacks=[CommandHandler("cancel", cmd_write_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    # Copilot commands
    app.add_handler(CommandHandler("suggest", cmd_suggest))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("git", cmd_git))
    app.add_handler(CommandHandler("gh", cmd_gh))
    app.add_handler(CommandHandler("exec", cmd_exec))
    # Workspace commands
    app.add_handler(CommandHandler("workspace", cmd_workspace))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("cd", cmd_cd))
    app.add_handler(CommandHandler("pwd", cmd_pwd))
    app.add_handler(CommandHandler("ls", cmd_ls))
    app.add_handler(CommandHandler("cat", cmd_cat))
    app.add_handler(write_conv)
    app.add_handler(CommandHandler("mkdir", cmd_mkdir))
    app.add_handler(CommandHandler("rm", cmd_rm))
    app.add_handler(CommandHandler("upload", cmd_upload))
    app.add_handler(CommandHandler("download", cmd_download))
    # Generic message / file upload
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.Document.ALL) & ~filters.COMMAND,
        handle_message,
    ))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("GCBOT starting — polling for updates…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
