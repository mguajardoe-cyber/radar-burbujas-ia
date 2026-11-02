# Radar de Burbujas IA

> **"Nos avisa cada semana qué acciones de IA están en zona de burbuja, para decidir si reducir exposición."**

Proyecto final del Diplomado en Ciencia de Datos para las Finanzas (FEN, Universidad de Chile).
Autor: Martín Guajardo Espina · Profesores: Sebastián Egaña y César Núñez.

El Radar de Burbujas IA es un **producto de datos** para el comité de inversiones. En cada ejecución:
- Descarga los precios de 9 acciones de inteligencia artificial y de dos índices.
- Aplica un test estadístico de burbujas.
- Asigna a cada acción un perfil de riesgo con K-Means.
- Entrega un **reporte Excel con un semáforo** (verde, amarillo o rojo).

Funciona con un solo comando y registra en un log cada ejecución con sus KPIs y alertas. Tiene pruebas automáticas y una **ejecución semanal programada** en GitHub Actions (cada lunes a las 02:00 UTC), que se activa al publicar el repositorio en GitHub.

El documento está ordenado según las **7 capas** de un producto de datos.

---

## 1. Propósito y usuarios

- **Problema:** la exposición a acciones de IA se decide sin una medida objetiva del riesgo de burbuja, en un contexto de dudas sobre el retorno del gasto en IA.
- **Usuario:** el comité de inversiones de una AFP (equipo de renta variable extranjera), que se reúne cada semana. Es un usuario hipotético.
- **Decisión que habilita:** mantener, reducir o cubrir la exposición por acción.
- **Sin el producto:** la decisión vuelve a basarse solo en intuición e informes externos.

## 2. Entradas

- **Fuente:** Yahoo Finance mediante la librería `yfinance` (pública, sin credenciales).
- **Universo:** NVDA, MSFT, GOOGL, META, AMD, AVGO, TSM, ORCL y AMZN, más los índices Nasdaq (^IXIC) y S&P 500 (^GSPC). Datos diarios desde 1995.
- **Validaciones** (`src/ingesta.py`):
  - Sin fechas duplicadas.
  - Precios positivos.
  - Sin huecos de más de 5 días hábiles (10 para índices, por los feriados largos de cada bolsa).
  - Variaciones diarias de más de 50% marcadas para revisión.
  - Una serie que falla se excluye del reporte y queda en el log.
- **Diccionario de datos:** `docs/diccionario_datos.csv`, con la definición, la unidad y el origen de cada columna.

## 3. Procesamiento

1. **Cierre semanal** (viernes) del precio ajustado, en logaritmo.
2. **Test de burbuja BSADF** (Phillips, Shi y Yu, 2015) en una **ventana móvil de 5 años**. Cada semana busca el tramo de crecimiento más *explosivo*, es decir, un precio que sube porque ya subió. Los valores críticos se obtienen con 20.000 simulaciones Monte Carlo, y la implementación está verificada contra `statsmodels`.
3. **Semáforo:** amarillo si el estadístico supera el valor crítico al 90%, rojo si supera el del 95%. Para evitar señales de una sola semana, **el color cambia solo si la señal se mantiene 6 semanas seguidas** (regla de duración mínima de la misma literatura).
4. **Variables de contexto:** momentum de 12 meses, volatilidad anual y beta contra el S&P 500.
5. **Perfil de riesgo con K-Means** (Módulo 6, `src/perfiles.py`):
   - Se entrena con el historial semanal de las 9 acciones (9.971 semanas), usando BSADF, momentum, volatilidad y beta estandarizados.
   - Se eligió **k = 3** con el método del codo y Silhouette (0,374). Los perfiles son **estable**, **explosivo-alcista** y **volátil-sensible al mercado**.
   - El modelo se guarda en `data/processed/perfiles_kmeans.json` y se recalibra cada trimestre.
   - Es **descriptivo**: no cambia el semáforo.

Todo lo orquesta `src/main.py`. La lógica está en `src/` y los notebooks la explican paso a paso. El detalle técnico (parámetros, validación, limitaciones y decisiones de diseño) está en [`docs/metodologia.md`](docs/metodologia.md).

