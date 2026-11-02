# Metodología del Radar de Burbujas IA

Documento técnico: datos, test de burbuja, semáforo, reglas de exposición, validación, perfiles de riesgo, limitaciones y decisiones de diseño. La visión del producto por capas está en el [README](../README.md). Todos los parámetros viven en `src/config.py`.

## 1. Datos

- **Fuente:** Yahoo Finance mediante `yfinance` (pública, sin credenciales).
- **Universo:** NVDA, MSFT, GOOGL, META, AMD, AVGO, TSM, ORCL y AMZN, más los índices ^IXIC (Nasdaq) y ^GSPC (S&P 500). Datos diarios desde 1995; procesamiento semanal, con el cierre ajustado del viernes (W-FRI).
- **Validaciones** (`src/ingesta.py`). Una serie que no pasa se excluye del reporte y queda en el log.

  | Regla | Acciones | Índices |
  |---|---|---|
  | Fechas duplicadas | Excluye la serie | Excluye la serie |
  | Precios no positivos | Excluye la serie | Excluye la serie |
  | Volumen ≤ 0 | Se elimina solo ese día (error puntual de Yahoo) | No se exige: un índice no tiene volumen propio |
  | Hueco máximo entre fechas | 5 días hábiles | 10 días hábiles (feriados largos de cada bolsa); cada hueco mayor a 5 queda en el log |
  | Variación diaria > 50% | Se marca para revisión | Se marca para revisión |

- **Metadatos:** fuente y fecha y hora de descarga en cada fila. El diccionario de datos (`docs/diccionario_datos.csv`) define cada columna, con su unidad y su origen.

## 2. Test de burbuja: BSADF en ventana móvil

- **Definición:** versión acotada del GSADF de Phillips, Shi y Yu (2015). Para cada semana *t* se usan solo las últimas **260 semanas** (5 años):

  BSADF_t = máximo del estadístico ADF (t de β) de las regresiones que terminan en *t* y parten en cualquier semana de la ventana

  El largo mínimo es n0 = floor((0,01 + 1,8/√260) · 260) = **31 semanas**.
- **Supuestos:** logaritmo del cierre ajustado semanal, 1 rezago fijo, regresión con constante.
- **Valores críticos:** Monte Carlo con 20.000 caminatas aleatorias de largo 260 (nula de PSY 2015: y_t = 1/260 + y_{t−1} + ε_t), semilla 42. Como la ventana es fija, el umbral es único para toda acción y semana: **cv 90% = 0,36** y **cv 95% = 0,69**. Se guardan en `data/processed/cv_bsadf.json` y se recalculan solo si cambian la ventana, los rezagos, la semilla o el número de simulaciones.
- **Implementación:** `src/sadf.py` (`adf_hacia_atras`, `bsadf_movil`, `valores_criticos_bsadf`), verificada contra `statsmodels.adfuller`.
- **Por qué ventana móvil y no SADF anclado** (notebooks 01, 03 y 03b): con ventanas ancladas en 1995, el umbral rojo era casi inalcanzable (ADF máximo de NVDA 0,56 vs. umbral 1,58), y el amarillo daba falsas alarmas en ~66% de las series sin burbuja. El SADF anclado se conserva como referencia.

## 3. Semáforo

- **Amarillo:** BSADF > cv 90%. **Rojo:** BSADF > cv 95%. **Verde:** el resto. Sin semáforo mientras la serie no tenga 260 semanas.
- **Persistencia de 6 semanas:** es la regla de duración mínima de PSY (2015), log(260) ≈ 5,6 → 6. El color cambia solo tras 6 semanas seguidas en el nuevo nivel, en ambas direcciones, y cada serie parte en verde. La señal sin filtro queda en la columna `semaforo_bruto`.
- **Efecto de la persistencia** (notebook 03b):
  - Los episodios rojos del universo bajan de 204 a 32, y ninguno dura 1 o 2 semanas. Las semanas en rojo bajan de 6,6% a 4,3%.
  - En series simuladas sin burbuja (1.661 semanas), las falsas alarmas bajan de 16,9 a 2,7 episodios rojos por serie.
  - Como alternativa se evaluó una persistencia de 2 semanas; filtra menos.
- **Resultados:** la puntocom queda en rojo desde el 24-12-1999, **11 semanas antes del peak**, con historia de ^IXIC desde 1990 (16 semanas con la señal bruta).
- **Sensibilidad a la ventana (156 / 260 / 364 semanas):**
  - Umbrales rojos de 0,72 / 0,69 / 0,70.
  - Rojo antes del peak de 2000: 10 / 11 / 57 semanas.
  - Falsas alarmas similares, ~3% de las semanas.
  - Las conclusiones no dependen de la ventana.

## 4. Variables de contexto

