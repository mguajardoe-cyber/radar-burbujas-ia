# =============================================================================
# Capa 3 — Procesamiento: variables semanales y semáforo basado en SADF
#
# Propósito:
#   1. Agregar los precios diarios validados a cierre semanal (viernes).
#   2. Calcular por acción e índice:
#      - Secuencia de ADF recursivos sobre el log-precio (src/sadf.py) y su
#        máximo acumulado (estadístico SADF hasta la fecha).
#      - Momentum: retorno de 52 semanas.
#      - Volatilidad: desviación de retornos semanales (52 semanas), anualizada.
#      - Beta (CAPM): cov(r_i, r_m) / var(r_m) en 104 semanas, mercado = ^GSPC.
#   3. Semáforo semanal. Metodología vigente (docs/metodologia.md):
#      BSADF en ventana móvil de 260 semanas (src/sadf.py):
#      - Rojo:     BSADF > valor crítico 95%.
#      - Amarillo: BSADF > valor crítico 90%.
#      - Verde:    resto (o menos de 260 semanas de historia: sin semáforo).
#      Persistencia: el color cambia solo tras 6 semanas seguidas en el nuevo
#      nivel (duración mínima de PSY 2015). Los valores críticos se guardan en
#      data/processed/cv_bsadf.json y se reutilizan entre ejecuciones.
#      Referencia (notebook 03): SADF anclado al inicio de la serie, con
#      rojo = ADF > cv 95% del SADF y amarillo = ADF > cv 95% de su ventana.
#
# Entradas:
#   - data/processed/precios_validados.csv (salida de src/ingesta.py).
#   - Parámetros de src/config.py.
#
# Salidas:
#   - Panel semanal (ticker, fecha, precio, BSADF, valores críticos, semáforo
#     bruto y con persistencia, variables) → data/processed/panel_semanal.csv.
#   - Valores críticos del Monte Carlo → data/processed/cv_bsadf.json.
#   - Semáforo de la última semana por ticker → data/processed/semaforo_actual.csv.
# =============================================================================

import json
import logging

import numpy as np
import pandas as pd

from src import config as C
from src import sadf as S

log = logging.getLogger("radar.features")


def a_semanal(validados, hoy=None):
    """Cierre ajustado semanal (último día hábil de cada semana) en formato
    ancho: filas = viernes, columnas = tickers.

    Se descartan semanas que aún no terminan (viernes posterior a `hoy`), para
    que una corrida a mitad de semana no use un cierre parcial.
    """
    hoy = pd.Timestamp.today().normalize() if hoy is None else pd.Timestamp(hoy)
    ancho = validados.pivot(index="fecha", columns="ticker", values="adj_close")
    ancho.index = pd.to_datetime(ancho.index)
    semanal = ancho.resample(C.FRECUENCIA).last()
    semanal = semanal[semanal.index <= hoy]
    return semanal.dropna(how="all")


def semaforo(estadistico, umbral_amarillo, umbral_rojo):
    """Clasifica cada semana en verde / amarillo / rojo."""
    return np.select([estadistico > umbral_rojo, estadistico > umbral_amarillo],
                     ["rojo", "amarillo"], default="verde")


NIVEL = {"verde": 0, "amarillo": 1, "rojo": 2}
COLOR = {v: k for k, v in NIVEL.items()}


def aplicar_persistencia(colores, semanas=C.PERSISTENCIA_SEMANAS, inicial="verde"):
    """Semáforo con persistencia (regla de duración mínima, PSY 2015).

    El color cambia solo cuando las últimas `semanas` están todas en un nivel
    distinto al actual, en la misma dirección:
      - Sube al menor nivel de esas semanas, si todas están sobre el actual.
      - Baja al mayor nivel de esas semanas, si todas están bajo el actual.
    La serie parte en `inicial` (verde: sin evidencia previa de burbuja).
    Recibe y devuelve colores ("verde", "amarillo", "rojo").
    """
    niveles = pd.Series([NIVEL[c] for c in colores], dtype=float)
    minimo = niveles.rolling(semanas).min().to_numpy()
    maximo = niveles.rolling(semanas).max().to_numpy()
    estado, salida = NIVEL[inicial], []
    for lo, hi in zip(minimo, maximo):
        if not np.isnan(lo):
            if lo > estado:
                estado = int(lo)
            elif hi < estado:
                estado = int(hi)
        salida.append(COLOR[estado])
    return np.array(salida)


