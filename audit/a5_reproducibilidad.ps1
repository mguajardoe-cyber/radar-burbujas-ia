# =============================================================================
# Auditoría — 5. Reproducibilidad
# Clona el repositorio (último commit) en una carpeta temporal, crea un entorno
# limpio con Python 3.13, instala requirements.txt, corre pytest y
# src/main.py --offline, y compara el semáforo resultante con el del
# repositorio original.
# Uso: powershell -File audit\a5_reproducibilidad.ps1 -Destino <carpeta temporal>
# Salida: audit/resultados/a5_reproducibilidad.txt
# =============================================================================
param([Parameter(Mandatory = $true)][string]$Destino)

$ErrorActionPreference = "Continue"
$git = "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
$origen = (Resolve-Path "$PSScriptRoot\..").Path
$informe = Join-Path $origen "audit\resultados\a5_reproducibilidad.txt"
$clon = Join-Path $Destino "radar-burbujas-ia"

function Anotar($texto) { Write-Output $texto; Add-Content -Path $informe -Value $texto -Encoding utf8 }

if (Test-Path $clon) { Remove-Item -Recurse -Force $clon -Confirm:$false }
New-Item -ItemType Directory -Force $Destino | Out-Null
"Reproducibilidad - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $informe -Encoding utf8

$inicio = Get-Date
& $git clone -q $origen $clon
Anotar "Commit clonado: $(& $git -C $clon log --oneline -1)"

py -V:3.13 -m venv "$clon\.venv"
# Sin "pip install --upgrade pip": en Windows puede dejar a pip inutilizable en un entorno nuevo
& "$clon\.venv\Scripts\python.exe" -m pip install -q -r "$clon\requirements.txt"
Anotar "pip install exit: $LASTEXITCODE"
Anotar "Python: $(& "$clon\.venv\Scripts\python.exe" --version)"

Push-Location $clon
$pytest = & ".venv\Scripts\python.exe" -m pytest -q 2>&1 | Select-Object -Last 3
Anotar "pytest: $($pytest -join ' | ')"
$main = & ".venv\Scripts\python.exe" src\main.py --offline 2>&1 | Select-String "RESUMEN_EJECUCION"
Anotar "main.py --offline exit: $LASTEXITCODE"
Anotar "$main"
Pop-Location

$cmp = & "$origen\.venv\Scripts\python.exe" "$origen\audit\a5_comparar.py" "$origen\data\processed\semaforo_actual.csv" "$clon\data\processed\semaforo_actual.csv"
Anotar "$cmp"
Anotar "Duracion total: $([math]::Round(((Get-Date) - $inicio).TotalMinutes, 1)) min"
