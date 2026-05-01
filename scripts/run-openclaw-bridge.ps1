$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$packageTarget = Join-Path $repoRoot "packages\telegram-userbot"

if (-not (Test-Path $venvPython)) {
    python -m venv (Join-Path $repoRoot ".venv")
}

if (-not (Test-Path $venvPython)) {
    throw "Python venv bootstrap failed"
}

$installed = $false
try {
    & $venvPython -c "import importlib.metadata; import sys; sys.exit(0 if importlib.metadata.version('telegram-userbot') else 1)" | Out-Null
    $installed = ($LASTEXITCODE -eq 0)
} catch {
    $installed = $false
}

if (-not $installed) {
    & $venvPython -m pip install -e $packageTarget | Out-Null
}

$bridgeArgs = @("-m", "telegram_userbot.app", "--openclaw-root", "C:\Users\Jester\.openclaw")
if ($args -contains "-Once") {
    $bridgeArgs += "--once"
}

& $venvPython @bridgeArgs
exit $LASTEXITCODE
