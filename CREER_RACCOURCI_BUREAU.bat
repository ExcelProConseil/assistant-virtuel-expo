@echo off
rem Cree le bouton "JPV Commandes" sur le Bureau (a faire une seule fois, par double-clic)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0CREER_RACCOURCI_BUREAU.ps1"
echo.
pause
