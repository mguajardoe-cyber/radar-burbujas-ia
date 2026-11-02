# =============================================================================
# Capa 6 — Mantenimiento: ejecución semanal en el Programador de tareas de Windows
#
# Propósito: alternativa local a GitHub Actions (.github/workflows/radar_semanal.yml).
#   Registra una tarea que ejecuta src/main.py (modo normal, origen "programada")
#   cada domingo a las 23:00 en la hora del equipo, para que el reporte esté
#   listo antes de la reunión del lunes a las 08:00. Si el equipo estaba
#   apagado, la tarea corre apenas se encienda (StartWhenAvailable).
#
# Entradas: .venv\Scripts\python.exe y src\main.py del proyecto (rutas relativas
#   a la carpeta de este script).
# Salidas: tarea "RadarBurbujasIA" en el Programador de tareas. Cada corrida
#   escribe su log en logs\ y su reporte en outputs\ (no hace commit a Git).
#
# Uso (PowerShell, desde la carpeta del proyecto):
#   .\scripts\programar_tarea_windows.ps1                      # registra la tarea
#   .\scripts\programar_tarea_windows.ps1 -Dia Monday -Hora 06:00
#   .\scripts\programar_tarea_windows.ps1 -Desregistrar        # la elimina
#   Start-ScheduledTask -TaskName RadarBurbujasIA              # prueba inmediata
# =============================================================================

param(
    [string]$NombreTarea = "RadarBurbujasIA",
    [ValidateSet("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")]
    [string]$Dia = "Sunday",
    [string]$Hora = "23:00",
    [switch]$Desregistrar
)

$ErrorActionPreference = "Stop"

if ($Desregistrar) {
    Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false
    Write-Host "Tarea '$NombreTarea' eliminada."
    return
}

$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "No se encontró $python. Cree el entorno virtual antes (ver README, 'Cómo instalar y ejecutar')."
}

$accion = New-ScheduledTaskAction -Execute $python -Argument "src\main.py --origen programada" -WorkingDirectory $raiz
$disparador = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dia -At $Hora
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $NombreTarea -Action $accion -Trigger $disparador -Settings $ajustes `
    -Description "Radar de Burbujas IA: ejecución semanal de src/main.py (reporte listo antes del lunes 08:00)." | Out-Null

Write-Host "Tarea '$NombreTarea' registrada: cada $Dia a las $Hora (hora del equipo)."
Write-Host "Revise el resultado en logs\ después de la primera corrida."
