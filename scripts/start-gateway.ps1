param([int]$Port=8000)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Push-Location $root
try { & "$root/.venv/Scripts/python.exe" -m gateway --port $Port; if ($LASTEXITCODE) { throw 'Gateway failed' } } finally { Pop-Location }
