# GCBOT — GitHub Copilot CLI in Telegram

Put the full power of **GitHub Copilot CLI** at your fingertips through Telegram.

Send a message from Telegram. GCBOT forwards it to `gh copilot suggest` running on your
machine and returns the result. The AI reads and writes files, executes shell commands,
commits code, pushes branches, opens PRs, and manages multi-step projects — autonomously,
in the background, while you go about your day.

> Inspired by [OpenClaw](https://github.com/openai/openclaw) — but radically simpler,
> cheaper, vibe-coding focused, and self-improving design.

---

## Features

### Copilot commands

| Command | What it does |
|---------|-------------|
| `/suggest <task>` | Shell-command suggestion from Copilot (no execution) |
| `/run <task>` | Suggest **and execute** the command; returns output |
| `/git <task>` | Suggest a `git` command |
| `/gh <task>` | Suggest a `gh` CLI command |
| `/exec <cmd>` | Run a shell command directly (no Copilot) |
| plain message | Suggestion + inline **▶ Run** / **✖ Cancel** buttons |

### Workspace commands

All file operations are confined to the configured `WORKSPACE_DIR` (path traversal is blocked).

| Command | What it does |
|---------|-------------|
| `/workspace` | Show workspace path, size, and top-level items |
| `/new <project>` | Create and switch into a new project directory |
| `/cd <dir>` | Change session directory within the workspace |
| `/pwd` | Show the current session directory |
| `/ls [path]` | List files and directories |
| `/cat <file>` | Print file contents |
| `/write <file>` | Write text to a file (bot asks for content next) |
| `/mkdir <dir>` | Create a directory |
| `/rm <path>` | Delete a file or entire directory tree |
| `/upload` | Send a file from Telegram into the workspace |
| `/download <file>` | Send a workspace file back via Telegram |

---

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| [GitHub CLI](https://cli.github.com/) | latest |
| [gh copilot extension](https://docs.github.com/en/copilot/github-copilot-in-the-cli) | latest |
| A Telegram bot token | from [@BotFather](https://t.me/BotFather) |

Install the Copilot CLI extension once:

```bash
gh extension install github/gh-copilot
gh auth login          # if not already authenticated
gh copilot --version   # verify
```

---

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/SayCrazyy2/GCBOT.git
cd GCBOT

# 2. Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure the bot
cp .env.example .env
$EDITOR .env          # set TELEGRAM_TOKEN and WORKSPACE_DIR

# 5. Run
python bot.py
```

The bot uses long-polling — no public URL or webhook needed.

---

## Configuration (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_TOKEN` | ✅ | — | Bot token from @BotFather |
| `ALLOWED_USERS` | | *(allow all)* | Comma-separated Telegram user IDs |
| `WORKSPACE_DIR` | | `~/gcbot-workspace` | Directory where the AI reads/writes/deletes files |
| `MAX_OUTPUT_LENGTH` | | `3500` | Max chars returned per command output |
| `MAX_DOWNLOAD_SIZE` | | `20971520` (20 MB) | Max file size for `/download` |
| `COMMAND_TIMEOUT` | | `120` | Seconds before a command is killed |
| `COPILOT_TIMEOUT` | | `60` | Seconds to wait for Copilot suggestion |

---

## Usage examples

### Ask Copilot for a command
```
/suggest list all Python files modified in the last 24 hours
/run     show disk usage of the current directory sorted by size
/git     undo the last commit without losing changes
/gh      create a pull request for the current branch
```

Or just type naturally — GCBOT returns Copilot's suggestion with **▶ Run** / **✖ Cancel** buttons.

### Working on a project in the workspace
```
/new my-api              # creates ~/gcbot-workspace/my-api and switches into it
/run scaffold a FastAPI hello-world app
/ls                      # see what Copilot generated
/cat main.py             # read a file
/write .env              # GCBOT asks for content; type it and send
/download main.py        # Telegram sends you the file
```

### Uploading files
Send any file as a Telegram document — GCBOT saves it to your current workspace directory.

---

## Architecture

```
bot.py        Telegram bot — command handlers, inline keyboards, agentic loop
copilot.py    pexpect wrapper around `gh copilot suggest`
runner.py     Safe subprocess execution with per-session cwd, timeout & output capping
workspace.py  Path-safe file operations (read, write, delete, list) inside WORKSPACE_DIR
config.py     Environment-variable configuration via python-dotenv
```

---

## Security

* **Never** share or commit your `.env` file (it is listed in `.gitignore`).
* Set `ALLOWED_USERS` to your own Telegram user ID so only you can trigger commands.
* All workspace file operations are path-safe — `../` traversal attempts are blocked.
* `COMMAND_TIMEOUT` prevents runaway processes.
* Review Copilot's suggestion before pressing **▶ Run**.

---

## License

MIT