def valores_criticos_cache(ventana=C.VENTANA_BSADF, rezagos=C.REZAGOS_ADF, semilla=C.SEMILLA_MC,
                           n_sim=C.N_SIM_MC, ruta=C.RUTA_CV_BSADF):
    """Valores críticos del BSADF guardados en JSON para no simularlos en cada
    ejecución. Se recalculan solo si cambian ventana, rezagos, semilla o
    número de simulaciones. Devuelve dict {cuantil: valor crítico}.
    """
    parametros = {"ventana": ventana, "rezagos": rezagos, "semilla": semilla, "n_sim": n_sim}
    cache = {}
    if ruta.exists():
        cache = json.loads(ruta.read_text(encoding="utf-8"))
    clave = f"ventana={ventana}"
    guardado = cache.get(clave)
    if guardado and guardado["parametros"] == parametros:
        return {float(q): v for q, v in guardado["valores_criticos"].items()}

    log.info("Simulando valores críticos BSADF (ventana %d, %d simulaciones)", ventana, n_sim)
    cv = S.valores_criticos_bsadf(ventana, rezagos=rezagos, n_sim=n_sim, semilla=semilla)
    cache[clave] = {"parametros": parametros, "valores_criticos": {str(q): float(v) for q, v in cv.items()},
                    "fecha_calculo": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")}
    ruta.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    return cv


def senales_bsadf(semanal, ventana=C.VENTANA_BSADF, persistencia=C.PERSISTENCIA_SEMANAS):
    """BSADF en ventana móvil, valores críticos y semáforo para cada ticker.

    Los valores críticos son los mismos para todos (ventana fija) y se leen de
    la caché (data/processed/cv_bsadf.json). Devuelve un DataFrame largo:
    ticker, fecha, bsadf, cv_bsadf_90, cv_bsadf_95, semaforo_bruto (sin
    persistencia) y semaforo (con persistencia: el que ve el comité).
    """
    cv = valores_criticos_cache(ventana)
    umbral_amarillo, umbral_rojo = cv[C.CUANTIL_AMARILLO], cv[C.CUANTIL_ROJO]
    log.info("Umbrales BSADF (%d semanas): amarillo %.3f, rojo %.3f; persistencia %d semanas",
             ventana, umbral_amarillo, umbral_rojo, persistencia)

    partes = []
    for t in semanal.columns:
        bs = S.bsadf_movil(np.log(semanal[t].dropna()), ventana, rezagos=C.REZAGOS_ADF)
        if bs.empty:
            log.warning("%s: menos de %d semanas de historia, sin semáforo", t, ventana)
            continue
        df = pd.DataFrame({"ticker": t, "fecha": bs.index, "bsadf": bs.to_numpy(),
                           "cv_bsadf_90": umbral_amarillo, "cv_bsadf_95": umbral_rojo})
        df["semaforo_bruto"] = semaforo(df["bsadf"], umbral_amarillo, umbral_rojo)
        df["semaforo"] = aplicar_persistencia(df["semaforo_bruto"], persistencia)
        partes.append(df)
        log.info("%s: %d semanas con BSADF, semáforo actual %s (bruto %s)", t, len(df),
                 df["semaforo"].iloc[-1], df["semaforo_bruto"].iloc[-1])
    return pd.concat(partes, ignore_index=True)


def senales_sadf(semanal):
    """Secuencia ADF, valores críticos y semáforo para cada ticker.

    Los valores críticos se obtienen con una sola simulación Monte Carlo para
    todos los largos de serie (S.valores_criticos_varios_largos).
    Devuelve un DataFrame largo: ticker, fecha, adf, sadf, cv_ventana_95,
    cv_sadf_95, semaforo.
    """
    log_precios = {t: np.log(semanal[t].dropna()) for t in semanal.columns}
    cvs = S.valores_criticos_varios_largos([len(s) for s in log_precios.values()],
                                           rezagos=C.REZAGOS_ADF, n_sim=C.N_SIM_MC,
                                           semilla=C.SEMILLA_MC)
    partes = []
    for t, lp in log_precios.items():
        T = len(lp)
        _, n0 = S.ventana_minima(T)
        cv_sadf, cv_secuencia = cvs[T]
        seq = S.secuencia_adf(lp, n0, rezagos=C.REZAGOS_ADF)
        df = pd.DataFrame({
            "ticker": t,
            "fecha": seq.index,
            "adf": seq.to_numpy(),
            "sadf": seq.cummax().to_numpy(),   # estadístico SADF con la información hasta cada fecha
            "cv_ventana_95": cv_secuencia[1],
            "cv_sadf_95": cv_sadf[0.95],
        })
        df["semaforo"] = semaforo(df["adf"], df["cv_ventana_95"], df["cv_sadf_95"])
        partes.append(df)
        log.info("%s: T = %d semanas, n0 = %d, semáforo actual %s", t, T, n0, df["semaforo"].iloc[-1])
    return pd.concat(partes, ignore_index=True)


def variables_riesgo(semanal):
    """Momentum, volatilidad anualizada y beta por ticker y semana (formato largo)."""
    retornos = np.log(semanal).diff()
    mercado = retornos[C.INDICE_MERCADO]

    momentum = semanal / semanal.shift(C.SEMANAS_MOMENTUM) - 1
    volatilidad = retornos.rolling(C.SEMANAS_VOLATILIDAD).std() * np.sqrt(C.SEMANAS_POR_ANO)
    # Join por fecha: cada columna se alinea con el retorno del mercado de la misma semana
    covarianza = retornos.rolling(C.SEMANAS_BETA).cov(mercado)
    beta = covarianza.div(mercado.rolling(C.SEMANAS_BETA).var(), axis=0)

    variables = {"momentum_52s": momentum, "volatilidad_anual": volatilidad, f"beta_{C.SEMANAS_BETA}s": beta}
    largo = pd.concat({k: v.stack() for k, v in variables.items()}, axis=1)
    largo.index.names = ["fecha", "ticker"]
    return largo.reset_index()


def construir_panel(validados, hoy=None, metodo="bsadf", ventana=C.VENTANA_BSADF):
    """Panel semanal completo: precio, señales del test, semáforo y variables.

    metodo: "bsadf" (vigente) o "anclado" (SADF anclado, solo referencia).
    ventana: largo de la ventana del BSADF (otro valor solo para sensibilidad).
    """
    semanal = a_semanal(validados, hoy)
    precios = semanal.stack().rename("adj_close").reset_index()
    precios.columns = ["fecha", "ticker", "adj_close"]
    senales = senales_bsadf(semanal, ventana) if metodo == "bsadf" else senales_sadf(semanal)

    panel = (precios
             .merge(senales, on=["ticker", "fecha"], how="left")
             .merge(variables_riesgo(semanal), on=["ticker", "fecha"], how="left")
             .sort_values(["ticker", "fecha"])
             .reset_index(drop=True))
    return panel


def semaforo_actual(panel):
    """Última semana de cada ticker, con las semanas consecutivas que lleva en
    el color actual."""
    panel = panel.dropna(subset=["semaforo"])
    filas = []
    for t, g in panel.groupby("ticker", sort=False):
        colores = g["semaforo"].to_numpy()
        cambio = np.flatnonzero(colores != colores[-1])
        semanas_en_estado = len(colores) - (cambio[-1] + 1 if len(cambio) else 0)
        fila = g.iloc[-1].to_dict()
        fila["semanas_en_estado"] = semanas_en_estado
        filas.append(fila)
    orden = {"rojo": 0, "amarillo": 1, "verde": 2}
    actual = pd.DataFrame(filas)
    estadistico = "bsadf" if "bsadf" in actual.columns else "adf"
    return actual.sort_values(["semaforo", estadistico],
                              key=lambda s: s.map(orden) if s.name == "semaforo" else -s)


def guardar(panel, actual):
    """Guarda el panel semanal y el semáforo actual (CSV)."""
    panel.to_csv(C.DIR_PROCESSED / "panel_semanal.csv", index=False)
    actual.to_csv(C.DIR_PROCESSED / "semaforo_actual.csv", index=False)
    log.info("Panel semanal y semáforo actual guardados en data/processed")
