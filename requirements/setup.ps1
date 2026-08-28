param(
    [ValidateSet('all', 'backend', 'data-processing')]
    [string]$Group = 'all'
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvRoot = Join-Path $projectRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to create the shared Python virtual environment.'
    }
}

$pipCache = Join-Path $venvRoot '.pip-cache'
$pipTemp = Join-Path $venvRoot '.tmp'
New-Item -ItemType Directory -Path $pipCache -Force | Out-Null
New-Item -ItemType Directory -Path $pipTemp -Force | Out-Null
$normalizedCache = $pipCache.Replace('\', '/')
$pipConfig = "[global]`nindex-url = https://pypi.org/simple`ncache-dir = $normalizedCache`ndisable-pip-version-check = true`n"
Set-Content -LiteralPath (Join-Path $venvRoot 'pip.ini') -Value $pipConfig -Encoding utf8
$env:TEMP = $pipTemp
$env:TMP = $pipTemp

$requirementFiles = switch ($Group) {
    'backend' { @('backend.txt') }
    'data-processing' { @('data-processing.txt') }
    default { @('backend.txt', 'data-processing.txt') }
}

Push-Location $projectRoot
try {
    foreach ($requirementFile in $requirementFiles) {
        & $venvPython -m pip install -r (Join-Path $PSScriptRoot $requirementFile)
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install dependency group from $requirementFile."
        }
    }
}
finally {
    Pop-Location
}
