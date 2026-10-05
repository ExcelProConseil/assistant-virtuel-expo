@echo off
chcp 65001 >nul
cd /d "%~dp0"
title JPV Commandes - serveur (ne pas fermer)

where py >nul 2>nul
if %errorlevel%==0 (set PYTHON=py -3) else (set PYTHON=python)

rem 1. Le logiciel JPV Commandes (serveur local) dans sa propre fenetre
start "JPV Commandes - serveur" cmd /k %PYTHON% outils\serveur.py

rem 2. La page s'ouvre dans le navigateur apres 2 secondes
timeout /t 2 >nul
start "" http://localhost:8000

rem 3. JPV-AGENT (menu des agents) dans cette fenetre
set AGENTS=C:\Users\cmore\OneDrive\Bureau\commandes clt\JPV_AGENTS.bat
if exist "%AGENTS%" (call "%AGENTS%") else (echo JPV_AGENTS.bat introuvable : %AGENTS% & pause)
