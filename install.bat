@echo off
rem One-click install for Windows: double-click this file. Add -Core after it to skip the large analysis packages.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
