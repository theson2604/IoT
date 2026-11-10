param([string]$Scenario='normal',[int]$Seed=1)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Push-Location $root
try { & "$root/.venv/Scripts/python.exe" -m simulator --scenario $Scenario --seed $Seed; if ($LASTEXITCODE) { throw 'Simulator failed' } } finally { Pop-Location }
