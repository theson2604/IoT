$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$compiler=Join-Path $env:USERPROFILE '.platformio/packages/toolchain-gccmingw32/bin/g++.exe'
if (!(Test-Path $compiler)) { throw 'Install: python -m platformio pkg install --global --tool platformio/toolchain-gccmingw32' }
$env:PATH="$(Split-Path $compiler);$env:PATH"
$out=Join-Path $env:TEMP 'energy-modbus-tests.exe'
& $compiler '-std=c++11' '-D__USE_MINGW_ANSI_STDIO=1' '-Wall' '-Wextra' '-Werror' "-I$root/firmware/lib/Modbus" "$root/tests/modbus_test.cpp" '-o' $out
if ($LASTEXITCODE) { throw 'Compile failed' }
& $out
if ($LASTEXITCODE) { throw 'Tests failed' }

$energyOut=Join-Path $env:TEMP 'energy-protocol-tests.exe'
& $compiler '-std=c++11' '-D__USE_MINGW_ANSI_STDIO=1' '-Wall' '-Wextra' '-Werror' "-I$root/firmware/lib/Energy" "$root/tests/energy_test.cpp" '-o' $energyOut
if ($LASTEXITCODE) { throw 'Energy tests compile failed' }
& $energyOut
if ($LASTEXITCODE) { throw 'Energy tests failed' }
