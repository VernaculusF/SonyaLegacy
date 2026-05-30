# One-time setup for the local Piper TTS service.
# Creates a venv next to this file and downloads voice models.
#
# Run once: powershell -ExecutionPolicy Bypass -File services\tts\setup.ps1
# Then start with: services\tts\start_tts.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"
$cache = Join-Path $root ".cache\piper"

Write-Host "[setup] TTS service venv: $venv"
if (-not (Test-Path $venv)) {
  Write-Host "[setup] creating venv..."
  python -m venv $venv
}

$py = Join-Path $venv "Scripts\python.exe"

Write-Host "[setup] upgrading pip..."
& $py -m pip install --upgrade pip wheel setuptools

Write-Host "[setup] installing piper-tts + onnxruntime..."
& $py -m pip install -r (Join-Path $root "requirements.txt")

# Download voice models. Recommended: irina (female, primary). Optionally denis (male).
New-Item -ItemType Directory -Force -Path $cache | Out-Null

$voices = @(
  @{ name = "ru_RU-irina-medium";  required = $true  },
  @{ name = "ru_RU-denis-medium";  required = $false },
  @{ name = "ru_RU-ruslan-medium"; required = $false }
)

# Piper-voices repo lays voices under ru/ru_RU/<voice>/<quality>/.
function _resolveBasePath($voiceShort) {
  # ru_RU-irina-medium → ru/ru_RU/irina/medium
  $parts = $voiceShort -split "-"
  if ($parts.Length -lt 3) { return $null }
  $locale = $parts[0]
  $speaker = $parts[1]
  $quality = $parts[2]
  return "ru/$locale/$speaker/$quality"
}

foreach ($v in $voices) {
  $name = $v.name
  $base = _resolveBasePath $name
  if (-not $base) { continue }
  $modelPath = Join-Path $cache "$name.onnx"
  $cfgPath = "$modelPath.json"
  if ((Test-Path $modelPath) -and (Test-Path $cfgPath)) {
    Write-Host "[setup] $name already present, skipping"
    continue
  }
  $url1 = "https://huggingface.co/rhasspy/piper-voices/resolve/main/$base/$name.onnx"
  $url2 = "https://huggingface.co/rhasspy/piper-voices/resolve/main/$base/$name.onnx.json"
  Write-Host "[setup] downloading $name ..."
  try {
    Invoke-WebRequest -Uri $url1 -OutFile $modelPath -UseBasicParsing
    Invoke-WebRequest -Uri $url2 -OutFile $cfgPath -UseBasicParsing
    Write-Host "[setup]   $name OK"
  } catch {
    if ($v.required) {
      Write-Host "[setup] FAILED to download $name (required): $_"
      exit 1
    } else {
      Write-Host "[setup] $name not available, skipping (optional)"
    }
  }
}

Write-Host "[setup] done. Start the server with services\tts\start_tts.ps1"
