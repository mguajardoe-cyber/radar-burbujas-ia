# Guía de interpretación del Radar de Burbujas IA

*Para el comité de inversiones · Una página*

## Qué mide

Cada semana, el radar revisa los últimos **5 años** de cada acción y busca si hubo un tramo de **crecimiento explosivo**: un precio que sube *porque ya subió*, más rápido que lo normal. Esa es la huella estadística de una burbuja. El resultado se resume en un color.

## Qué significa cada color y qué hacer

| Color | Qué significa | Qué hacer en la reunión |
|---|---|---|
| 🟢 **Verde** | Sin evidencia de crecimiento explosivo. | Mantener la exposición según la política habitual. |
| 🟡 **Amarillo** | Señal temprana: el crecimiento es más rápido de lo normal (supera el umbral del 90%), aún sin evidencia fuerte. | **Monitorear.** Revisar la exposición y las variables de contexto; no exige actuar. |
| 🔴 **Rojo** | Evidencia fuerte de crecimiento explosivo (supera el umbral del 95%). | **Discutir reducir o cubrir la exposición** a esa acción. Tener presente que el riesgo suele estar *después* del rojo (ver abajo). |

**Un color solo cambia si la señal se mantiene 6 semanas seguidas.** Por eso, una acción puede seguir en rojo aunque la señal de esta semana ya haya bajado. El reporte lo indica en la columna "Señal bruta de la semana".

## Perfil de riesgo (columna de la hoja "Variables")

Además del color, cada acción trae un **perfil de riesgo**. El perfil dice a qué tipo de semana histórica de estas 9 tecnológicas se parece la semana actual, según cuatro rasgos: crecimiento explosivo (BSADF), alza de 12 meses, volatilidad y sensibilidad al mercado (beta). Se calcula con K-Means, un método que agrupa semanas parecidas.

| Perfil | Cómo es | Lectura para el comité |
|---|---|---|
| **Estable** | Volatilidad (~29% anual) y beta (~1,1) más bajas del grupo; alza moderada | Comportamiento habitual. "Estable" es **en comparación con estas tecnológicas**, no un activo de bajo riesgo |
| **Explosivo-alcista** | Alza de 12 meses muy fuerte (~+145% en promedio) y BSADF alto | La fase en la que suelen formarse las burbujas; mirar junto con el color |
| **Volátil-sensible al mercado** | Volatilidad alta (~57%) y beta cercana a 2, sin alza explosiva | Se mueve mucho con el mercado: en una caída general, probablemente caerá más que el índice |

- **El perfil no cambia el color ni reemplaza al semáforo.** Son dos lecturas distintas. El color mira si hubo crecimiento explosivo en los últimos 5 años, y un rojo se mantiene por persistencia. El perfil mira solo la semana actual. Por eso una acción puede estar en rojo con perfil "estable": el 30-10-2026, TSM sigue en rojo por su tramo explosivo, pero su alza de hoy (+37%) ya no se parece a las semanas explosivas típicas.
- **Es descriptivo, no predictivo:** no dice qué va a pasar con el precio.
- El modelo se recalibra cada trimestre (`docs/gobernanza.md`), y los nombres y cifras de esta tabla pueden cambiar levemente.

## Qué NO promete el producto

- **No predice la fecha de la caída.** Detecta que el precio está acelerando. El rojo suele apagarse cerca del techo, justo cuando el precio deja de acelerar, y **eso no significa que el peligro pasó**. En la puntocom, el Nikkei de 1989 y Bitcoin 2021, **gran parte de la caída vino después de que el rojo se apagara** (en el Nikkei y en Bitcoin, el rojo se apagó incluso antes del techo).
- **No anticipa crisis que no son burbujas.** La crisis financiera de 2008 y la caída de 2022 por alza de tasas no se vieron venir en el Nasdaq, porque no estuvieron precedidas de un crecimiento explosivo. **Un verde no es una garantía.**
- **No es una regla de inversión validada.** Las reglas automáticas probadas (reducir al 50% en rojo, con o sin un año de "enfriamiento") redujeron caídas en los episodios con señal. Pero superaron a reducir exposición al azar solo en algunos casos (Nasdaq y Bitcoin sí; Nikkei y la cartera de 9 acciones no). El color es un **insumo para la discusión**, no una orden.
- **Puede dar falsas alarmas.** En series largas sin burbuja aparece en promedio un rojo falso cada ~10 años. Hay que mirar cuánto dura el color y el contexto.
- **Necesita historia.** Una acción con menos de 5 años de cotización no tiene semáforo.

## Cómo leer el reporte Excel (`reporte_radar_AAAA-MM-DD.xlsx`)

1. **Hoja "Semáforo":** una fila por acción, ordenadas de más a menos urgente (rojo → amarillo → verde). Columnas clave:
   - **Semanas en el color:** un rojo de 20 semanas es más sólido que uno de 6.
   - **BSADF esta semana** y los **umbrales:** mientras más lejos sobre el umbral rojo, más fuerte la señal.
   - **Señal bruta:** si difiere del color, la acción está en transición.
2. **Hoja "Variables":**
   - La columna **"Perfil de riesgo"** se explica arriba.
   - En la columna "Por qué está en este color", una frase lista para leer en la reunión. Agrega contexto cuando es llamativo: alza de más de 50% en 12 meses, volatilidad sobre 45% anual o beta sobre 1,5 (muy sensible al mercado).
3. **Hoja "Gráficos":** la evolución del estadístico de las acciones en alerta frente a los dos umbrales. Una línea que viene bajando desde la zona roja anticipa un probable cambio de color en las semanas siguientes.

4. **Hoja "Registro de revisión":** la llena el operador después de la reunión, con fecha, revisor y decisión tomada. Sirve para medir el uso del reporte.

La fecha del encabezado es el **cierre del viernes** de los datos. El reporte se genera cada domingo en la noche con una ejecución programada (`docs/automatizacion.md`), para que esté listo antes de la reunión del lunes a las 08:00. Esa programación se activa al subir el repositorio a GitHub; hasta entonces, el operador lo genera con `python src/main.py`. Las dudas o inconsistencias se reportan al operador (`docs/gobernanza.md`).
