param([switch]$Update)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$compiler=Join-Path $env:USERPROFILE '.platformio/packages/toolchain-gccmingw32/bin/g++.exe'
$env:PATH="$(Split-Path $compiler);$env:PATH"
$out=Join-Path $env:TEMP 'energy-wire-vectors.exe'
& $compiler '-std=c++11' '-D__USE_MINGW_ANSI_STDIO=1' '-Wall' '-Wextra' '-Werror' "-I$root/firmware/lib/Energy" "$root/tests/wire_vectors.cpp" '-o' $out
if ($LASTEXITCODE) { throw 'Vector compilation failed' }
$actual=(& $out) -join "`n"
if ($LASTEXITCODE) { throw 'Vector generation failed' }
$fixture=Join-Path $root 'tests/fixtures/firmware-vectors.json'
if ($Update) { [IO.File]::WriteAllText($fixture,$actual+"`n",[Text.UTF8Encoding]::new($false)) }
if (([IO.File]::ReadAllText($fixture).Replace("`r`n","`n").Trim()) -cne $actual.Trim()) { throw 'Firmware/Python wire vectors differ' }
Write-Output 'PASS: firmware-generated wire vectors match Python fixture'
