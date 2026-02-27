# set-env.ps1
# Charge les variables depuis le fichier .env et les enregistre en variables d'environnement Machine.
# Exécuter PowerShell en tant qu'administrateur.

$envFile = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path $envFile)) {
    Write-Error "Fichier introuvable : $envFile"
    exit 1
}

Write-Host "Lecture de : $envFile"

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq '' -or $line.StartsWith('#')) { return }
    $idx = $line.IndexOf('=')
    if ($idx -lt 0) { return }
    $name = $line.Substring(0,$idx).Trim()
    $value = $line.Substring($idx+1).Trim()
    try {
        [System.Environment]::SetEnvironmentVariable($name, $value, 'Machine')
        Write-Host "Set Machine env: $name"
    } catch {
        Write-Warning "Impossible de définir $name : $_"
    }
}

Write-Host "Terminé. Redémarrez les services ou le serveur si nécessaire pour que les changements prennent effet."