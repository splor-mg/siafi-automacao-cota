@echo off
setlocal

:: %~dp0 já termina com barra — passa o caminho completo do script diretamente
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0robo.ps1"
set PS_EXIT=%ERRORLEVEL%

pause
exit /b %PS_EXIT%
