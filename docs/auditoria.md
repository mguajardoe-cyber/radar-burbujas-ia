# Verificación independiente de resultados — Radar de Burbujas IA

Los scripts y resultados están en `audit/`. Todas las cifras se recalcularon desde `data/raw` con implementaciones propias (`audit/comun.py`), sin reutilizar el código de `src/` ni las cifras publicadas.

## Veredicto

**Los datos, el detector, el semáforo, el backtest y los KPIs de datos y operación se reproducen exactamente.** Coinciden:
- Las validaciones de datos.
- El BSADF, los umbrales y la persistencia.
- El semáforo actual.
- Las caídas máximas, los retornos y el Sharpe.
- Las anticipaciones del rojo.

La verificación encontró **un error de implementación** en el control placebo, que afectaba a los percentiles. Se corrigió sin cambiar la metodología (sección 6). Las cifras publicadas en el README y en `docs/metodologia.md` son las corregidas.

## 1. Datos (`audit/a1_datos.py`)

- Validaciones recalculadas para las 11 series: **coinciden** con `resumen_validacion.csv` (días, volumen 0 eliminado, hueco máximo, saltos y validez).
- Nasdaq: cierre de 5.048,62 el 10-03-2000 y de 1.114,11 el 09-10-2002, una caída de **−77,93%**. Son además el máximo y el mínimo diarios del ciclo.

## 2. Detector (`audit/a2_detector.py`)

- **BSADF con `statsmodels.adfuller` vs. `src/sadf.py`:** 90 semanas al azar (30 de NVDA, ^IXIC y TSM); diferencia máxima de 3,8×10⁻¹².
- **BSADF propio** (MCO con `numpy.linalg.lstsq`) de todas las semanas del universo vs. `panel_semanal.csv`: diferencia máxima de 9×10⁻¹¹.
- **Valores críticos** recalculados con otra semilla (2026) y 5.000 simulaciones: 90% = 0,351 ± 0,023 y 95% = 0,716 ± 0,022, frente a 0,360 y 0,694 publicados. **Dentro del error Monte Carlo.**
- **Persistencia:** 7 casos borde (rojo aislado, 5 vs. 6 semanas, verde aislado, alternancia amarillo/rojo, bajadas, inicio en rojo). Coinciden la implementación propia, `src` y el resultado esperado.
- **Semáforo al 30-10-2026:** idéntico en color, semanas en el color y señal bruta.

## 3. Backtest (`audit/a3_backtest.py`)

- **Sin sesgo de anticipación**, comprobado de tres formas:
  - Un único rojo en la semana 10 reduce la exposición recién desde el retorno de la semana 12.
  - Alterar los precios futuros no cambia el BSADF de las semanas anteriores.
  - Cambiar el color de una semana solo altera la exposición dos semanas después.
- **Métricas propias** de mantener, v1 y v2 en el Nasdaq (completo y tres episodios), Nikkei 1989, Bitcoin 2021 y la cartera B: **idénticas** a las publicadas.
- **Anticipación del rojo:** Nasdaq 2000 = 11 semanas (16 sin persistencia), Nikkei 1989 = 45 y Bitcoin 2021 = 42. **Sin rojo** en 2007-2009 ni en 2021-2022 con el semáforo oficial; la señal bruta tuvo 7 semanas sueltas en rojo en 2007-2009, que la persistencia filtra.

## 4. Cifras publicadas (`audit/a4_cifras.py`; tabla completa en `audit/resultados/cifras.md`)

| Cifra | Publicado | Recalculado | Estado |
|---|---|---|---|
| Caída del Nasdaq en la puntocom | −77,9% | −77,93% | OK |
| Universo | 9 acciones + 2 índices | 11 series | OK |
| Ventana / largo mínimo | 260 / 31 | 260 / 31 | OK |
| Umbrales amarillo / rojo | 0,36 / 0,69 | 0,351 / 0,716 (±0,02) | OK |
| Persistencia | 6 | 6 (log 260 = 5,56) | OK |
| Semáforo actual | TSM rojo 23 semanas; AMD amarillo 11 | Igual | OK |
| Anticipación puntocom / Nikkei / Bitcoin | 11 / 45 / 42 | 11 / 45 / 42 | OK |
| Falsas burbujas 2008 y 2022 (Nasdaq) | 0 | 0 semanas en rojo | OK |
| Episodios rojos del universo (bruto → persistencia) | 204 → 32 | 204 → 32 | OK |
| % de semanas en rojo | 6,6% → 4,3% | 6,6% → 4,3% | OK |
| Falsas alarmas por serie simulada | 16,9 → 2,7 | 17,6 ± 0,4 → 2,9 ± 0,1 (otra semilla) | OK |
| Caídas máximas mantener / v1 / v2 | Tabla de episodios | Idénticas | OK |
| Retorno anual y Sharpe (A y B) | Tabla de backtest | Idénticos | OK |
| Percentiles placebo | Ver sección 6 | Concuerdan tras la corrección | OK |

