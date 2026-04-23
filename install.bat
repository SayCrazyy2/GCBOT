@echo off
setlocal EnableDelayedExpansion

:: =============================================================================
::  GCBOT — Installer for Windows
:: =============================================================================

:: Enable ANSI colors on Windows 10+
for /f "tokens=4-5 delims=. " %%a in ('ver') do (
    if %%a GEQ 10 (
        reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1
    )
)

:: Color codes (only work in Windows Terminal / modern cmd)
set "R=[0m"
set "BOLD=[1m"
set "RED=[1;31m"
set "GREEN=[1;32m"
set "YELLOW=[1;33m"
set "CYAN=[1;36m"
set "BLUE=[1;34m"
set "MAGENTA=[1;35m"
set "DIM=[2m"

:: =============================================================================
::  Repo defaults
:: =============================================================================
set "REPO_URL=https://github.com/SayCrazyy2/GCBOT.git"
set "REPO_NAME=GCBOT"
set "DEFAULT_INSTALL_DIR=%USERPROFILE%\%REPO_NAME%"
set "ERRORS=0"

:: =============================================================================
::  Banner
:: =============================================================================
cls
echo.
echo %CYAN%%BOLD%  ██████╗  ██████╗██████╗  ██████╗ ████████╗%R%
echo %CYAN%%BOLD% ██╔════╝ ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝%R%
echo %CYAN%%BOLD% ██║  ███╗██║     ██████╔╝██║   ██║   ██║   %R%
echo %CYAN%%BOLD% ██║   ██║██║     ██╔══██╗██║   ██║   ██║   %R%
echo %CYAN%%BOLD% ╚██████╔╝╚██████╗██████╔╝╚██████╔╝   ██║   %R%
echo %CYAN%%BOLD%  ╚═════╝  ╚═════╝╚═════╝  ╚═════╝    ╚═╝   %R%
echo.
echo %DIM%  GitHub Copilot CLI • Telegram Bot • Windows Installer%R%
echo.

:: =============================================================================
::  1. Check prerequisites
:: =============================================================================
echo %MAGENTA%%BOLD%1 / 5  Checking prerequisites%R%
echo %MAGENTA%────────────────────────────────────────────────────────────%R%

:: git ────────────────────────────────────────────────────────────────────────
echo.
where git >nul 2>&1
if %errorlevel% NEQ 0 (
    echo   %RED%✘  git not found.%R%
    echo   %YELLOW%   Please install Git from https://git-scm.com/download/win%R%
    echo   %YELLOW%   then re-run this installer.%R%
    set /a ERRORS+=1
) else (
    for /f "tokens=*" %%v in ('git --version 2^>nul') do set "GIT_VER=%%v"
    echo   %GREEN%✔  !GIT_VER!%R%
)

:: python ─────────────────────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% NEQ 0 (
    where python3 >nul 2>&1
    if %errorlevel% NEQ 0 (
        echo   %RED%✘  Python 3 not found.%R%
        echo   %YELLOW%   Install Python 3.10+ from https://www.python.org/downloads/%R%
        echo   %YELLOW%   (check "Add python.exe to PATH" during setup)%R%
        set /a ERRORS+=1
    ) else (
        set "PYTHON_CMD=python3"
        for /f "tokens=*" %%v in ('python3 --version 2^>nul') do set "PY_VER=%%v"
        echo   %GREEN%✔  !PY_VER!%R%
    )
) else (
    set "PYTHON_CMD=python"
    for /f "tokens=*" %%v in ('python --version 2^>nul') do set "PY_VER=%%v"
    echo   %GREEN%✔  !PY_VER!%R%
)