Retornos semanales logarítmicos:
- **Momentum:** retorno de 52 semanas.
- **Volatilidad:** desviación de 52 semanas, anualizada.
- **Beta (CAPM):** cov(r_i, r_m) / var(r_m) en 104 semanas, contra ^GSPC.

## 5. Reglas de exposición y backtest (`src/backtest.py`)

- **Regla v1:** rojo → 50% invertido; verde → 100%; amarillo mantiene la exposición anterior.
- **Regla v2:** igual a la v1, pero al terminar un episodio rojo la exposición se mantiene en 50% durante **52 semanas de enfriamiento**. Un rojo nuevo reinicia el contador. Justificación: las caídas posteriores a una burbuja duran entre 1 y 3 años (Nasdaq 2000-2002 ≈ 2,5 años). Con 26 y 104 semanas se reporta solo una sensibilidad informativa, sin elegir la mejor.
- **Ejecución:** la señal de la semana *t* se ejecuta al cierre de *t+1* y rige desde el retorno de *t+2*. La caja rinde 0%. Costos de 0% (base) y 0,1% del monto transado (sensibilidad).
- **Carteras:**
  - **A:** ^IXIC con historia desde 1990, evaluada en 1994-2026.
  - **B:** las 9 acciones con igual peso, en 2018-2026.
- **Control placebo:** 1.000 reglas aleatorias con el mismo número y duración de episodios de exposición reducida, ubicados uniformemente al azar (en la cartera B, por acción). El percentil es el % de placebos con una caída máxima **menos** severa que la regla: bajo significa que el momento de la señal aporta. Si la regla no reduce la exposición dentro de la ventana evaluada, el percentil es "no aplica", porque solo reflejaría empates.

| Cartera | Caída máx. mantener | v1 | v2 | Percentil placebo v1 / v2 |
|---|---|---|---|---|
| A: Nasdaq 1994-2026 | −77,4% | −73,2% | −64,8% | 14,4 / 13,1 |
| A: Nasdaq 2000-2002 | −77,4% | −73,2% | −64,8% | 15,2 / 13,8 |
| A: 2007-2009 y 2021-2022 | Sin señal: igual a mantener | | | no aplica |
| B: 9 acciones 2018-2026 | −45,4% | −43,5% | −37,9% | 49,0 / 25,7 |

## 6. Validación fuera de muestra de la regla v2

La v2 se diseñó después de evaluar la v1. Su resultado dentro de muestra (Nasdaq) no cuenta como validación. Para controlar ese sesgo:
- El parámetro (52 semanas) se fijó antes de evaluar.
- La regla se aplicó sin cambios a burbujas no usadas para diseñarla.
- El criterio de éxito se definió de antemano.
- No se probaron otras variantes.

- **Criterio de éxito:** en la mayoría de los episodios evaluables, (a) reducir la caída máxima frente a mantener **y** (b) percentil placebo < 20.
- **Episodios evaluables:**
  - **Nikkei 1989:** rojo 45 semanas antes del peak (29-12-1989). Caída −57,7% vs. −61,9%; percentil 53,6. Cumple (a), no (b).
  - **Bitcoin 2021:** rojo 42 semanas antes del peak (12-11-2021). Caída −53,5% vs. −74,2%; percentil 13,2. Cumple (a) y (b).
  - **Shanghái 2007 y 2015:** no evaluables. La serie tiene un hueco de 13 días hábiles tras el 09-02-1999, sobre el máximo de 10.
- **Resultado: 1 de 2 no es mayoría → la v2 no está validada.** Por eso el impacto (IL5) se presenta como **calidad de detección**: el rojo anticipa los tres peaks evaluables (puntocom 11 semanas, Nikkei 45, Bitcoin 42) y no marca como burbujas las caídas de 2008 ni de 2022.

## 7. Perfiles de riesgo con K-Means (`src/perfiles.py`, notebook 04)

- **Datos:** 9.971 semanas-acción (las 9 acciones, desde diciembre de 1999) con BSADF, momentum, volatilidad y beta, estandarizados (media 0, desviación 1). Semilla 42, n_init 10.
- **Elección de k entre 2 y 6:**

  | k | 2 | 3 | 4 | 5 | 6 |
  |---|---|---|---|---|---|
  | Silhouette | 0,385 | 0,374 | 0,289 | 0,291 | 0,291 |

  La inercia baja 24% de 2 a 3 y 19% de 3 a 4. Se elige **k = 3** con la regla "el k más grande cuya Silhouette queda a menos de 0,02 de la máxima". k = 2 junta las semanas explosivas con las volátiles, que para el comité son situaciones distintas. La regla se fijó a la vista de la curva; con la máxima estricta, k sería 2.
