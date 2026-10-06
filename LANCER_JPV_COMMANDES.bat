@echo off
cd /d "%~dp0"
title JPV Commandes - serveur (ne pas fermer, vous pouvez la reduire)

rem Python : "py" si present, sinon "python"
where py >nul 2>nul
if %errorlevel%==0 (set PYTHON=py -3) else (set PYTHON=python)

rem 1. Arrete une ancienne version encore ouverte (comme JPV Stock apres une mise a jour)
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>nul

rem 2. Demarre le logiciel dans sa propre fenetre (reduite)
start "JPV Commandes - serveur" /min cmd /k %PYTHON% outils\serveur.py

rem 3. Ouvre la page dans le navigateur
timeout /t 3 /nobreak >nul
start "" http://localhost:8000
exit
