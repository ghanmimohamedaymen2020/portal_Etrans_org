# service-install.ps1
# Installe l'application comme service Windows en utilisant NSSM.
# Exécuter PowerShell en tant qu'administrateur.

param(
    [string]$AppName = 'EtransApp'
)

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppRoot = (Resolve-Path (Join-Path $ScriptRoot '..')).Path
$VenvPath = Join-Path $AppRoot '.venv'
$PythonExe = Join-Path $VenvPath 'Scripts\python.exe'
$Requirements = Join-Path $AppRoot 'requirements.txt'
$RunPy = Join-Path $AppRoot 'run.py'

function Ensure-Venv {
    if (-not (Test-Path $VenvPath)) {
        Write-Host "Création du virtualenv dans $VenvPath"
        python -m venv $VenvPath
    } else {
        Write-Host "Virtualenv trouvé : $VenvPath"
    }
}

function Ensure-Dependencies {
    if (-not (Test-Path $PythonExe)) {
        throw "Python dans venv introuvable : $PythonExe"
    }
    Write-Host "Installation des dépendances depuis $Requirements"
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r $Requirements
}

function Get-NssmPath {
    # Vérifier si nssm est déjà dans le PATH
    $n = Get-Command nssm -ErrorAction SilentlyContinue
    if ($n) { return $n.Source }

    # Sinon vérifier dossier local deploy\nssm
    $localNssm = Join-Path $ScriptRoot 'nssm.exe'
    if (Test-Path $localNssm) { return $localNssm }

    # Télécharger NSSM si absent
    $zipUrl = 'https://nssm.cc/release/nssm-2.24.zip'
    $zipFile = Join-Path $ScriptRoot 'nssm.zip'
    Write-Host "Téléchargement NSSM depuis $zipUrl"
    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
        Expand-Archive -Path $zipFile -DestinationPath $ScriptRoot -Force
        Remove-Item $zipFile -Force
        # rechercher nssm.exe dans l'archive extraite
        $found = Get-ChildItem -Path $ScriptRoot -Recurse -Filter 'nssm.exe' | Select-Object -First 1
        if ($found) { return $found.FullName }
    } catch {
        Write-Warning "Impossible de télécharger/extraire NSSM : $_"
    }
    return $null
}

function Install-Service {
    param($nssmPath)
    if (-not $nssmPath) { throw 'nssm introuvable. Installez manuellement nssm et relancez le script.' }

    Write-Host "Installation du service $AppName avec NSSM ($nssmPath)"

    & $nssmPath install $AppName $PythonExe $RunPy
    & $nssmPath set $AppName AppDirectory $AppRoot

    # Optionnel : rediriger stdout/stderr vers fichiers logs
    $logDir = Join-Path $AppRoot 'logs'
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    & $nssmPath set $AppName AppStdout (Join-Path $logDir 'stdout.log')
    & $nssmPath set $AppName AppStderr (Join-Path $logDir 'stderr.log')

    Write-Host "Démarrage du service $AppName"
    & $nssmPath start $AppName
}

# --- Exécution ---
try {
    Write-Host "AppRoot: $AppRoot"
    Ensure-Venv
    Ensure-Dependencies

    $nssm = Get-NssmPath
    if (-not $nssm) { throw 'NSSM introuvable et téléchargement échoué. Téléchargez NSSM manuellement depuis https://nssm.cc/download et placez nssm.exe dans le dossier deploy.' }

    Install-Service -nssmPath $nssm
    Write-Host "Service installé avec succès. Vérifiez les logs dans $AppRoot\logs"
} catch {
    Write-Error "Échec : $_"
    exit 1
}
