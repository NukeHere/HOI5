$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing game interpreter: $python"
}
$basePython = & $python -c 'import sys; print(sys._base_executable)'
if ($LASTEXITCODE -ne 0 -or -not $basePython) {
    throw 'Could not locate the base Python executable.'
}
$preferences = 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences'
New-Item -Path $preferences -Force | Out-Null
foreach ($exe in (@($python, $basePython) | Select-Object -Unique)) {
    $previous = Get-ItemPropertyValue -LiteralPath $preferences -Name $exe -ErrorAction SilentlyContinue
    $value = ([string]$previous -replace '(?i)GpuPreference=[^;]*;?', '').Trim(';')
    if ($value) { $value += ';' }
    New-ItemProperty -LiteralPath $preferences -Name $exe -Value ($value + 'GpuPreference=2;') -PropertyType String -Force | Out-Null
}
Push-Location -LiteralPath $PSScriptRoot
try { & $python (Join-Path $PSScriptRoot 'MainMenu.py') }
finally { Pop-Location }
