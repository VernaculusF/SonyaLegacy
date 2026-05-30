# Start the local TTS server. Listens on 127.0.0.1:8878 by default.
#
# Run: powershell -File services\tts\start_tts.ps1
# Or just double-click after setup.ps1 finished once.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"
$py = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $py)) {
  Write-Host "[error] venv not found: $py"
  Write-Host "[error] run services\tts\setup.ps1 first."
  exit 1
}

# Optional env overrides:
#   $env:TTS_VOICE = "kseniya"   # baya|aidar|kseniya|xenia|eugene
#   $env:TTS_PORT  = "8878"
& $py (Join-Path $root "server.py")
