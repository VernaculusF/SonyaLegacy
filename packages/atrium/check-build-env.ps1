# Atrium build-environment checker.
# Tells you exactly what is installed and what is missing to build the .exe.
# Run:  powershell -ExecutionPolicy Bypass -File check-build-env.ps1

Write-Host "=== Atrium .exe build environment ===" -ForegroundColor Cyan
$ok = $true

function Check($name, $cmd, $hint) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) {
        $ver = & $cmd --version 2>$null | Select-Object -First 1
        Write-Host ("  [OK]   {0}: {1}" -f $name, $ver) -ForegroundColor Green
    } else {
        Write-Host ("  [MISS] {0} - {1}" -f $name, $hint) -ForegroundColor Yellow
        $script:ok = $false
    }
}

Check "Node"  "node"  "https://nodejs.org (need 18+)"
Check "Rust (cargo)" "cargo" "https://rustup.rs"
Check "rustc" "rustc" "installed together with rustup"

# MSVC linker
$link = Get-ChildItem "C:\Program Files*\Microsoft Visual Studio" -Recurse -Filter link.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if ($link) {
    Write-Host ("  [OK]   MSVC linker: {0}" -f $link.FullName) -ForegroundColor Green
} else {
    Write-Host "  [MISS] MSVC C++ Build Tools - 'Build Tools for Visual Studio' -> workload 'Desktop development with C++'" -ForegroundColor Yellow
    $ok = $false
}

# WebView2
$wv = Test-Path "C:\Program Files (x86)\Microsoft\EdgeWebView\Application"
$edge = Test-Path "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if ($wv -or $edge) {
    Write-Host "  [OK]   WebView2 runtime (or Edge) present" -ForegroundColor Green
} else {
    Write-Host "  [MISS] WebView2 Runtime - https://developer.microsoft.com/microsoft-edge/webview2/ (Evergreen)" -ForegroundColor Yellow
    $ok = $false
}

# Icons
if (Test-Path "src-tauri\icons\icon.ico") {
    Write-Host "  [OK]   Tauri icons present" -ForegroundColor Green
} else {
    Write-Host "  [MISS] icons - run: python src-tauri\gen_icons.py" -ForegroundColor Yellow
    $ok = $false
}

# node_modules
if (Test-Path "node_modules\@pixiv\three-vrm") {
    Write-Host "  [OK]   npm deps installed" -ForegroundColor Green
} else {
    Write-Host "  [MISS] npm deps - run: npm install" -ForegroundColor Yellow
    $ok = $false
}

Write-Host ""
if ($ok) {
    Write-Host "All set. Build with:  npm run tauri:build" -ForegroundColor Green
} else {
    Write-Host "Install the [MISS] items above, then run this script again." -ForegroundColor Yellow
}
