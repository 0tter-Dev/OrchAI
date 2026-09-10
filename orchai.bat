@echo off
setlocal

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "TOOLS_DIR=%ROOT_DIR%\tools\windows"
set "SETUP_LAUNCHER=%TOOLS_DIR%\orchai-setup.bat"
set "CONTROL_LAUNCHER=%TOOLS_DIR%\orchai-control.bat"

:MENU
cls
echo ============================================
echo                   OrchAI
echo ============================================
echo.
echo   [1] Run checks and start OrchAI (headless API)
echo   [2] Run checks and start OrchAI (Desktop)
echo   [3] Open API docs in browser
echo   [4] Go to Setup menu
echo   [5] Go to Control menu
echo   [0] Exit
echo.
set /p "ACTION=Choose an option: "

if "%ACTION%"=="1" goto MENU_CHECK_AND_START_API
if "%ACTION%"=="2" goto MENU_CHECK_AND_START_DESKTOP
if "%ACTION%"=="3" goto MENU_OPEN_BROWSER
if "%ACTION%"=="4" goto MENU_SETUP
if "%ACTION%"=="5" goto MENU_CONTROL
if "%ACTION%"=="0" goto EXIT

echo Unsupported option: %ACTION%
pause
goto MENU

:MENU_CHECK_AND_START_API
call "%SETUP_LAUNCHER%" check headless
if errorlevel 1 (
  echo.
  echo OrchAI setup checks failed. Fix the reported issue and try again.
  pause
  goto MENU
)
call "%CONTROL_LAUNCHER%" start api
pause
goto MENU

:MENU_CHECK_AND_START_DESKTOP
call "%SETUP_LAUNCHER%" check desktop
if errorlevel 1 (
  echo.
  echo OrchAI setup checks failed. Fix the reported issue and try again.
  pause
  goto MENU
)
call "%CONTROL_LAUNCHER%" start desktop
pause
goto MENU

:MENU_OPEN_BROWSER
call :OPEN_BROWSER
pause
goto MENU

:MENU_SETUP
call "%SETUP_LAUNCHER%"
goto MENU

:MENU_CONTROL
call "%CONTROL_LAUNCHER%"
goto MENU

:OPEN_BROWSER
call :RESOLVE_API_URL
echo.
echo Opening OrchAI API docs at %API_URL%
start "" "%API_URL%"
exit /b 0

:RESOLVE_API_URL
set "API_HOST=%ORCHAI_API_HOST%"
if "%API_HOST%"=="" call :READ_ENV_VALUE ORCHAI_API_HOST API_HOST
if "%API_HOST%"=="" set "API_HOST=127.0.0.1"

set "API_PORT=%ORCHAI_API_PORT%"
if "%API_PORT%"=="" call :READ_ENV_VALUE ORCHAI_API_PORT API_PORT
if "%API_PORT%"=="" set "API_PORT=8000"

set "API_URL=http://%API_HOST%:%API_PORT%/docs"
exit /b 0

:READ_ENV_VALUE
set "ENV_KEY=%~1"
set "ENV_TARGET=%~2"
if not exist "%ROOT_DIR%\.env" exit /b 0
for /f "usebackq tokens=1,* delims==" %%A in ("%ROOT_DIR%\.env") do (
  if /I "%%A"=="%ENV_KEY%" set "%ENV_TARGET%=%%B"
)
exit /b 0

:EXIT
echo.
echo Leaving OrchAI launcher.
exit /b 0
