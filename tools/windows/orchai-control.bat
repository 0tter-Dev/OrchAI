@echo off
setlocal

set "TOOLS_DIR=%~dp0"
if "%TOOLS_DIR:~-1%"=="\" set "TOOLS_DIR=%TOOLS_DIR:~0,-1%"
for %%I in ("%TOOLS_DIR%\..\..") do set "ROOT_DIR=%%~fI"
set "CONTROL_SCRIPT=%ROOT_DIR%\scripts\orchai-local-process-control.ps1"

if /I "%~1"=="status" goto RUN_STATUS_FROM_ARGUMENT
if /I "%~1"=="start" goto RUN_START_FROM_ARGUMENT
if /I "%~1"=="stop" goto RUN_STOP_FROM_ARGUMENT
if /I "%~1"=="restart" goto RUN_RESTART_FROM_ARGUMENT

:MENU
cls
echo ============================================
echo              OrchAI - Control
echo ============================================
echo.
echo   [1] Check status
echo   [2] Start (headless API)
echo   [3] Start (Desktop)
echo   [4] Stop
echo   [5] Restart (same mode as last start)
echo   [0] Exit
echo.
set /p "ACTION=Choose an option: "

if "%ACTION%"=="1" goto MENU_STATUS
if "%ACTION%"=="2" goto MENU_START_API
if "%ACTION%"=="3" goto MENU_START_DESKTOP
if "%ACTION%"=="4" goto MENU_STOP
if "%ACTION%"=="5" goto MENU_RESTART
if "%ACTION%"=="0" goto EXIT

echo Unsupported option: %ACTION%
pause
goto MENU

:MENU_STATUS
call :RUN_CONTROL status
pause
goto MENU

:MENU_START_API
call :RUN_CONTROL start api
pause
goto MENU

:MENU_START_DESKTOP
call :RUN_CONTROL start desktop
pause
goto MENU

:MENU_STOP
call :RUN_CONTROL stop
pause
goto MENU

:MENU_RESTART
call :RUN_CONTROL restart
pause
goto MENU

:RUN_STATUS_FROM_ARGUMENT
call :RUN_CONTROL status
exit /b %ERRORLEVEL%

:RUN_START_FROM_ARGUMENT
call :RUN_CONTROL start %~2
exit /b %ERRORLEVEL%

:RUN_STOP_FROM_ARGUMENT
call :RUN_CONTROL stop
exit /b %ERRORLEVEL%

:RUN_RESTART_FROM_ARGUMENT
call :RUN_CONTROL restart %~2
exit /b %ERRORLEVEL%

:RUN_CONTROL
powershell -NoProfile -ExecutionPolicy Bypass -File "%CONTROL_SCRIPT%" %~1 %~2
exit /b %ERRORLEVEL%

:EXIT
echo.
echo Leaving OrchAI control launcher.
exit /b 0