:: gh CLI ─────────────────────────────────────────────────────────────────────
where gh >nul 2>&1
if %errorlevel% NEQ 0 (
    echo   %YELLOW%⚠  gh CLI not found.%R%
    echo   %YELLOW%   Attempting to install via winget...%R%
    winget install --id GitHub.cli -e --source winget >nul 2>&1
    if %errorlevel% EQU 0 (
        echo   %GREEN%✔  gh CLI installed via winget.%R%
        :: Refresh PATH for this session
        for /f "tokens=*" %%p in ('where gh 2^>nul') do set "GH_PATH=%%p"
    ) else (
        echo   %YELLOW%   winget install failed.%R%
        echo   %YELLOW%   Please install gh CLI from https://cli.github.com/ and re-run.%R%
        set /a ERRORS+=1
    )
) else (
    for /f "tokens=*" %%v in ('gh --version 2^>nul ^| findstr /i "gh version"') do set "GH_VER=%%v"
    echo   %GREEN%✔  !GH_VER!%R%
)

if %ERRORS% GTR 0 (
    echo.
    echo   %RED%%BOLD%✘  %ERRORS% prerequisite(s) missing. Fix them and re-run.%R%
    echo.
    pause
    exit /b 1
)

:: =============================================================================
::  2. Clone repository
:: =============================================================================
echo.
echo %MAGENTA%%BOLD%2 / 5  Cloning repository%R%
echo %MAGENTA%────────────────────────────────────────────────────────────%R%
echo.
echo   %DIM%Default install directory: %DEFAULT_INSTALL_DIR%%R%
set /p "INSTALL_DIR=  Install directory [%DEFAULT_INSTALL_DIR%]: "
if "!INSTALL_DIR!"=="" set "INSTALL_DIR=%DEFAULT_INSTALL_DIR%"

if exist "!INSTALL_DIR!\.git" (
    echo   %GREEN%✔  Repo already cloned — pulling latest changes...%R%
    git -C "!INSTALL_DIR!" pull
) else if exist "!INSTALL_DIR!" (
    echo   %YELLOW%⚠  Directory exists but is not a git repo.%R%
    set /p "OVERWRITE=  Overwrite it? [y/N]: "
    if /i "!OVERWRITE!"=="y" (
        rmdir /s /q "!INSTALL_DIR!"
        git clone "%REPO_URL%" "!INSTALL_DIR!"
    ) else (
        echo   %RED%✘  Aborting — choose a different directory.%R%
        pause
        exit /b 1
    )
) else (
    git clone "%REPO_URL%" "!INSTALL_DIR!"
)
echo   %GREEN%✔  Repository ready at !INSTALL_DIR!%R%

:: =============================================================================
::  3. Python virtual environment + dependencies
:: =============================================================================
echo.
echo %MAGENTA%%BOLD%3 / 5  Setting up Python environment%R%
echo %MAGENTA%────────────────────────────────────────────────────────────%R%
echo.

set "VENV_DIR=!INSTALL_DIR!\.venv"
if not exist "!VENV_DIR!" (
    echo   Creating virtual environment...
    %PYTHON_CMD% -m venv "!VENV_DIR!"
    echo   %GREEN%✔  Virtual environment created.%R%
) else (
    echo   %GREEN%✔  Virtual environment already exists.%R%
)

echo   Installing Python dependencies...
call "!VENV_DIR!\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
python -m pip install -r "!INSTALL_DIR!\requirements.txt" --quiet
echo   %GREEN%✔  Dependencies installed.%R%

:: gh copilot extension ────────────────────────────────────────────────────────
gh extension list 2>nul | findstr /i "github/gh-copilot" >nul 2>&1
if %errorlevel% EQU 0 (
    echo   %GREEN%✔  gh copilot extension already installed.%R%
    gh extension upgrade gh-copilot >nul 2>&1
) else (
    gh auth status >nul 2>&1
    if %errorlevel% EQU 0 (
        echo   Installing gh copilot extension...
        gh extension install github/gh-copilot
        echo   %GREEN%✔  gh copilot extension installed.%R%
    ) else (
        echo   %YELLOW%⚠  Not logged in to GitHub CLI.%R%
        echo   %YELLOW%   Run: gh auth login%R%
        echo   %YELLOW%   Then: gh extension install github/gh-copilot%R%
    )
)

:: =============================================================================
::  4. Configure .env
:: =============================================================================
echo.
echo %MAGENTA%%BOLD%4 / 5  Configuring .env%R%
echo %MAGENTA%────────────────────────────────────────────────────────────%R%
echo.