## 5. Reproducibilidad (`audit/a5_reproducibilidad.ps1`)

Se hizo un clon limpio del repositorio en una carpeta temporal, con un entorno nuevo de Python 3.13:
- `pip install -r requirements.txt`: OK.
- `pytest`: todas las pruebas pasan.
- `src/main.py --offline`: estado OK, 11/11 series válidas.
- El **semáforo resultante es idéntico** al del repositorio (diferencia de BSADF = 0).

Si la carpeta tiene una ruta muy larga, la instalación del entorno puede quedar incompleta por el límite de 260 caracteres de Windows. El README lo advierte.

## 6. Hallazgos y correcciones

### C1 — Placebo con episodios casi equiespaciados (crítico, corregido)

- **Problema:** `src/backtest.py` (`mascara_aleatoria`) repartía las semanas libres con una multinomial de probabilidades iguales. Eso producía huecos casi idénticos: en 1.000 placebos del Nasdaq, el primer episodio siempre empezó entre las semanas 257 y 355 de 1.661.
- **Corrección:** posiciones uniformes al azar, con separadores elegidos sin reemplazo. Se conservan el número y la duración de los episodios, la separación mínima, la semilla y la definición del percentil. No cambia la metodología, que siempre fue "mismos episodios en fechas al azar".
- **Prueba de regresión:** `tests/test_backtest.py` falla con la implementación anterior y pasa con la corregida.

Percentiles con la implementación anterior y con la corregida (`audit/resultados/percentiles_antes_despues.csv`; semilla 42, 1.000 placebos):

| Episodio | v1 anterior | v1 corregido | v2 anterior | v2 corregido |
|---|---|---|---|---|
| Nasdaq periodo completo | 53,5 | **14,4** | 3,1 | **13,1** |
| Nasdaq 2000-2002 | 53,5 | **15,2** | 3,1 | **13,8** |
| Cartera B (9 acciones) | 97,5 | **49,0** | 3,9 | **25,7** |
| Nikkei 1989 | 72,4 | **51,2** | 52,5 | **53,6** |
| Bitcoin 2021 | 86,7 | **35,3** | 26,0 | **13,2** |

Los valores corregidos concuerdan con un generador independiente (semilla 2026): 14,5 / 11,4 / 47,7 / 27,4 / 52,2 / 13,7, dentro del error Monte Carlo.

**Efecto en las conclusiones:**
- La v1 aporta algo en el Nasdaq (percentil 14) y queda igual al azar en la cartera B (49).
- El criterio fuera de muestra de la v2 queda en **1 de 2** (Bitcoin cumple; Nikkei no). Como no es mayoría, **la v2 sigue no validada**.
- Caídas máximas, retornos, Sharpe y anticipaciones no cambian.

### Hallazgos de documentación (corregidos)

| Hallazgo | Corrección |
|---|---|
| La documentación daba por hecha una ejecución semanal programada que no estaba configurada | Se implementó el workflow `radar_semanal.yml` y se documentó su estado de activación (`docs/automatizacion.md`) |
| "El CI corre en cada push" sin que el repositorio estuviera publicado | Se indica que se activa al publicar el repositorio (`docs/despliegue.md`) |
| Guía: "la caída fuerte vino después de que el rojo se apagara" | "Gran parte de la caída vino después…", porque en la puntocom el rojo seguía vigente en el peak |
| "8 de 11 series en rojo desde 2023" (notebook 03b) | Se precisa: 8 con señal bruta, 6 con el semáforo oficial |
| "Sin falsas burbujas en 2008 y 2022" | Se aclara que vale para el semáforo oficial; la señal bruta tuvo 7 semanas sueltas en 2007-2009 |
| Rutas largas en Windows | Advertencia en la instalación del README |

## 7. Alcance y hallazgos abiertos

- **Alcance:** esta verificación cubre los datos, el detector, el semáforo, el backtest, la validación fuera de muestra y los KPIs de datos y operación. Los componentes operativos (KPIs ampliados, alertas de deriva, perfiles K-Means y reporte) están cubiertos por las pruebas automáticas de `tests/`.
- **Ejecución programada y CI:** configurados; se activan al publicar el repositorio (`docs/despliegue.md`).
- **Shanghái no evaluable:** tiene un hueco de 13 días hábiles en 1999. Resolverlo exigiría cambiar la regla de validación o la fuente.
- **Validación fuera de muestra con 2 episodios:** es una limitación de la muestra, no un error.
