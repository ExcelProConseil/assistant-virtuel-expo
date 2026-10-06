@echo off
rem Cree le bouton "JPV Commandes" sur le Bureau (a faire une seule fois, par double-clic)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\JPV Commandes.lnk'); $s.TargetPath='%~dp0LANCER_JPV_COMMANDES.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\imageres.dll,109'; $s.WindowStyle=7; $s.Description='JPV Commandes'; $s.Save(); Write-Host ('Bouton cree sur : ' + $d)"
echo.
echo Le bouton "JPV Commandes" est maintenant sur votre Bureau.
pause
