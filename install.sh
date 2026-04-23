#!/usr/bin/env bash
# =============================================================================
#  GCBOT — Installer for Linux & macOS
# =============================================================================
set -euo pipefail

# ── terminal colors ───────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  BOLD="\033[1m"    ; DIM="\033[2m"
  RED="\033[1;31m"  ; GREEN="\033[1;32m"
  YELLOW="\033[1;33m"; CYAN="\033[1;36m"
  BLUE="\033[1;34m" ; MAGENTA="\033[1;35m"
  RESET="\033[0m"
else
  BOLD="" ; DIM="" ; RED="" ; GREEN="" ; YELLOW="" ; CYAN="" ; BLUE="" ; MAGENTA="" ; RESET=""
fi

# ── helpers ───────────────────────────────────────────────────────────────────
banner() {
  echo ""
  echo -e "${CYAN}${BOLD}"
  echo "  ██████╗  ██████╗██████╗  ██████╗ ████████╗"
  echo " ██╔════╝ ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝"
  echo " ██║  ███╗██║     ██████╔╝██║   ██║   ██║   "
  echo " ██║   ██║██║     ██╔══██╗██║   ██║   ██║   "
  echo " ╚██████╔╝╚██████╗██████╔╝╚██████╔╝   ██║   "
  echo "  ╚═════╝  ╚═════╝╚═════╝  ╚═════╝    ╚═╝   "
  echo -e "${RESET}"
  echo -e "${DIM}  GitHub Copilot CLI • Telegram Bot • Installer${RESET}"
  echo ""
}

step()    { echo -e "\n${BLUE}${BOLD}▶ $*${RESET}"; }
ok()      { echo -e "  ${GREEN}✔  $*${RESET}"; }
warn()    { echo -e "  ${YELLOW}⚠  $*${RESET}"; }
fail()    { echo -e "\n${RED}${BOLD}✘  $*${RESET}\n"; exit 1; }
ask()     { echo -e -n "  ${CYAN}$*${RESET} "; }
heading() { echo -e "\n${MAGENTA}${BOLD}$*${RESET}"; printf "${MAGENTA}%0.s─" $(seq 1 ${HEADING_WIDTH}); echo -e "${RESET}"; }

# ── repo info (keep in sync with GitHub) ─────────────────────────────────────
HEADING_WIDTH=60
REPO_URL="https://github.com/SayCrazyy2/GCBOT.git"
REPO_NAME="GCBOT"
DEFAULT_INSTALL_DIR="$HOME/$REPO_NAME"

# =============================================================================
#  0. Banner
# =============================================================================
banner

# =============================================================================
#  1. Detect OS
# =============================================================================
heading "1 / 6  Detecting environment"

OS="$(uname -s)"
case "$OS" in
  Darwin)
    PLATFORM="macOS"
    ok "Platform: macOS ($(sw_vers -productVersion 2>/dev/null || echo 'unknown'))"
    ;;
  Linux)
    PLATFORM="Linux"
    if [[ -f /etc/os-release ]]; then
      source /etc/os-release
      ok "Platform: Linux — $NAME ${VERSION_ID:-}"
    else
      ok "Platform: Linux"
    fi
    ;;
  *)
    fail "Unsupported OS: $OS. Please use Linux or macOS."
    ;;
esac

# =============================================================================
#  2. Detect / select package manager
# =============================================================================
heading "2 / 6  Detecting package manager"

PKG_INSTALL=""
PKG_UPDATE=""

detect_pkg_manager() {
  if [[ "$PLATFORM" == "macOS" ]]; then
    if command -v brew &>/dev/null; then
      PKG_INSTALL="brew install"
      PKG_UPDATE="brew update"
      ok "Package manager: Homebrew ($(brew --version | head -1))"
    else
      warn "Homebrew not found — installing it now…"
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      # Re-source brew environment (Apple Silicon)
      if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
      fi
      PKG_INSTALL="brew install"
      PKG_UPDATE="brew update"
      ok "Homebrew installed."
    fi
  else
    # Linux — try each manager in preference order
    if command -v apt-get &>/dev/null; then
      PKG_INSTALL="sudo apt-get install -y"
      PKG_UPDATE="sudo apt-get update -y"
      ok "Package manager: apt (Debian / Ubuntu)"
    elif command -v dnf &>/dev/null; then
      PKG_INSTALL="sudo dnf install -y"
      PKG_UPDATE="sudo dnf check-update -y || true"
      ok "Package manager: dnf (Fedora / RHEL)"
    elif command -v yum &>/dev/null; then
      PKG_INSTALL="sudo yum install -y"
      PKG_UPDATE="sudo yum check-update -y || true"
      ok "Package manager: yum (CentOS / older RHEL)"
    elif command -v pacman &>/dev/null; then
      PKG_INSTALL="sudo pacman -S --noconfirm"
      PKG_UPDATE="sudo pacman -Sy"
      ok "Package manager: pacman (Arch / Manjaro)"
    elif command -v zypper &>/dev/null; then
      PKG_INSTALL="sudo zypper install -y"
      PKG_UPDATE="sudo zypper refresh"
      ok "Package manager: zypper (openSUSE)"
    elif command -v apk &>/dev/null; then
      PKG_INSTALL="sudo apk add"
      PKG_UPDATE="sudo apk update"
      ok "Package manager: apk (Alpine)"
    else
      warn "No known package manager found."
      warn "Please install git, python3, python3-pip, and gh manually, then re-run."
      fail "Aborting — package manager required."
    fi
  fi
}

