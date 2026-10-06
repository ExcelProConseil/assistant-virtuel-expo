@echo off
rem Lance JPV Commandes, puis le menu JPV-AGENT
call "%~dp0LANCER_JPV_COMMANDES.bat"
set AGENTS=C:\Users\cmore\OneDrive\Bureau\commandes clt\JPV_AGENTS.bat
if exist "%AGENTS%" (call "%AGENTS%") else (echo JPV_AGENTS.bat introuvable : %AGENTS% & pause)
