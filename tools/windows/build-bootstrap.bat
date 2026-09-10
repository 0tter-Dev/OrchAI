@echo off
setlocal

set "TOOLS_DIR=%~dp0"
if "%TOOLS_DIR:~-1%"=="\" set "TOOLS_DIR=%TOOLS_DIR:~0,-1%"
for %%I in ("%TOOLS_DIR%\..\..") do set "ROOT_DIR=%%~fI"

set "PROJECT_FILE=%TOOLS_DIR%\bootstrap\OrchAI.Bootstrap.csproj"
set "OUTPUT_DIR=%ROOT_DIR%\dist\windows"

if /I "%~1"=="check" goto CHECK_ONLY

:BUILD
call :CHECK_DOTNET
if errorlevel 1 exit /b 1

if not exist "%PROJECT_FILE%" (
  echo [error] Bootstrap project not found: %PROJECT_FILE%
  exit /b 1
)

echo.
echo Building OrchAI Windows bootstrap executable...
echo Project: %PROJECT_FILE%
echo Output:  %OUTPUT_DIR%

call dotnet publish "%PROJECT_FILE%" --configuration Release --runtime win-x64 --output "%OUTPUT_DIR%"
if errorlevel 1 exit /b %ERRORLEVEL%

if not exist "%OUTPUT_DIR%\orchai-bootstrap.exe" (
  echo [error] Build completed but orchai-bootstrap.exe was not found.
  exit /b 1
)

echo.
echo [ok] Bootstrap executable created at:
echo      %OUTPUT_DIR%\orchai-bootstrap.exe
exit /b 0

:CHECK_ONLY
call :CHECK_DOTNET
if errorlevel 1 exit /b 1
if not exist "%PROJECT_FILE%" (
  echo [error] Bootstrap project not found: %PROJECT_FILE%
  exit /b 1
)
echo [ok] Bootstrap build prerequisites are available.
exit /b 0

:CHECK_DOTNET
where dotnet >nul 2>nul
if errorlevel 1 (
  echo [error] Required tool not found: dotnet
  echo         Install the .NET SDK before building the bootstrap executable.
  exit /b 1
)
exit /b 0
