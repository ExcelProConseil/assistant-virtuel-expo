# Met a jour JPV Commandes depuis le dernier ZIP telecharge (Telechargements).
# Securise : s'arrete si le ZIP est introuvable ou invalide. Tes donnees (JPV_Commandes_Donnees) ne sont jamais touchees.
$dossier = $PSScriptRoot
if (-not (Test-Path (Join-Path $dossier "outils\serveur.py"))) { Write-Host "Dossier du logiciel introuvable : $dossier"; exit 1 }
$z = Get-ChildItem (Join-Path $HOME "Downloads") -Filter "assistant-virtuel-expo*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $z) { Write-Host "Aucun fichier assistant-virtuel-expo*.zip dans Telechargements. Telecharge d'abord le ZIP, puis relance."; exit 1 }
Write-Host ("ZIP utilise : " + $z.Name + " (" + $z.LastWriteTime + ")")
$tmp = Join-Path $env:TEMP "jpv_maj"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive -LiteralPath $z.FullName -DestinationPath $tmp -Force
$nouveau = Get-ChildItem $tmp -Directory | Select-Object -First 1
if (-not $nouveau -or -not (Test-Path (Join-Path $nouveau.FullName "outils\serveur.py"))) { Write-Host "Ce ZIP ne ressemble pas a JPV Commandes. Rien n'a ete modifie."; exit 1 }
Copy-Item -Path (Join-Path $nouveau.FullName "*") -Destination $dossier -Recurse -Force
Remove-Item $tmp -Recurse -Force
Write-Host ("Mise a jour terminee. calcul.py = " + (Get-Item (Join-Path $dossier "outils\calcul.py")).Length + " octets")
