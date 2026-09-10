@echo off
setlocal enabledelayedexpansion

set "TOOLS_DIR=%~dp0"
if "%TOOLS_DIR:~-1%"=="\" set "TOOLS_DIR=%TOOLS_DIR:~0,-1%"
for %%I in ("%TOOLS_DIR%\..\..") do set "ROOT_DIR=%%~fI"
set "FRONTEND_DIR=%ROOT_DIR%\apps\desktop\frontend"

if /I "%~1"=="check" goto RUN_CHECK_FROM_ARGUMENT

:MENU
cls
echo ============================================
echo              OrchAI - Setup
echo ============================================
echo.
echo   [1] Check environment, prerequisites, and dependencies (headless API)
echo   [2] Check environment, prerequisites, and dependencies (Desktop)
echo   [0] Exit
echo.
set /p "ACTION=Choose an option: "

if "%ACTION%"=="1" goto MENU_CHECK_HEADLESS
if "%ACTION%"=="2" goto MENU_CHECK_DESKTOP
if "%ACTION%"=="0" goto EXIT

echo Unsupported option: %ACTION%
pause
goto MENU

:MENU_CHECK_HEADLESS
call :RUN_SETUP_CHECK headless
pause
goto MENU

:MENU_CHECK_DESKTOP
call :RUN_SETUP_CHECK desktop
pause
goto MENU

:RUN_CHECK_FROM_ARGUMENT
set "TARGET_MODE=%~2"
if "%TARGET_MODE%"=="" set "TARGET_MODE=headless"
call :RUN_SETUP_CHECK %TARGET_MODE%
exit /b %ERRORLEVEL%

:CHECK_PREREQUISITES
set "TARGET=%~1"
echo.
echo Checking required local tools...
set "MISSING_TOOLS=0"
call :CHECK_TOOL python "Install Python 3.14 or newer from https://www.python.org/downloads/"
call :CHECK_PYTHON_VERSION
call :CHECK_TOOL uv "Install uv from https://docs.astral.sh/uv/"
if /I "%TARGET%"=="desktop" (
  call :CHECK_TOOL node "Install Node.js from https://nodejs.org/"
)

if "%MISSING_TOOLS%"=="1" (
  echo.
  echo One or more required tools are missing. Install them first, then re-run this launcher.
  exit /b 1
)

echo.
echo All required tools were found.
exit /b 0

:CHECK_TOOL
where %~1 >nul 2>nul
if errorlevel 1 (
  echo [missing] %~1
  echo           %~2
  set "MISSING_TOOLS=1"
) else (
  echo [ok] %~1
)
exit /b 0

:CHECK_PYTHON_VERSION
where python >nul 2>nul
if errorlevel 1 exit /b 0
set "PYTHON_VERSION="
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%V"
if "%PYTHON_VERSION%"=="" (
  echo [warn] Could not determine the Python version; skipping the 3.14+ check.
  exit /b 0
)
for /f "tokens=1,2 delims=." %%A in ("%PYTHON_VERSION%") do (
  set "PY_MAJOR=%%A"
  set "PY_MINOR=%%B"
)
set /a "PY_VERSION_OK=0"
if %PY_MAJOR% GTR 3 set /a "PY_VERSION_OK=1"
if %PY_MAJOR%==3 if %PY_MINOR% GEQ 14 set /a "PY_VERSION_OK=1"
if "%PY_VERSION_OK%"=="1" (
  echo [ok] python %PYTHON_VERSION%
) else (
  echo [missing] python %PYTHON_VERSION% ^(3.14 or newer required^)
  echo           Install Python 3.14 or newer from https://www.python.org/downloads/
  set "MISSING_TOOLS=1"
)
exit /b 0

:REQUIRE_TOOL
where %~1 >nul 2>nul
if errorlevel 1 (
  echo [error] Required tool not found: %~1
  echo         %~2
  exit /b 1
)
exit /b 0

:PREPARE_ENV_FILE
echo.
echo Preparing the local environment file...
call :COPY_IF_MISSING "%ROOT_DIR%\.env.example" "%ROOT_DIR%\.env"
if errorlevel 1 exit /b 1
echo.
echo Local environment file is ready. An existing .env was preserved.
exit /b 0

:COPY_IF_MISSING
set "SOURCE_FILE=%~1"
set "TARGET_FILE=%~2"
if not exist "%SOURCE_FILE%" (
  echo [error] Source file not found: %SOURCE_FILE%
  exit /b 1
)
if exist "%TARGET_FILE%" (
  echo [skip] %TARGET_FILE% already exists.
  exit /b 0
)
copy "%SOURCE_FILE%" "%TARGET_FILE%" >nul
if errorlevel 1 (
  echo [error] Could not create %TARGET_FILE%.
  exit /b 1
)
echo [created] %TARGET_FILE%
exit /b 0

:INSTALL_DEPENDENCIES
set "TARGET=%~1"
echo.
echo Installing Python dependencies...
call :REQUIRE_TOOL uv "Install uv from https://docs.astral.sh/uv/"
if errorlevel 1 exit /b 1

cd /d "%ROOT_DIR%" || exit /b 1
call uv sync --dev
if errorlevel 1 exit /b 1

if /I "%TARGET%"=="desktop" (
  echo.
  echo Installing and building the Desktop frontend...
  call :REQUIRE_TOOL node "Install Node.js from https://nodejs.org/"
  if errorlevel 1 exit /b 1
  pushd "%FRONTEND_DIR%" || exit /b 1
  call npm install
  if errorlevel 1 (
    popd
    exit /b 1
  )
  call npm run build
  if errorlevel 1 (
    popd
    exit /b 1
  )
  popd
)

echo.
echo Dependencies are installed.
exit /b 0

:RUN_DATABASE_SYNC
echo.
echo Synchronizing the database...
call :REQUIRE_TOOL uv "Install uv from https://docs.astral.sh/uv/"
if errorlevel 1 exit /b 1
cd /d "%ROOT_DIR%" || exit /b 1
call uv run orchai db sync
exit /b %ERRORLEVEL%

:VALIDATE_BOOTSTRAP
echo.
echo Validating the OrchAI CLI...
call :REQUIRE_TOOL uv "Install uv from https://docs.astral.sh/uv/"
if errorlevel 1 exit /b 1
cd /d "%ROOT_DIR%" || exit /b 1
call uv run orchai --help >nul
exit /b %ERRORLEVEL%

:RUN_SETUP_CHECK
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=headless"
if /I not "%TARGET%"=="headless" if /I not "%TARGET%"=="desktop" (
  echo [error] Unknown target mode: %TARGET% ^(expected "headless" or "desktop"^)
  exit /b 1
)
echo.
echo Target mode: %TARGET%
call :CHECK_PREREQUISITES %TARGET%
if errorlevel 1 exit /b 1
call :PREPARE_ENV_FILE
if errorlevel 1 exit /b 1
call :INSTALL_DEPENDENCIES %TARGET%
if errorlevel 1 exit /b 1
call :RUN_DATABASE_SYNC
if errorlevel 1 exit /b 1
call :VALIDATE_BOOTSTRAP
if errorlevel 1 exit /b 1
echo.
echo OrchAI setup check completed successfully.
exit /b 0

:EXIT
echo.
echo Leaving OrchAI setup launcher.
exit /b 0
