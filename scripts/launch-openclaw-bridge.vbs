Option Explicit

Dim shell
Dim command

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\Users\Jester\Desktop\Sonya"

command = """C:\Users\Jester\Desktop\Sonya\.venv\Scripts\python.exe"" -m tg_bridge.app --openclaw-root ""C:\Users\Jester\.openclaw"""
shell.Run command, 0, False
