param(
    [ValidateSet("status", "start", "stop", "restart")]
    [string] $Action = "status",
    [ValidateSet("api", "desktop", "")]
    [string] $Mode = ""
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$config = @{
    ORCHAI_API_HOST = "127.0.0.1"
    ORCHAI_API_PORT = "8000"
    ORCHAI_RUNTIME_DIR = "runtime"
}

function Read-OrchAIEnv {
    param([string] $Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }

        $name, $value = $trimmed.Split("=", 2)
        $key = $name.Trim().ToUpperInvariant()
        if (-not $config.ContainsKey($key)) {
            continue
        }

        $config[$key] = $value.Trim().Trim('"')
    }
}

function Read-ProcessEnvOverrides {
    foreach ($key in @($config.Keys)) {
        $value = [System.Environment]::GetEnvironmentVariable($key)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $config[$key] = $value
        }
    }
}

function Resolve-OrchAIPath {
    param([string] $Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return [System.IO.Path]::GetFullPath((Join-Path $RootDir $Path))
}

function Require-Tool {
    param(
        [string] $Name,
        [string] $Hint
    )

    if ($null -eq (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Host "[error] Required tool not found: $Name"
        Write-Host "        $Hint"
        exit 1
    }
}

function Get-TrackedPid {
    if (-not (Test-Path -LiteralPath $pidFile)) {
        return $null
    }

    $rawPid = (Get-Content -LiteralPath $pidFile -TotalCount 1).Trim()
    $pidValue = 0
    if (-not [int]::TryParse($rawPid, [ref] $pidValue)) {
        return $null
    }

    return $pidValue
}

function Get-TrackedProcess {
    param([int] $ProcessId)

    return Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
}

function Get-TrackedMetadata {
    if (-not (Test-Path -LiteralPath $metadataFile)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $metadataFile -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Test-OwnedProcess {
    param([int] $ProcessId)

    $process = Get-TrackedProcess -ProcessId $ProcessId
    if ($null -eq $process) {
        return $false
    }

    $metadata = Get-TrackedMetadata
    if ($null -eq $metadata) {
        return $false
    }

    $startedAtUtc = $process.StartTime.ToUniversalTime().ToString("o")
    if ($metadata.pid -ne $ProcessId) {
        return $false
    }

    if ($metadata.processName -ne $process.ProcessName) {
        return $false
    }

    if ($metadata.startedAtUtc -ne $startedAtUtc) {
        return $false
    }

    return $true
}

function Write-ProcessMetadata {
    param(
        [System.Diagnostics.Process] $Process,
        [string] $ProcessMode,
        [string] $Port
    )

    $metadata = [ordered]@{
        pid = $Process.Id
        processName = $Process.ProcessName
        startedAtUtc = $Process.StartTime.ToUniversalTime().ToString("o")
        mode = $ProcessMode
        port = $Port
    }
    $metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataFile -Encoding ascii
}

function Get-ListeningPid {
    param([string] $Port)

    $portNumber = [int]$Port
    $connections = Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue
    if ($null -ne $connections) {
        $owners = @($connections | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 0 })
        if ($owners.Count -gt 0) {
            return [int]$owners[0]
        }
    }

    $netstatLines = netstat -ano | Select-String ":$Port\s"
    foreach ($line in $netstatLines) {
        $parts = ($line.ToString() -split "\s+") | Where-Object { $_ }
        if ($parts.Count -ge 5 -and $parts[3] -eq "LISTENING" -and $parts[4] -match "^\d+$") {
            return [int]$parts[4]
        }
    }

    return $null
}

function Write-ServiceCommand {
    param(
        [string] $Path,
        [string[]] $Lines
    )

    $content = @(
        "@echo off",
        "cd /d `"$RootDir`""
    ) + $Lines
    Set-Content -LiteralPath $Path -Value $content -Encoding ascii
}

function Write-TrackedStatus {
    $trackedPid = Get-TrackedPid
    if ($null -eq $trackedPid) {
        Write-Host "[stopped] OrchAI"
        return $true
    }

    $process = Get-TrackedProcess -ProcessId $trackedPid
    if ($null -eq $process) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $metadataFile -Force -ErrorAction SilentlyContinue
        Write-Host "[stopped] OrchAI (removed stale pid $trackedPid)"
        return $true
    }

    if (-not (Test-OwnedProcess -ProcessId $trackedPid)) {
        Write-Host "[unmanaged] OrchAI pid $trackedPid was not started by orchai-control; leaving pid file untouched."
        return $false
    }

    $metadata = Get-TrackedMetadata
    $modeLabel = if ($null -ne $metadata) { $metadata.mode } else { "unknown" }
    Write-Host "[running] OrchAI ($modeLabel mode, pid $trackedPid)"
    return $true
}

function Stop-TrackedProcess {
    $trackedPid = Get-TrackedPid
    if ($null -eq $trackedPid) {
        Write-Host "[stopped] OrchAI"
        return $true
    }

    $process = Get-TrackedProcess -ProcessId $trackedPid
    if ($null -eq $process) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $metadataFile -Force -ErrorAction SilentlyContinue
        Write-Host "[stopped] OrchAI (removed stale pid $trackedPid)"
        return $true
    }

    if (-not (Test-OwnedProcess -ProcessId $trackedPid)) {
        Write-Host "[blocked] OrchAI pid $trackedPid was not started by orchai-control. Stop it manually if needed."
        return $false
    }

    Write-Host "Stopping OrchAI pid $trackedPid ..."
    & taskkill /PID $trackedPid /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[error] Could not stop OrchAI pid $trackedPid."
        return $false
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $metadataFile -Force -ErrorAction SilentlyContinue
    Write-Host "[stopped] OrchAI"
    return $true
}

function Start-ApiProcess {
    Require-Tool -Name "uv" -Hint "Install uv from https://docs.astral.sh/uv/"

    $trackedPid = Get-TrackedPid
    if ($null -ne $trackedPid -and (Test-OwnedProcess -ProcessId $trackedPid)) {
        Write-Host "[running] OrchAI already tracked at pid $trackedPid."
        return $true
    }
    if ($null -ne $trackedPid -and $null -eq (Get-TrackedProcess -ProcessId $trackedPid)) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $metadataFile -Force -ErrorAction SilentlyContinue
    }

    $port = $config.ORCHAI_API_PORT
    $existingListeningPid = Get-ListeningPid -Port $port
    if ($null -ne $existingListeningPid) {
        Write-Host "[blocked] API port $port is already in use by pid $existingListeningPid."
        Write-Host "          orchai-control will not track or stop a process it did not start."
        return $false
    }

    Write-Host "Starting OrchAI (headless API) ..."
    Remove-Item -LiteralPath $apiLogFile -Force -ErrorAction SilentlyContinue
    Write-ServiceCommand -Path $apiCommandFile -Lines @(
        "uv run orchai api serve --host $($config.ORCHAI_API_HOST) --port $port >> `"$apiLogFile`" 2>&1"
    )
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = "cmd.exe"
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
    $escapedCommandFile = $apiCommandFile.Replace('"', '""')
    $startInfo.Arguments = '/d /s /c "{0}"' -f $escapedCommandFile
    [System.Diagnostics.Process]::Start($startInfo) | Out-Null

    $deadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 500
        $listeningPid = Get-ListeningPid -Port $port
        if ($null -ne $listeningPid) {
            $serviceProcess = Get-TrackedProcess -ProcessId $listeningPid
            if ($null -ne $serviceProcess) {
                Set-Content -LiteralPath $pidFile -Value $listeningPid -Encoding ascii
                Write-ProcessMetadata -Process $serviceProcess -ProcessMode "api" -Port $port
                Write-Host "[started] OrchAI API pid $listeningPid, listening on http://$($config.ORCHAI_API_HOST):$port"
                return $true
            }
        }
    } while ((Get-Date) -lt $deadline)

    Write-Host "[error] OrchAI API did not start listening on port $port."
    Write-Host "        See $apiLogFile for startup output."
    return $false
}

function Start-DesktopProcess {
    Require-Tool -Name "uv" -Hint "Install uv from https://docs.astral.sh/uv/"

    $trackedPid = Get-TrackedPid
    if ($null -ne $trackedPid -and (Test-OwnedProcess -ProcessId $trackedPid)) {
        Write-Host "[running] OrchAI already tracked at pid $trackedPid."
        return $true
    }
    if ($null -ne $trackedPid -and $null -eq (Get-TrackedProcess -ProcessId $trackedPid)) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $metadataFile -Force -ErrorAction SilentlyContinue
    }

    Write-Host "Starting OrchAI (Desktop shell) ..."
    Remove-Item -LiteralPath $desktopLogFile -Force -ErrorAction SilentlyContinue
    Write-ServiceCommand -Path $desktopCommandFile -Lines @(
        "uv run --extra desktop python -m apps.desktop.shell.main >> `"$desktopLogFile`" 2>&1"
    )
    # The Desktop shell opens its own visible pywebview window -- unlike
    # the headless API, there is no fixed configured port to poll for
    # readiness (server_runner.py binds a free 127.0.0.1 port at
    # runtime), so the tracked pid is captured directly from the
    # launched process instead of by observing a listening socket.
    # WindowStyle must stay Normal, not Hidden/Minimized: pywebview's
    # WebView2 control requires its window to actually initialize on the
    # UI thread, and a hidden/minimized parent console show-state hint
    # was observed (during manual testing) to break that initialization
    # with COM threading errors -- confirmed by comparing against a
    # direct (non-wrapped) launch, which had no such errors.
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = "cmd.exe"
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Normal
    $escapedCommandFile = $desktopCommandFile.Replace('"', '""')
    $startInfo.Arguments = '/d /s /c "{0}"' -f $escapedCommandFile
    $process = [System.Diagnostics.Process]::Start($startInfo)

    Start-Sleep -Milliseconds 500
    $trackedProcess = Get-TrackedProcess -ProcessId $process.Id
    if ($null -eq $trackedProcess) {
        Write-Host "[error] OrchAI Desktop shell exited immediately."
        Write-Host "        See $desktopLogFile for startup output."
        return $false
    }

    Set-Content -LiteralPath $pidFile -Value $trackedProcess.Id -Encoding ascii
    Write-ProcessMetadata -Process $trackedProcess -ProcessMode "desktop" -Port ""
    Write-Host "[started] OrchAI Desktop shell pid $($trackedProcess.Id)"
    return $true
}

function Start-ProcessForMode {
    param([string] $StartMode)

    switch ($StartMode) {
        "api" { return Start-ApiProcess }
        "desktop" { return Start-DesktopProcess }
        default {
            Write-Host "[error] Mode is required for start (api|desktop)."
            Write-Host "        Usage: orchai-control.bat start api|desktop"
            return $false
        }
    }
}

Read-OrchAIEnv -Path (Join-Path $RootDir ".env")
Read-ProcessEnvOverrides

$runtimeDir = Resolve-OrchAIPath -Path $config.ORCHAI_RUNTIME_DIR
$pidFile = Join-Path $runtimeDir "orchai.pid"
$metadataFile = Join-Path $runtimeDir "orchai.json"
$apiCommandFile = Join-Path $runtimeDir "orchai-api-control.cmd"
$apiLogFile = Join-Path $runtimeDir "orchai-api.log"
$desktopCommandFile = Join-Path $runtimeDir "orchai-desktop-control.cmd"
$desktopLogFile = Join-Path $runtimeDir "orchai-desktop.log"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

switch ($Action) {
    "status" {
        Write-Host ""
        Write-Host "OrchAI local process status"
        Write-Host "Runtime directory: $runtimeDir"
        if (-not (Write-TrackedStatus)) {
            exit 1
        }
    }
    "start" {
        if (-not (Start-ProcessForMode -StartMode $Mode)) {
            exit 1
        }
    }
    "stop" {
        if (-not (Stop-TrackedProcess)) {
            exit 1
        }
    }
    "restart" {
        $restartMode = $Mode
        if ([string]::IsNullOrWhiteSpace($restartMode)) {
            $metadata = Get-TrackedMetadata
            if ($null -ne $metadata -and -not [string]::IsNullOrWhiteSpace($metadata.mode)) {
                $restartMode = $metadata.mode
            }
        }
        if ([string]::IsNullOrWhiteSpace($restartMode)) {
            Write-Host "[error] Mode is required for restart when nothing was previously tracked (api|desktop)."
            Write-Host "        Usage: orchai-control.bat restart api|desktop"
            exit 1
        }

        if (-not (Stop-TrackedProcess)) {
            exit 1
        }
        if (-not (Start-ProcessForMode -StartMode $restartMode)) {
            exit 1
        }
    }
}
