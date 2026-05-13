param(
    [switch]$Detached,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Test-BridgeRuntimeRunning {
    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match "tg_bridge\.app"
    }
    return @($processes).Count -gt 0
}

$mutex = New-Object System.Threading.Mutex($false, "Global\SonyaTgBridgeRunner")
$mutexAcquired = $false
try {
    $mutexAcquired = $mutex.WaitOne(0, $false)
} catch [System.Threading.AbandonedMutexException] {
    $mutexAcquired = $true
}

if (-not $mutexAcquired) {
    exit 0
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$venvSitePackages = Join-Path $venvRoot "Lib\site-packages"
$runtimeSource = Join-Path $repoRoot "src"
$packageTarget = Join-Path $repoRoot "packages\tg-bridge"
$packageSource = Join-Path $packageTarget "src"
$workspaceInstalled = $false

if (-not (Test-Path $venvPython)) {
    python -m venv $venvRoot
}

if (-not (Test-Path $venvPython)) {
    throw "Python venv bootstrap failed"
}

$installed = $false
try {
    & $venvPython -c "import importlib.metadata, sys; sys.exit(0 if importlib.metadata.version('tg-bridge') else 1)" | Out-Null
    $installed = ($LASTEXITCODE -eq 0)
} catch {
    $installed = $false
}

if (-not $installed) {
    & $venvPython -m pip install -e $packageTarget | Out-Null
}

try {
    & $venvPython -c "import importlib.metadata, sys; sys.exit(0 if importlib.metadata.version('sonya-workspace') else 1)" | Out-Null
    $workspaceInstalled = ($LASTEXITCODE -eq 0)
} catch {
    $workspaceInstalled = $false
}

if (-not $workspaceInstalled) {
    & $venvPython -m pip install -e $repoRoot | Out-Null
}

$bridgeArgs = @("-m", "tg_bridge.app", "--openclaw-root", "C:\Users\Jester\.openclaw")
if ($Once) {
    $bridgeArgs += "--once"
}

$env:VIRTUAL_ENV = $venvRoot
$env:PYTHONPATH = "$runtimeSource;$packageSource;$venvSitePackages"

try {
    if ($Detached) {
        if (Test-BridgeRuntimeRunning) {
            exit 0
        }
        $argumentLine = ($bridgeArgs | ForEach-Object {
            if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
        }) -join ' '
        Start-Process -FilePath $venvPython -ArgumentList $argumentLine -WorkingDirectory $repoRoot -WindowStyle Hidden
        exit 0
    }

    & $venvPython @bridgeArgs
    exit $LASTEXITCODE
} finally {
    if ($mutexAcquired) {
        $mutex.ReleaseMutex() | Out-Null
    }
    $mutex.Dispose()
}