## 4. Salidas

- **Reporte semanal** `outputs/reporte_radar_AAAA-MM-DD.xlsx`, con cuatro hojas:
  - **Semáforo:** color, semanas en el color, estadístico y umbrales.
  - **Variables:** contexto de riesgo, **perfil de riesgo** y una explicación en palabras simples del color.
  - **Gráficos:** evolución del estadístico de las acciones en alerta.
  - **Registro de revisión:** el operador anota fecha, revisor y decisión del comité. Es la evidencia del KPI de frecuencia de uso.
- **Datos procesados** en `data/processed/` (CSV, para reproducibilidad) y modelo K-Means (`perfiles_kmeans.json`).
- **Log** de cada ejecución en `logs/`, con los KPIs IL3 e IL4 y las alertas de deriva.
- **Figuras para las láminas** en `outputs/figuras/`.

## 5. Consumo y usabilidad

- **Guía de interpretación para el comité:** [`docs/guia_interpretacion.md`](docs/guia_interpretacion.md). Explica qué significa cada color, qué hacer ante cada uno y qué *no* promete el producto.
- **Explicabilidad:** cada acción trae una frase que explica por qué está en su color, además de su perfil de riesgo.
- **Arquitectura:** [`docs/arquitectura.drawio`](docs/arquitectura.drawio), editable en [Draw.io](https://app.diagrams.net).

### Gobernanza ([`docs/gobernanza.md`](docs/gobernanza.md))

- **Roles:**
  - Dueño del producto: aprueba parámetros y metas.
  - Operador: verifica la corrida del lunes, revisa alertas y anota las revisiones.
  - Consumidor: el comité.
  - Soporte.
  En el proyecto, el autor cumple los tres roles operativos.
- **Accesos:** el repositorio es privado y el comité **solo lee el reporte**.
- **Feedback:** issues de GitHub con la plantilla [`.github/ISSUE_TEMPLATE/feedback.md`](.github/ISSUE_TEMPLATE/feedback.md). El comité envía su feedback al operador, que lo registra. Meta de primera respuesta: 1 día hábil.
- **Recalibración trimestral** (enero, abril, julio y octubre): KPIs, falsas alarmas, perfiles K-Means, universo y diccionario. Está definida, pero aún no implementada. La metodología del semáforo no se recalibra.

## 6. Mantenimiento

- **Ejecución semanal programada** ([`docs/automatizacion.md`](docs/automatizacion.md)):
  - `.github/workflows/radar_semanal.yml`: cron `0 2 * * 1` (lunes 02:00 UTC ≈ domingo 23:00 en Chile), más ejecución manual. Hace commit del reporte, el log y los datos; si `main.py` falla, el workflow queda en rojo.
  - Alternativa local: `scripts/programar_tarea_windows.ps1` (Programador de tareas de Windows).
  - El workflow se activa al publicar el repositorio en GitHub (`docs/despliegue.md`).
- **Log por ejecución:** origen de la corrida (manual, programada o de pruebas), duración, filas descargadas, series válidas, tickers excluidos, KPIs y errores.
- **Alertas de deriva** (`src/monitoreo.py`, WARNING que no hace fallar la corrida):
  - Datos de más de 7 días.
  - Filas descargadas ±10% frente a la corrida anterior.
  - Una serie que se mueve más de ±50% en la última semana.
- **Alerta de falla:** si falla la descarga o menos del 98% de las series es válida, la ejecución queda FALLIDA, no se sobrescriben los resultados y el programa termina con código 1.
- **Caché de valores críticos** (`data/processed/cv_bsadf.json`): no se repite la simulación en cada ejecución.
- **Git y CI:** el workflow `.github/workflows/ci.yml` corre las pruebas (`pytest`, 20 pruebas) en cada push, incluida una ejecución completa sin internet. Se activa al publicar el repositorio en GitHub (`docs/despliegue.md`).
- **Verificación independiente:** `docs/auditoria.md` recalcula las cifras desde los datos con código propio (`audit/`).

## 7. KPIs

Cada KPI lleva una etiqueta:

| Etiqueta | Significado |
|---|---|
| **MEDIDO** | Calculado con datos o logs reales |
| **DEFINIDO** | Meta y forma de medición fijadas, sin datos todavía |
| **PROYECTADO** | Calculado con supuestos, marcados `SUPUESTO` en `src/config.py` |

Los IL3 e IL4 se calculan en cada corrida (`src/kpis.py`) y quedan en el log. Los IL5 de negocio están en `notebooks/06c_kpis_negocio.ipynb`. Valores con datos al 30-10-2026.

| Nivel | KPI | Valor | Meta | Etiqueta | Fuente |
|---|---|---|---|---|---|
| IL3 | Cobertura de fuentes (series válidas / universo) | **100%** (11/11) | ≥ 98% | MEDIDO | Línea `KPI_IL3` del log |
| IL3 | Completitud (días válidos / días descargados) | **99,999%** (75.319/75.320; AMD pierde 1 día con volumen 0) | ≥ 98% | MEDIDO | Log, por serie y total |
| IL3 | Tasa de duplicidad (filas ticker-fecha repetidas) | **0%** | 0% | MEDIDO | Log |
| IL3 | Campos documentados en el diccionario | **100%** | 100% | MEDIDO | `docs/diccionario_datos.csv` |
| IL3 | Frescura (días desde el último dato) | **3 días** (dato del 30-10-2026) | ≤ 7 días (WARNING si se supera) | MEDIDO | Log |
| IL4 | Corridas sin error | **100%** (15/15; tasa de fallos 0%) | Fallos < 1% | MEDIDO | `logs/`: manual 4, pruebas 2, sin origen registrado 9 |
| IL4 | Duración de la corrida | **Máx. 25,0 s**, promedio 9,2 s; con descarga, 14,6 s | < 5 min | MEDIDO | `logs/` (25 s = corrida que entrenó K-Means por primera vez) |
| IL4 | Cumplimiento del SLA (reporte antes del lunes 08:00 en Chile) | Sin corridas programadas todavía | ≥ 95% | DEFINIDO | Pasa a MEDIDO con la primera corrida del workflow |
| IL4 | Frecuencia de uso (revisiones por semana) | 0 revisiones: no hay usuario real | ≥ 1 por semana | DEFINIDO | Hoja "Registro de revisión", `scripts/contar_revisiones.py` |
| IL5 | Anticipación del rojo antes del peak | **11 semanas** (puntocom), **45** (Nikkei 1989), **42** (Bitcoin 2021) | Rojo antes del peak | MEDIDO (backtest histórico) | Notebooks 03b y 06b |
| IL5 | Falsas burbujas en crisis sin burbuja | **Ninguna:** sin rojo en el Nasdaq antes de 2008 ni de 2022 | 0 | MEDIDO (backtest histórico) | Notebook 06 |
| IL5 | Regla v2 frente al azar fuera de muestra | **1 de 2** episodios (Bitcoin sí, Nikkei no): **no validada** | Mayoría con percentil < 20 | MEDIDO (backtest histórico) | Notebook 06b |
| IL5 | Pérdida evitada con la v2 (exposición supuesta de US$100 M) | Nasdaq 2000-02 **US$12,6 M** (dentro de muestra) · Nikkei **US$4,2 M** · Bitcoin **US$20,7 M** (fuera de muestra) | — | PROYECTADO | Notebook 06c; regla no validada |
| IL5 | Decisiones habilitadas (episodios rojos por año) | **1,1 por año** en las 9 acciones (30 en 26,9 años); **1 en 27 años** en el Nasdaq | — | MEDIDO (historial) | Notebook 06c |
| IL5 | Eficiencia operativa | **208 h/año** de análisis manual (4 h × 52, SUPUESTO) vs. **12,7 min/año** de máquina | — | PROYECTADO | Notebook 06c y logs |

El IL5 principal es la **calidad de detección**. Los montos en US$ son una proyección sobre una exposición supuesta, con una regla que no pasó su validación fuera de muestra. Las cifras de detección y backtest fueron verificadas de forma independiente (`docs/auditoria.md`); los KPIs operativos y los perfiles están cubiertos por pruebas automáticas.

---

## Hallazgos principales

1. **El detector funciona.** El semáforo se encendió en rojo antes del techo de las tres burbujas evaluadas (Nasdaq 2000, Nikkei 1989 y Bitcoin 2021) y no marcó en rojo al Nasdaq antes de las caídas de 2008 y 2022, que tuvieron otro origen (crisis financiera y alza de tasas).
2. **El semáforo actual (30-10-2026):** TSM en rojo, AMD en amarillo y el resto en verde.
   - **Perfiles de riesgo:** AMD es explosivo-alcista; AVGO, META y ORCL son volátil-sensibles al mercado; el resto es estable.
   - TSM sigue en rojo por persistencia, pero su alza actual (+37%) ya no se parece a las semanas explosivas típicas.
3. **Convertir la señal en una regla de inversión es más difícil.** El "percentil placebo" compara la regla con 1.000 reglas aleatorias que reducen la exposición el mismo tiempo: un valor bajo significa que el momento de la señal aporta.
   - La regla v1 (rojo → 50% invertido, verde → 100%) redujo poco la caída máxima del Nasdaq (−73,2% vs. −77,4%). Frente al azar, queda en el percentil 14 en el Nasdaq (aporta algo) y en el 49 en la cartera de 9 acciones (igual al azar).
   - La regla v2 agrega un año de "enfriamiento" tras el rojo. Mejora dentro de la muestra donde se diseñó (Nasdaq: −64,8%, percentil 13). Fuera de muestra reduce la caída en el Nikkei 1989 (−57,7% vs. −61,9%) y en Bitcoin 2021 (−53,5% vs. −74,2%).
   - El criterio fijado antes de evaluarla pedía, en la mayoría de los episodios fuera de muestra, menor caída **y** percentil < 20. La v2 lo cumple en Bitcoin (13,2), pero no en el Nikkei (53,6): **1 de 2 no es mayoría**, así que **no se considera validada**.
4. **Control del sesgo de diseño:** la regla v2 se definió después de evaluar la v1. Para controlar ese sesgo se fijaron antes el parámetro y el criterio de éxito, se validó en burbujas no usadas para diseñarla y no se probaron más variantes (`docs/metodologia.md`, secciones 6 y 9).

## Limitaciones

- **Sesgo de supervivencia:** las 9 acciones son "ganadoras" conocidas hoy. La validación histórica se hace sobre índices.
- **Detecta, no predice:** el test identifica crecimiento explosivo, no la fecha de la caída, y no anticipa crisis que no vienen de una burbuja (como 2008 o 2022).
- **Historia corta:** una acción necesita 5 años de historia para tener semáforo.
- **Falsas alarmas:** en series largas sin burbuja, es probable al menos un rojo falso cada ~10 años.
- **Pocos episodios fuera de muestra:** solo dos son evaluables (Shanghái queda fuera por un hueco de datos en 1999).
- **Usuario hipotético:** el uso real del reporte no se pudo medir. El SLA y la frecuencia de uso quedan DEFINIDOS.
- **Programación semanal aún no activa:** el workflow está listo, pero se activa al subir el repositorio a GitHub.
- **Perfiles K-Means descriptivos:** las semanas no son observaciones independientes y los perfiles no predicen caídas. Se eligió k = 3 sobre k = 2 (Silhouette 0,374 vs. 0,385) por utilidad para el comité, con una regla de tolerancia fijada después de ver la curva.

---

## Cómo instalar y ejecutar

Requisitos: Windows, macOS o Linux con **Python 3.13**. En Windows, conviene ubicar el proyecto en una carpeta de ruta corta: con rutas muy largas, el entorno virtual puede superar el límite de 260 caracteres de Windows y la instalación queda incompleta.

```bash
# 1. Crear el entorno virtual e instalar dependencias
python3.13 -m venv .venv          # en Windows: py -V:3.13 -m venv .venv
source .venv/bin/activate         # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Ejecución semanal (descarga datos nuevos de Yahoo Finance)
python src/main.py                # --origen programada si la lanza un programador

# 3. Ejecución sin internet (usa los CSV de data/raw; reproduce los resultados)
python src/main.py --offline

# 4. Pruebas automáticas
pytest -v
```

Cada ejecución genera `outputs/reporte_radar_AAAA-MM-DD.xlsx` y agrega su registro a `logs/radar_AAAA-MM-DD.log`.

## Estructura del repositorio

```
├── src/
│   ├── config.py      # universo y parámetros (un solo lugar)
│   ├── ingesta.py     # Capa 2: descarga y validaciones
│   ├── sadf.py        # Capa 3: tests SADF y BSADF
│   ├── features.py    # Capa 3: semanal, semáforo con persistencia, variables
│   ├── perfiles.py    # Capa 3: perfiles de riesgo con K-Means
│   ├── backtest.py    # Capa 7: reglas v1/v2, placebo
│   ├── kpis.py        # Capa 7: KPIs IL3, IL4 e IL5 con etiqueta MEDIDO/DEFINIDO/PROYECTADO
│   ├── monitoreo.py   # Capa 6: alertas de deriva
│   ├── reporte.py     # Capa 4: Excel semanal
│   └── main.py        # orquesta el flujo completo
├── notebooks/         # explicación paso a paso (ver mapa abajo)
├── scripts/           # tarea programada de Windows y conteo de revisiones
├── data/raw/          # descargas originales (CSV)
├── data/processed/    # datos validados, panel semanal, semáforo, caché de valores críticos, modelo K-Means
├── outputs/           # reportes Excel, tabla de episodios y figuras/ para las láminas
├── logs/              # log de cada ejecución (evidencia de los KPIs IL3 e IL4)
├── tests/             # pruebas automáticas (pytest)
├── docs/              # metodología, guía, gobernanza, automatización, despliegue, arquitectura, diccionario, verificación
├── .github/           # workflows (CI y radar semanal) y plantilla de feedback
├── audit/             # verificación independiente de las cifras
└── requirements.txt
```

## Mapa de notebooks

| Notebook | Qué muestra |
|---|---|
| `01_prueba_concepto_sadf` | Prueba de concepto: el test SADF detecta la burbuja puntocom antes de marzo de 2000 |
| `02_ingesta_y_validacion` | Descarga, validaciones y KPIs de calidad de datos (IL3) |
| `03_features_y_semaforo` | Primer semáforo (SADF anclado) y por qué no servía: el rojo era casi inalcanzable |
| `03b_bsadf_ventana_movil` | Metodología vigente: BSADF en ventana móvil, persistencia de 6 semanas y sensibilidad a la ventana |
| `04_kmeans` | Perfiles de riesgo: estandarización, codo, Silhouette, centroides, perfil actual y limitaciones |
| `06_backtest_kpis` | Backtest de la regla v1, control placebo y tabla de KPIs |
| `06b_regla_enfriamiento_fuera_de_muestra` | Regla v2 y validación fuera de muestra (Nikkei, Shanghái, Bitcoin) |
| `06c_kpis_negocio` | KPIs IL5 en lenguaje de negocio: pérdida evitada en US$, decisiones por año y eficiencia, con sensibilidad |
| `07_reporte` | Cómo se arma el reporte Excel para el comité |

El notebook 05 (random forest, probabilidad de caída) está planificado, pero no se desarrolló.

### Figuras para las láminas (`outputs/figuras/`)

| Archivo | Muestra |
|---|---|
| `perdida_evitada_usd.png` | Pérdida evitada por episodio con la v2 (PROYECTADO), con el percentil placebo |
| `decisiones_por_ano.png` | Episodios rojos por año en las 9 acciones |
| `kmeans_codo_silhouette.png` | Elección de k: codo y Silhouette |
| `kmeans_bsadf_vs_volatilidad.png` | Perfiles K-Means y semana actual de cada acción |
