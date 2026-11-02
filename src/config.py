# =============================================================================
# Configuración central del Radar de Burbujas IA
#
# Propósito:
#   Reunir en un solo lugar el universo, las rutas y los parámetros de todas
#   las capas. Cualquier cambio de parámetro se hace aquí y requiere la
#   aprobación del dueño del producto (docs/gobernanza.md). Las decisiones de
#   diseño están documentadas en docs/metodologia.md.
#
# Entradas: ninguna.
# Salidas: constantes importadas por los demás módulos de src/.
# =============================================================================

from pathlib import Path

# --- Rutas -------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
DIR_OUTPUTS = RAIZ / "outputs"
DIR_LOGS = RAIZ / "logs"
DIR_DOCS = RAIZ / "docs"

# --- Capa 2: universo y descarga ----------------------------------------------
# 9 acciones de inteligencia artificial + 2 índices de referencia.
UNIVERSO = {
    "NVDA": "NVIDIA", "MSFT": "Microsoft", "GOOGL": "Alphabet", "META": "Meta Platforms",
    "AMD": "Advanced Micro Devices", "AVGO": "Broadcom", "TSM": "Taiwan Semiconductor",
    "ORCL": "Oracle", "AMZN": "Amazon",
}
INDICES = {"^IXIC": "Nasdaq Composite", "^GSPC": "S&P 500"}
INDICE_MERCADO = "^GSPC"          # mercado para el beta (CAPM)
FECHA_INICIO = "1995-01-01"
FUENTE = "Yahoo Finance (yfinance)"

# --- Capa 2: validaciones (docs/metodologia.md, sección 1) ----------------------
# Días con volumen 0 o negativo: se elimina solo ese día y se registra en el log
# (errores puntuales de Yahoo: AMD 02-01-2015 y ^GSPC 24-05-2023).
MAX_HUECO_DIAS_HABILES = 5        # hueco máximo permitido entre dos fechas (acciones)

# Índices: un índice no tiene volumen propio
# (Yahoo informa 0 por décadas) y los feriados largos de cada bolsa son cierres
# reales. Para índices no se exige volumen positivo y el hueco máximo es de 10
# días hábiles; cada hueco mayor a 5 días queda registrado en el log.
OTROS_INDICES = {"000001.SS"}     # índices cuyo ticker no empieza con ^
EXIGIR_VOLUMEN_INDICES = False
MAX_HUECO_DIAS_HABILES_INDICES = 10
UMBRAL_SALTO_DIARIO = 0.50        # variación diaria que se marca para revisión
META_PCT_VALIDADAS = 0.98         # KPI IL3 / alerta de falla

# --- Capa 7: metas de los KPIs IL3 (src/kpis.py) --------------------------------
# Metas propuestas; las ajusta el dueño del producto.
META_COMPLETITUD = 0.98           # días válidos / días descargados (misma vara que la cobertura)
META_DUPLICIDAD = 0.0             # filas (ticker, fecha) duplicadas: ninguna (regla de validación 1)
META_CAMPOS_DOCUMENTADOS = 1.0    # todas las columnas en docs/diccionario_datos.csv
META_FRESCURA_DIAS = 7            # días entre el último dato y la ejecución (una semana)

# --- Capa 6: alertas de deriva (src/monitoreo.py; WARNING, no fallan la corrida) ---
# Frescura: META_FRESCURA_DIAS. Además:
UMBRAL_VARIACION_FILAS = 0.10     # filas descargadas vs. la corrida anterior: ±10%
UMBRAL_SALTO_SEMANAL = 0.50       # variación de una serie en la última semana: ±50%

# --- Capa 7: metas de los KPIs IL4 (operación) ----------------------------------
META_TASA_FALLOS = 0.01           # corridas con error / corridas: menos de 1%
META_DURACION_S = 300             # duración de una corrida: menos de 5 minutos
# SLA: el reporte debe estar listo antes del lunes a las 08:00, hora de Chile
# (la reunión del comité es el lunes). Se mide solo en corridas programadas.
ZONA_HORARIA_COMITE = "America/Santiago"
SLA_HORA_LIMITE_LUNES = 8
META_SLA = 0.95                   # % de corridas programadas con reporte a tiempo
META_REVISIONES_SEMANA = 1        # revisiones del reporte registradas por semana (una por reunión)

