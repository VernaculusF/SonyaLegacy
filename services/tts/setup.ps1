# One-time setup for the local TTS service. Creates a venv next to this
# file (services\tts\.venv) and installs torch+aiohttp.
#
# Run once: powershell -File services\tts\setup.ps1
# Then start with: services\tts\start_tts.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"

Write-Host "[setup] TTS service venv: $venv"

if (-not (Test-Path $venv)) {
  Write-Host "[setup] creating venv..."
  python -m venv $venv
}

$py = Join-Path $venv "Scripts\python.exe"

Write-Host "[setup] upgrading pip..."
& $py -m pip install --upgrade pip wheel setuptools

Write-Host "[setup] installing torch + deps (this can take a few minutes)..."
& $py -m pip install -r (Join-Path $root "requirements.txt")

Write-Host "[setup] downloading Silero v4_ru model (warmup)..."
& $py -c "import torch; torch.hub.set_dir(r'$root\.cache'); m,_ = torch.hub.load(repo_or_dir='snakers4/silero-models', model='silero_tts', language='ru', speaker='v4_ru', trust_repo=True); print('voices:', m.speakers)"

Write-Host "[setup] done. Start the server with services\tts\start_tts.ps1"
