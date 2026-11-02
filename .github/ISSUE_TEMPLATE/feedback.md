---
name: Feedback del comité
about: Reportar una duda, una inconsistencia en el reporte o una sugerencia
title: "[Feedback] "
labels: feedback
---

<!--
Plantilla para el comité de inversiones (o para el operador, que registra el
feedback recibido por correo o en la reunión). Ver docs/gobernanza.md.
Tiempo de respuesta esperado: primera respuesta en 1 día hábil.
-->

## Tipo
- [ ] Duda de interpretación (qué significa un color, una cifra o una frase)
- [ ] Inconsistencia (el color o un dato no calza con lo que se ve en el mercado)
- [ ] Error en el reporte (archivo que no abre, hoja vacía, fecha equivocada)
- [ ] Sugerencia de mejora

## Reporte afectado
- Archivo: `reporte_radar_AAAA-MM-DD.xlsx`
- Hoja: Semáforo / Variables / Gráficos / Registro de revisión
- Ticker(s):

## Descripción
<!-- Qué se esperaba ver y qué se vio. Si es una inconsistencia, indicar la fuente de comparación. -->

## ¿Afecta una decisión de esta semana?
- [ ] Sí: se necesita respuesta antes de la próxima reunión
- [ ] No

---
*Para el equipo de soporte:* revisar el log de la corrida (`logs/radar_AAAA-MM-DD.log`), en especial las líneas `ALERTA DE DERIVA` y `KPI IL3`.
