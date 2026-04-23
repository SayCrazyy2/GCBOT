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

| Command | What it does |
|---------|-------------|
| `/suggest <task>` | Get a shell-command suggestion from Copilot (no execution) |
| `/run <task>` | Suggest **and execute** the command; returns output |
| `/git <task>` | Suggest a `git` command |
| `/gh <task>` | Suggest a `gh` CLI command |
| plain message | Suggestion + inline **▶ Run** / **✖ Cancel** buttons |

* **Auth** — restrict access to specific Telegram user IDs via `ALLOWED_USERS`.
* **Safe-by-default** — plain messages only suggest; you click **▶ Run** to execute.
* **Self-improving** — instruct the bot to edit its own source code via Copilot.

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
$EDITOR .env          # set TELEGRAM_TOKEN and optionally ALLOWED_USERS / WORK_DIR

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
| `WORK_DIR` | | `~` | Working directory for executed commands |
| `MAX_OUTPUT_LENGTH` | | `3500` | Max chars returned per command output |
| `COMMAND_TIMEOUT` | | `120` | Seconds before a command is killed |
| `COPILOT_TIMEOUT` | | `60` | Seconds to wait for Copilot suggestion |

---

## Usage examples

```
/suggest list all Python files modified in the last 24 hours
/run     show disk usage of the current directory sorted by size
/git     undo the last commit without losing changes
/gh      create a pull request for the current branch
```

Or just type naturally:

```
find all TODO comments in the src/ directory
```

GCBOT returns Copilot's suggestion with **▶ Run** and **✖ Cancel** buttons.

---

## Architecture

```
bot.py        Telegram bot — command handlers, inline keyboards, agentic loop
copilot.py    pexpect wrapper around `gh copilot suggest`
runner.py     Safe subprocess execution with timeout & output capping
config.py     Environment-variable configuration via python-dotenv
```

---

## Security

* **Never** share or commit your `.env` file (it is listed in `.gitignore`).
* Set `ALLOWED_USERS` to your own Telegram user ID so only you can trigger commands.
* `COMMAND_TIMEOUT` prevents runaway processes.
* Review Copilot's suggestion before pressing **▶ Run**.

---

## License

MIT
