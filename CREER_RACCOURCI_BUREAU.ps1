# Cree le bouton "JPV Commandes" sur le Bureau (dans tous les dossiers Bureau de l'utilisateur)
$dossier = $PSScriptRoot
$cible = Join-Path $dossier "LANCER_JPV_COMMANDES.bat"
$bureaux = @([Environment]::GetFolderPath('Desktop'), (Join-Path $HOME 'Desktop'), (Join-Path $HOME 'OneDrive\Bureau')) |
    Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
foreach ($b in $bureaux) {
    $lnk = Join-Path $b "JPV Commandes.lnk"
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $s.TargetPath = $cible
    $s.WorkingDirectory = $dossier
    $s.IconLocation = "$env:SystemRoot\System32\imageres.dll,109"
    $s.Description = "JPV Commandes"
    $s.Save()
    Write-Host ("Bouton cree : " + $lnk)
}