set "ENV_FILE=!INSTALL_DIR!\.env"
set "SKIP_ENV=0"

if exist "!ENV_FILE!" (
    set /p "RECONFIGURE=  .env already exists. Reconfigure it? [y/N]: "
    if /i not "!RECONFIGURE!"=="y" (
        echo   %GREEN%✔  Keeping existing .env%R%
        set "SKIP_ENV=1"
    )
)

if "!SKIP_ENV!"=="0" (
    copy /y "!INSTALL_DIR!\.env.example" "!ENV_FILE!" >nul
    echo   %DIM%  Press Enter to keep the default shown in [brackets].%R%
    echo.

    :: TELEGRAM_TOKEN ─────────────────────────────────────────────────────────
    set "TG_TOKEN="
    :ask_token
    set /p "TG_TOKEN=  Telegram bot token (from @BotFather): "
    if "!TG_TOKEN!"=="" (
        echo   %YELLOW%⚠  Token cannot be empty.%R%
        goto ask_token
    )

    :: ALLOWED_USERS ──────────────────────────────────────────────────────────
    set /p "TG_USERS=  Allowed Telegram user IDs, comma-separated (empty = allow all): "

    :: WORKSPACE_DIR ──────────────────────────────────────────────────────────
    set "DEFAULT_WS=%USERPROFILE%\gcbot-workspace"
    set /p "WS_DIR=  Workspace directory [!DEFAULT_WS!]: "
    if "!WS_DIR!"=="" set "WS_DIR=!DEFAULT_WS!"

    :: COMMAND_TIMEOUT ────────────────────────────────────────────────────────
    set /p "CMD_TIMEOUT=  Command timeout in seconds [120]: "
    if "!CMD_TIMEOUT!"=="" set "CMD_TIMEOUT=120"

    :: Write .env using PowerShell (reliable on all modern Windows) ───────────
    powershell -NoProfile -Command ^
      "$env = Get-Content '!ENV_FILE!';" ^
      "$env = $env -replace '^TELEGRAM_TOKEN=.*', 'TELEGRAM_TOKEN=!TG_TOKEN!';" ^
      "$env = $env -replace '^ALLOWED_USERS=.*', 'ALLOWED_USERS=!TG_USERS!';" ^
      "$env = $env -replace '^WORKSPACE_DIR=.*', 'WORKSPACE_DIR=!WS_DIR!';" ^
      "$env = $env -replace '^COMMAND_TIMEOUT=.*', 'COMMAND_TIMEOUT=!CMD_TIMEOUT!';" ^
      "$env | Set-Content '!ENV_FILE!'"

    echo   %GREEN%✔  .env written to !ENV_FILE!%R%

    if "!TG_USERS!"=="" (
        echo   %YELLOW%⚠  ALLOWED_USERS is empty — anyone who finds the bot can use it.%R%
    )
)

:: =============================================================================
::  5. Done!
:: =============================================================================
echo.
echo %MAGENTA%%BOLD%5 / 5  Finishing up%R%
echo %MAGENTA%────────────────────────────────────────────────────────────%R%
echo.
echo %GREEN%%BOLD%╔══════════════════════════════════════════════════════════╗%R%
echo %GREEN%%BOLD%║           ✔  GCBOT installation complete!                ║%R%
echo %GREEN%%BOLD%╚══════════════════════════════════════════════════════════╝%R%
echo.
echo   %BOLD%Next steps:%R%
echo.
echo   %CYAN%1.%R%  Authenticate with GitHub (if not already done):
echo       %DIM%gh auth login%R%
echo.
echo   %CYAN%2.%R%  Start GCBOT (in a new terminal):
echo       %DIM%cd !INSTALL_DIR!%R%
echo       %DIM%.venv\Scripts\activate%R%
echo       %DIM%python bot.py%R%
echo.
echo   %CYAN%3.%R%  Open Telegram and send your bot %BOLD%/start%R%
echo.
pause
endlocal
