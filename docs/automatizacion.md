# Automatización y KPIs de operación (IL4)

El radar está pensado para correr solo una vez por semana: el reporte debe estar listo **antes del lunes a las 08:00 (hora de Chile)**, cuando se reúne el comité. Hay dos formas de programarlo: GitHub Actions (recomendada) o el Programador de tareas de Windows.

## Opción recomendada: GitHub Actions (`.github/workflows/radar_semanal.yml`)

- **Cuándo corre:** cada lunes a las 02:00 UTC (`cron: "0 2 * * 1"`). En Chile equivale al domingo a las 23:00 en horario de verano y a las 22:00 en invierno. También se puede lanzar a mano desde **Actions → Radar semanal → Run workflow**.
- **Qué hace:**
  1. Instala Python 3.13 y las dependencias.
  2. Ejecuta `python src/main.py` en modo normal, con descarga de Yahoo Finance.
  3. Hace commit al repositorio del reporte (`outputs/`), el log (`logs/`) y los datos actualizados (`data/`). Usa `permissions: contents: write`.
- **Si falla:** el log de la falla igual se guarda en el repositorio, el workflow queda **en rojo** y GitHub envía un correo al dueño del repositorio. No se sobrescriben los resultados de la semana anterior.
- **Para activarlo:** publicar el repositorio (`docs/despliegue.md`). Los workflows programados se activan solos en la rama principal. Conviene lanzarlo una vez a mano para verificar que funciona.
- **Riesgos conocidos:**
  - GitHub puede retrasar las corridas programadas en horas de alta demanda. Igual quedan varias horas de margen hasta las 08:00.
  - Yahoo Finance puede limitar las descargas desde servidores de GitHub. Si pasa, la corrida queda FALLIDA y el operador la relanza a mano o usa la opción local.

## Alternativa local: Programador de tareas de Windows (`scripts/programar_tarea_windows.ps1`)

Registra la tarea `RadarBurbujasIA`, que ejecuta `src\main.py --origen programada` cada domingo a las 23:00 en la hora del equipo. Si el equipo estaba apagado a esa hora, la tarea corre apenas se encienda.

```powershell
.\scripts\programar_tarea_windows.ps1                       # registrar (domingo 23:00)
.\scripts\programar_tarea_windows.ps1 -Dia Monday -Hora 06:00
Start-ScheduledTask -TaskName RadarBurbujasIA               # probar ahora
.\scripts\programar_tarea_windows.ps1 -Desregistrar         # eliminar
```

A diferencia de GitHub Actions, esta opción no hace commit: el reporte y el log quedan en la carpeta local.

## Origen de cada corrida

`main.py` acepta `--origen manual | programada | pruebas` (por defecto, `manual`). El origen queda en la línea `RESUMEN_EJECUCION` del log, junto con la hora UTC de término (`fin_utc`) y las filas descargadas (`filas`).

| Origen | Quién la lanza |
|---|---|
| `programada` | El cron de GitHub Actions o la tarea de Windows |
| `manual` | Una persona: desde la terminal o con **Run workflow** en GitHub |
| `pruebas` | `tests/test_main.py` (pytest y CI) |
| `no_registrado` | Corridas registradas antes de incorporar el campo origen al log |

## KPIs IL4 (`src/kpis.py`, se registran en el log al final de cada corrida)

| KPI | Meta | Etiqueta hoy | Cómo se mide |
|---|---|---|---|
| Tasa de corridas sin error | Tasa de fallos < 1% | MEDIDO | Líneas `RESUMEN_EJECUCION` de `logs/`, separadas por origen |
| Duración máxima y promedio | < 5 min | MEDIDO | Campo `duracion_s` del log |
| Cumplimiento del SLA | ≥ 95% de las corridas programadas | DEFINIDO | Corrida programada con estado OK y `fin_utc` (convertido a hora de Chile) el domingo o el lunes antes de las 08:00. Pasa a MEDIDO con la primera corrida programada |
| Frecuencia de uso | ≥ 1 revisión por semana | DEFINIDO | Filas de la hoja **"Registro de revisión"** de cada reporte, contadas con `python scripts/contar_revisiones.py`. Hoy no hay usuario real (comité hipotético) |

La hoja "Registro de revisión" la llena el **operador** después de cada reunión: fecha, revisor, decisión tomada y comentarios. El comité solo lee el reporte (ver `docs/gobernanza.md`). Si el reporte de una semana se regenera, las filas ya escritas se conservan.