detect_pkg_manager

# =============================================================================
#  3. Install prerequisites
# =============================================================================
heading "3 / 6  Installing prerequisites"

install_if_missing() {
  local cmd="$1"
  local pkg="$2"
  if command -v "$cmd" &>/dev/null; then
    ok "$cmd already installed ($(command -v "$cmd"))"
  else
    warn "$cmd not found — installing package '$pkg'…"
    $PKG_UPDATE
    $PKG_INSTALL "$pkg"
    ok "$cmd installed."
  fi
}

install_if_missing git  git
install_if_missing python3 python3

# python3-pip is separate on many distros
if ! python3 -m pip --version &>/dev/null; then
  warn "pip not found — installing…"
  if [[ "$PLATFORM" == "macOS" ]]; then
    python3 -m ensurepip --upgrade || true
  elif command -v apt-get &>/dev/null; then
    sudo apt-get install -y python3-pip
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3-pip
  elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm python-pip
  elif command -v apk &>/dev/null; then
    sudo apk add py3-pip
  fi
fi
ok "pip: $(python3 -m pip --version)"

# GitHub CLI ─────────────────────────────────────────────────────────────────
if command -v gh &>/dev/null; then
  ok "gh CLI already installed ($(gh --version | head -1))"
else
  warn "gh CLI not found — installing…"
  if [[ "$PLATFORM" == "macOS" ]]; then
    brew install gh
  elif command -v apt-get &>/dev/null; then
    # Official GitHub apt source
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
    sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
https://cli.github.com/packages stable main" \
      | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
    sudo apt-get update
    sudo apt-get install -y gh
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y 'dnf-command(config-manager)' || true
    sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
    sudo dnf install -y gh
  elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm github-cli
  elif command -v zypper &>/dev/null; then
    sudo zypper addrepo https://cli.github.com/packages/rpm/gh-cli.repo
    sudo zypper install -y gh
  else
    warn "Could not auto-install gh CLI for this distro."
    warn "Please install it manually from https://cli.github.com/ and re-run."
    fail "Aborting."
  fi
  ok "gh CLI installed ($(gh --version | head -1))"
fi

# =============================================================================
#  4. Clone the repository
# =============================================================================
heading "4 / 6  Cloning repository"

ask "Install directory [$DEFAULT_INSTALL_DIR]: "
read -r INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  ok "Repo already cloned at $INSTALL_DIR — pulling latest changes…"
  git -C "$INSTALL_DIR" pull
elif [[ -d "$INSTALL_DIR" ]]; then
  warn "Directory $INSTALL_DIR exists but is not a git repo."
  ask "Overwrite it? [y/N]: "
  read -r OVERWRITE
  if [[ "${OVERWRITE,,}" == "y" ]]; then
    rm -rf "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
  else
    fail "Aborting — choose a different install directory."
  fi
else
  git clone "$REPO_URL" "$INSTALL_DIR"
  ok "Cloned to $INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# =============================================================================
#  5. Python virtual environment + dependencies
# =============================================================================
heading "5 / 6  Setting up Python environment"

VENV_DIR="$INSTALL_DIR/.venv"
if [[ -d "$VENV_DIR" ]]; then
  ok "Virtual environment already exists — skipping creation."
else
  python3 -m venv "$VENV_DIR"
  ok "Virtual environment created at $VENV_DIR"
fi

# Activate venv for the remainder of the script
source "$VENV_DIR/bin/activate"
ok "Virtual environment activated."

pip install --upgrade pip --quiet
pip install -r "$INSTALL_DIR/requirements.txt" --quiet
ok "Python dependencies installed."

