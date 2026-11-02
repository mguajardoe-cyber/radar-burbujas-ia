# Gobernanza del Radar de Burbujas IA (Capas 5 y 6)

Cómo se opera, quién responde y cómo se mantiene el producto.

**Nota:** el usuario es hipotético. En el proyecto, el autor cumple los roles de dueño, operador y soporte. La tabla dice qué haría cada rol en una operación real.

## 1. Roles

| Rol | Quién (proyecto / operación real) | Responsabilidades |
|---|---|---|
| **Dueño del producto** | Autor / jefe de renta variable extranjera | Define el universo, los parámetros y las metas de los KPIs. Aprueba cualquier cambio de metodología, y cada decisión queda en el registro de decisiones de `docs/metodologia.md`. Revisa los KPIs cada trimestre. |
| **Operador** | Autor / analista del equipo | Verifica cada lunes antes de las 08:00 que la corrida programada terminó en verde. Si falló, la relanza a mano. Revisa las alertas de deriva del log. Envía el reporte al comité y, después de la reunión, anota la revisión en la hoja "Registro de revisión". |
| **Consumidor** | Comité de inversiones (hipotético) | Lee el reporte semanal y decide mantener, reducir o cubrir la exposición. Reporta dudas o inconsistencias por el canal de feedback. |
| **Soporte** | Autor / equipo de datos | Atiende fallas del pipeline, errores de datos y consultas. Mantiene el código, las pruebas y el CI. |

## 2. Accesos

| Recurso | Dueño y soporte | Operador | Comité |
|---|---|---|---|
| Repositorio privado en GitHub (código, datos, logs) | Escritura | Escritura (lanzar el workflow, anotar revisiones) | Sin acceso |
| Reporte Excel semanal (`outputs/`) | Lectura y escritura | Lectura y escritura | **Solo lectura**: lo recibe del operador |
| Parámetros (`src/config.py`) | Cambios solo con aprobación del dueño | Sin cambios | Sin acceso |

- Los profesores tienen acceso de lectura al repositorio para la evaluación.
- Fuera de los secretos propios de GitHub Actions, el producto no usa credenciales, porque Yahoo Finance es una fuente pública.

## 3. Canal de feedback

- **Canal principal:** issues de GitHub con la plantilla [`.github/ISSUE_TEMPLATE/feedback.md`](../.github/ISSUE_TEMPLATE/feedback.md). Sirve para dudas de interpretación, colores que no calzan con lo que ve el mercado, errores en el reporte y sugerencias.
- **El comité no tiene acceso al repositorio:** envía su feedback al operador por correo o en la misma reunión. El operador lo registra como issue.
- Cada issue se cierra con una respuesta y, si corresponde, con un cambio registrado en `docs/metodologia.md`.

## 4. Soporte y tiempos de respuesta esperados

| Situación | Cómo se detecta | Respuesta esperada |
|---|---|---|
| La corrida programada falla | Workflow en rojo (GitHub avisa por correo) o línea `estado=FALLIDA` en el log | Relanzarla antes del lunes a las 08:00. Si no se resuelve, avisar al comité que el reporte llega tarde |
| Alerta de deriva (WARNING en el log) | Línea `ALERTA DE DERIVA` y campo `alertas=` del log | Revisar antes de la reunión del lunes y anotar la explicación en un issue |
| Duda o inconsistencia del comité | Issue de feedback | Primera respuesta en 1 día hábil; resolución en 5 días hábiles |
| Cambio de metodología o de parámetros | Solicitud del dueño | Solo con aprobación del dueño, registro de la decisión y pruebas (CI) en verde |

Estos tiempos son metas propuestas. Hoy no se miden porque no hay usuario real.

## 5. Monitoreo en cada corrida (automático)

- **Calidad de datos (KPIs IL3):** cobertura, completitud, duplicidad, campos documentados y frescura (`src/kpis.py`).
- **Alertas de deriva** (`src/monitoreo.py`, WARNING; no hacen fallar la corrida):
  1. Datos desactualizados: el último dato tiene más de 7 días.
  2. Las filas descargadas varían más de 10% frente a la corrida anterior.
  3. Una serie sube o baja más de 50% en la última semana.
- **Falla controlada:** si la descarga no trae datos o menos de 98% de las series es válida, la corrida queda FALLIDA y no se sobrescriben los resultados.
- **Operación (KPIs IL4):** tasa de corridas sin error, duración, SLA y frecuencia de uso, calculados desde los logs (`docs/automatizacion.md`).

## 6. Calendario de recalibración trimestral (pendiente de implementar)

Primera semana hábil de **enero, abril, julio y octubre**, a cargo del dueño con apoyo de soporte. Hoy es un procedimiento definido, no automatizado.

| Tarea | Qué se revisa | Qué puede cambiar |
|---|---|---|
| KPIs del trimestre | Tasa de fallos, duración, SLA, alertas de deriva, frecuencia de uso | Metas de `config.py` (con aprobación del dueño) |
| Falsas alarmas | Rojos del trimestre en acciones sin caída posterior | Nada automáticamente: se documenta |
| Perfiles K-Means | Reentrenar con el panel actualizado (`notebooks/04_kmeans.ipynb`) y revisar si el k elegido y los nombres siguen siendo válidos | `data/processed/perfiles_kmeans.json` |
| Universo | Acciones que entran o salen del tema IA | `UNIVERSO` en `config.py` (decisión del dueño) |
| Diccionario de datos | Columnas nuevas sin documentar | `docs/diccionario_datos.csv` |

**No se recalibra:** los valores críticos del BSADF (ventana, umbrales, persistencia), las reglas v1 y v2 ni el criterio de éxito. Son la metodología validada, y cambiarlos requiere una nueva validación fuera de muestra.

## 7. Control de cambios

- Todo cambio pasa por Git. El CI (`.github/workflows/ci.yml`) corre las pruebas en cada push.
- Los cambios de parámetros o de metodología se anotan en el registro de decisiones de `docs/metodologia.md`, con motivo y control.
- Cada versión entregada lleva una etiqueta de Git (por ejemplo, `v1.2-entrega`).