# --- Capa 7: supuestos de los KPIs IL5 en lenguaje de negocio (PROYECTADOS) --------
# SUPUESTO: exposición del comité a tecnológicas. Orden de magnitud de una
# posición temática dentro de la renta variable extranjera de una AFP; no es
# un dato real (el usuario es hipotético). La sensibilidad usa 50, 100 y 500.
EXPOSICION_USD = 100_000_000      # SUPUESTO: exposición del comité a tecnológicas
EXPOSICIONES_SENSIBILIDAD_USD = (50_000_000, 100_000_000, 500_000_000)   # SUPUESTO
# SUPUESTO: horas semanales de análisis manual que el radar reemplaza (descargar
# precios, actualizar planillas y revisar gráficos de 9 acciones antes de la
# reunión). Estimación propia, no medida.
HORAS_ANALISIS_SEMANA = 4         # SUPUESTO: horas semanales de análisis manual
# Episodios para la pérdida evitada: los tres con rojo antes del peak (puntocom
# dentro de muestra; Nikkei y Bitcoin fuera de muestra). Salen de la tabla de
# episodios del notebook 06b (outputs/resumen_episodios_v1_v2.csv).
EPISODIOS_PERDIDA_EVITADA = ("Nasdaq 2000-2002", "Nikkei 1989", "Bitcoin 2021")

# --- Capa 3: test SADF -----------------------------------------------------------
FRECUENCIA = "W-FRI"              # cierre semanal (viernes)
REZAGOS_ADF = 1
N_SIM_MC = 20000
SEMILLA_MC = 42

# --- Capa 3: BSADF en ventana móvil ---------------------------------------------
# Reemplaza al SADF anclado como base del semáforo.
VENTANA_BSADF = 260               # semanas (5 años)
CUANTIL_AMARILLO = 0.90           # BSADF > valor crítico 90% → amarillo
CUANTIL_ROJO = 0.95               # BSADF > valor crítico 95% → rojo
# Persistencia: regla de duración mínima de
# Phillips, Shi y Yu (2015), log(T) con T = 260 → log(260) ≈ 5,6 → 6 semanas.
# El semáforo cambia de color solo tras 6 semanas seguidas en el nuevo nivel
# (en ambas direcciones).
PERSISTENCIA_SEMANAS = 6
RUTA_CV_BSADF = DIR_PROCESSED / "cv_bsadf.json"   # caché de valores críticos

# --- Capa 7: regla de exposición v2 ---------------------------------------------
# Tras un episodio rojo, la exposición se mantiene en 50% durante 52 semanas de
# enfriamiento antes de volver a 100%. Justificación: las caídas posteriores a
# una burbuja suelen durar entre 1 y 3 años (Nasdaq 2000-2002 ≈ 2,5 años).
# 26 y 104 semanas se reportan solo como sensibilidad; NO se elige la mejor.
SEMANAS_ENFRIAMIENTO = 52

# --- Capa 3: perfiles de riesgo con K-Means (src/perfiles.py) --------------------
# Descriptivos: NO cambian el semáforo, el backtest ni los KPIs.
VARIABLES_PERFIL = ("bsadf", "momentum_52s", "volatilidad_anual", "beta_104s")
K_CANDIDATOS = (2, 3, 4, 5, 6)
SEMILLA_KMEANS = 42
N_INIT_KMEANS = 10
# Elección de k: el k más grande cuya Silhouette queda a menos de 0,02 de la
# máxima (diferencias menores son ruido y un k mayor separa perfiles que el
# comité distingue); el codo se usa como verificación. Con la Silhouette
# máxima estricta, k sería 2 (ver notebook 04).
TOLERANCIA_SILHOUETTE = 0.02
UMBRAL_NOMBRE_PERFIL = 0.75       # z del centroide sobre el cual una variable da nombre al perfil
RUTA_PERFILES = DIR_PROCESSED / "perfiles_kmeans.json"   # modelo guardado (se recalibra cada trimestre)

# --- Capa 3: variables de riesgo --------------------------------------------------
SEMANAS_MOMENTUM = 52             # retorno de 12 meses
SEMANAS_VOLATILIDAD = 52          # desviación de retornos semanales, anualizada
SEMANAS_BETA = 104                # 2 años de retornos semanales
SEMANAS_POR_ANO = 52