# Install / update gh copilot extension ──────────────────────────────────────
# GitHub Copilot (built-in in newer gh versions)
if gh help copilot &>/dev/null; then
  ok "GitHub Copilot CLI already available (built-in)."
else
  warn "GitHub Copilot not found in gh CLI."

  if gh auth status &>/dev/null 2>&1; then
    warn "Attempting to install gh-copilot extension…"
    gh extension install github/gh-copilot 2>/dev/null || \
      warn "Failed to install gh-copilot (likely due to version conflict)."
  else
    warn "You are not logged in to GitHub CLI."
    warn "Run: gh auth login"
  fi
fi

# =============================================================================
#  6. Configure .env
# =============================================================================
heading "6 / 6  Configuring .env"

ENV_FILE="$INSTALL_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  ask ".env already exists. Reconfigure it? [y/N]: "
  read -r RECONFIGURE
  if [[ "${RECONFIGURE,,}" != "y" ]]; then
    ok "Keeping existing .env"
    SKIP_ENV=1
  fi
fi

if [[ -z "${SKIP_ENV:-}" ]]; then
  cp "$INSTALL_DIR/.env.example" "$ENV_FILE"

  echo ""
  echo -e "  ${DIM}Press Enter to keep the default shown in [brackets].${RESET}"

  # TELEGRAM_TOKEN ─────────────────────────────────────────────────────────
  echo ""
  ask "Telegram bot token (from @BotFather): "
  read -r TG_TOKEN
  while [[ -z "$TG_TOKEN" ]]; do
    warn "Token cannot be empty."
    ask "Telegram bot token: "
    read -r TG_TOKEN
  done

  # ALLOWED_USERS ───────────────────────────────────────────────────────────
  ask "Allowed Telegram user IDs, comma-separated (leave empty = allow all): "
  read -r TG_USERS
  if [[ -z "$TG_USERS" ]]; then
    warn "No restriction set — anyone who finds the bot can use it."
  fi

  # WORKSPACE_DIR ───────────────────────────────────────────────────────────
  DEFAULT_WS="$HOME/gcbot-workspace"
  ask "Workspace directory [$DEFAULT_WS]: "
  read -r WS_DIR
  WS_DIR="${WS_DIR:-$DEFAULT_WS}"
  WS_DIR="${WS_DIR/#\~/$HOME}"

  # COMMAND_TIMEOUT ─────────────────────────────────────────────────────────
  ask "Command timeout in seconds [120]: "
  read -r CMD_TIMEOUT
  CMD_TIMEOUT="${CMD_TIMEOUT:-120}"

  # Write .env via Python — safely handles any special characters in values.
  python3 - "$ENV_FILE" "$TG_TOKEN" "$TG_USERS" "$WS_DIR" "$CMD_TIMEOUT" <<'PYEOF'
import sys
import re

env_file, token, users, ws_dir, timeout = sys.argv[1:6]

with open(env_file, encoding="utf-8") as f:
    lines = f.readlines()

replacements = {
    "TELEGRAM_TOKEN":  token,
    "ALLOWED_USERS":   users,
    "WORKSPACE_DIR":   ws_dir,
    "COMMAND_TIMEOUT": timeout,
}

out = []
for line in lines:
    m = re.match(r'^([A-Z_]+)=', line)
    if m and m.group(1) in replacements:
        out.append(f"{m.group(1)}={replacements[m.group(1)]}\n")
    else:
        out.append(line)

with open(env_file, "w", encoding="utf-8") as f:
    f.writelines(out)
PYEOF

  ok ".env written to $ENV_FILE"
fi

# =============================================================================
#  Done!
# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║           ✔  GCBOT installation complete!                ║${RESET}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${BOLD}Next steps:${RESET}"
echo ""
echo -e "  ${CYAN}1.${RESET}  Authenticate with GitHub (if not already done):"
echo -e "      ${DIM}gh auth login${RESET}"
echo ""
echo -e "  ${CYAN}2.${RESET}  Start GCBOT:"
echo -e "      ${DIM}cd $INSTALL_DIR && source .venv/bin/activate && python bot.py${RESET}"
echo ""
echo -e "  ${CYAN}3.${RESET}  Open Telegram and send your bot ${BOLD}/start${RESET}"
echo ""
if [[ -z "$(grep "^ALLOWED_USERS=" "$ENV_FILE" | cut -d= -f2 | tr -d ' ')" ]]; then
  echo -e "  ${YELLOW}⚠  ALLOWED_USERS is empty — set it in $ENV_FILE to restrict access.${RESET}"
  echo ""
fi
