Option Explicit

Dim shell
Dim repoRoot

Set shell = CreateObject("WScript.Shell")
repoRoot = "C:\Users\Jester\Desktop\Sonya"
shell.CurrentDirectory = repoRoot

shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & repoRoot & "\scripts\run-openclaw-bridge.ps1"" -Detached", 0, False
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & repoRoot & "\scripts\run-openclaw-worker.ps1"" -Detached", 0, False