- **Perfiles** (centroides en unidades originales; nombres por regla fija sobre z ≥ 0,75):

  | Perfil | % del historial | BSADF | Momentum | Volatilidad | Beta |
  |---|---|---|---|---|---|
  | Estable | 64,6% | −0,49 | 20% | 29% | 1,10 |
  | Explosivo-alcista | 13,1% | 0,65 | 145% | 46% | 1,61 |
  | Volátil-sensible al mercado | 22,4% | −0,60 | 4% | 57% | 1,96 |

- **Uso:** `main.py` asigna el centroide más cercano a la semana actual de cada acción, con el modelo guardado en `data/processed/perfiles_kmeans.json`, que se recalibra cada trimestre. El perfil es **descriptivo**: no cambia el semáforo ni el backtest.

## 8. Limitaciones

1. **Sesgo de supervivencia:** las 9 acciones son "ganadoras" conocidas hoy. La validación histórica se hace sobre índices. En la cartera B solo es válida la comparación entre reglas, no el retorno absoluto.
2. **Detecta, no predice el momento:** el test identifica crecimiento explosivo, no la fecha de la caída. El BSADF baja cuando el precio deja de acelerar, que suele ser el peak.
3. **IL5 proveniente de backtests,** no de decisiones reales.
4. **Usuario hipotético:** el uso real no se puede medir. El SLA y la frecuencia de uso quedan DEFINIDOS.
5. **Historia corta:** una serie necesita 260 semanas para tener semáforo. Las series que parten en 1995 tienen semáforo desde diciembre de 1999; por eso la cartera A usa ^IXIC con historia desde 1990.
6. **Falsas alarmas inevitables en series largas:** aun con persistencia, ~93% de las series sin burbuja de 1.661 semanas tienen al menos un rojo (2,7 episodios en ~27 años). El color debe leerse junto con su duración y el contexto.
7. **La regla v1 protege poco:** su ventaja frente al azar es parcial (percentil 14,4 en el Nasdaq, 49,0 en la cartera B).
8. **Supuestos del backtest:** caja al 0%, índices de precios sin dividendos (igual para la regla y para mantener) y costos proporcionales simples.
9. **La regla v2 no está validada fuera de muestra** (1 de 2), y su resultado dentro de muestra no cuenta como evidencia.
10. **Validación fuera de muestra acotada:** solo 2 episodios evaluables. Shanghái queda excluido por un hueco de datos; no se verificó si fue un cierre real y no se usó otra fuente.
11. **KPIs en US$ y horas son proyecciones:** usan una exposición supuesta (US$100 millones) y 4 horas semanales de análisis manual (`SUPUESTO` en `config.py`).
12. **K-Means descriptivo:** las semanas no son observaciones independientes (ventanas traslapadas), la separación es moderada (Silhouette 0,37) y los perfiles son relativos a 9 tecnológicas.

## 9. Decisiones de diseño

| Decisión | Motivo | Control |
|---|---|---|
| Datos semanales, 1 rezago, valores críticos por Monte Carlo | Menos ruido que los datos diarios (notebook 01) | Implementación verificada contra `statsmodels` |
| Universo de 9 acciones de IA + ^IXIC y ^GSPC | Exposición temática del comité | Sesgo de supervivencia declarado |
| Volumen ≤ 0: se elimina solo ese día | Errores puntuales de Yahoo (AMD 02-01-2015, ^GSPC 24-05-2023) | Registrado en el log |
| Reglas de datos propias para índices | Sin volumen propio; los feriados largos son cierres reales | Sin cambios en el universo ni en las carteras A y B |
| BSADF en ventana móvil de 260 semanas | Con el SADF anclado, el rojo era inalcanzable | Sensibilidad 156 / 260 / 364 semanas |
| Persistencia de 6 semanas | Duración mínima de PSY 2015; elimina episodios de 1-2 semanas | Comparada con 2 semanas y sin persistencia |
| Regla v1 fijada antes del backtest | Evitar ajustar la regla a los resultados | Control placebo |
| Regla v2 con 52 semanas de enfriamiento, definida después de evaluar la v1 | La v1 vuelve al 100% en el peak, cuando empieza la caída | Parámetro y criterio fijados antes; validación fuera de muestra; sin variantes adicionales. Resultado: no validada |
| Percentil placebo "no aplica" si la regla no actúa | Sin reducción de exposición, el percentil solo cuenta empates | Misma definición del percentil |
| KPIs con etiqueta MEDIDO / DEFINIDO / PROYECTADO | No mezclar mediciones con supuestos | Supuestos marcados en `config.py` |
| Ejecución semanal en GitHub Actions | Reporte listo antes del lunes 08:00 | Origen de cada corrida en el log; KPI de SLA |
| Alertas de deriva como WARNING | Avisar al operador sin detener el reporte | Contadas en `alertas=` del log |
| K-Means con k = 3 | Perfiles distinguibles para el comité | Regla de tolerancia documentada; sin efecto en el semáforo ni el backtest |
