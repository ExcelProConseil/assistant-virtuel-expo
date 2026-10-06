@echo off
rem Double-clic : met a jour le logiciel avec le dernier ZIP telecharge
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0METTRE_A_JOUR.ps1"
echo.
pause
