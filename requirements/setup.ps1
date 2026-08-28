param(
    [ValidateSet('all', 'backend', 'backend-dev', 'data-processing')]
    [string]$Group = 'all'
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$setupScript = Join-Path $projectRoot 'scripts\setup_env.py'

python $setupScript --group $Group
if ($LASTEXITCODE -ne 0) {
    throw 'Cross-platform environment setup failed.'
}
