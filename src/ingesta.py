# =============================================================================
# Capa 2 — Entradas: descarga y validación de precios diarios
#
# Propósito:
#   Descargar desde Yahoo Finance los precios diarios del universo (acciones e
#   índices), agregar metadatos (fuente, fecha/hora de descarga) y aplicar las
#   validaciones de calidad (docs/metodologia.md, sección 1):
#     1. Sin fechas duplicadas.                         → si falla, se excluye
#     2. Precios positivos.                             → si falla, se excluye
#     3. Volumen positivo: el día con volumen ≤ 0 se elimina y se registra
#        (error puntual de la fuente). No se exige a índices.
#     4. Sin huecos mayores a 5 días hábiles (incluye el final de la serie
#        frente a la última fecha del universo).        → si falla, se excluye
#        Índices: hasta 10 días hábiles (feriados largos de cada bolsa); cada
#        hueco mayor a 5 días se registra en el log con su fecha.
#     5. Variaciones diarias > 50%: se marcan para revisión (no excluyen).
#   Las series excluidas no pasan al reporte y quedan registradas en el log.
#
# Entradas:
#   - Tickers y parámetros de src/config.py.
#
# Salidas:
#   - data/raw/precios_diarios.csv: descarga original + metadatos.
#   - data/processed/precios_validados.csv: solo series válidas.
#   - data/processed/resumen_validacion.csv: resultado de cada validación por ticker.
#   - KPIs IL3: % de series validadas y % de columnas documentadas.
# =============================================================================

import logging
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from src import config as C

log = logging.getLogger("radar.ingesta")

COLUMNAS_PRECIO = ["open", "high", "low", "close", "adj_close"]
RENOMBRE_YF = {"Open": "open", "High": "high", "Low": "low", "Close": "close",
               "Adj Close": "adj_close", "Volume": "volume"}


def descargar(tickers, inicio=C.FECHA_INICIO, fin=None):
    """Descarga precios diarios y los devuelve en formato largo (una fila por
    ticker y fecha), con columnas de metadatos `fuente` y `fecha_descarga`.

    Un ticker sin datos (falla de la descarga) no aparece en el resultado; la
    validación lo detecta como faltante.
    """
    import yfinance as yf

    fecha_descarga = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with warnings.catch_warnings():
        # yfinance 1.7 emite avisos internos de deprecación de pandas (no afectan los datos)
        warnings.simplefilter("ignore")
        crudo = yf.download(list(tickers), start=inicio, end=fin, auto_adjust=False,
                            group_by="ticker", progress=False, threads=False)

    partes = []
    for t in tickers:
        if t not in crudo.columns.get_level_values(0):
            log.error("Descarga sin datos para %s", t)
            continue
        df = crudo[t].rename(columns=RENOMBRE_YF).dropna(how="all")  # quita fechas previas a la salida a bolsa
        if df.empty:
            log.error("Descarga sin datos para %s", t)
            continue
        df = df.rename_axis("fecha").reset_index()
        df.insert(0, "ticker", t)
        partes.append(df)

    largo = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    largo["fuente"] = C.FUENTE
    largo["fecha_descarga"] = fecha_descarga
    log.info("Descarga: %d de %d tickers con datos, %d filas", largo["ticker"].nunique() if partes else 0,
             len(tickers), len(largo))
    return largo


def es_indice(ticker):
    """Verdadero para índices: tickers que empiezan con ^ y los de C.OTROS_INDICES."""
    return ticker.startswith("^") or ticker in C.OTROS_INDICES


def _huecos_dias_habiles(fechas):
    """Días hábiles faltantes entre fechas consecutivas (lunes a viernes)."""
    f = np.asarray(fechas, dtype="datetime64[D]")
    return np.busday_count(f[:-1], f[1:]) - 1


def validar_serie(df, fecha_ultima_universo):
    """Valida la serie diaria de un ticker.

    Devuelve (serie_limpia, resultado), donde resultado es un dict con el
    detalle de cada validación y si la serie es válida.
    """
    ticker = df["ticker"].iloc[0]
    indice = es_indice(ticker)
    df = df.sort_values("fecha").reset_index(drop=True)
    motivos = []

    # 1. Fechas duplicadas
    duplicados = int(df["fecha"].duplicated().sum())
    if duplicados:
        motivos.append(f"{duplicados} fechas duplicadas")

    # Valores faltantes dentro de la serie (filas incompletas)
    incompletas = int(df[COLUMNAS_PRECIO + ["volume"]].isna().any(axis=1).sum())
    if incompletas:
        motivos.append(f"{incompletas} filas con valores faltantes")

    # 2. Precios positivos
    no_positivos = int((df[COLUMNAS_PRECIO] <= 0).any(axis=1).sum())
    if no_positivos:
        motivos.append(f"{no_positivos} días con precios no positivos")

    # 3. Volumen positivo: se elimina el día y se registra (no se exige a índices)
    if indice and not C.EXIGIR_VOLUMEN_INDICES:
        dias_vol_cero = []
    else:
        vol_cero = df["volume"] <= 0
        dias_vol_cero = df.loc[vol_cero, "fecha"].dt.strftime("%Y-%m-%d").tolist()
        for d in dias_vol_cero:
            log.warning("%s: día %s eliminado por volumen no positivo", ticker, d)
        df = df.loc[~vol_cero].reset_index(drop=True)

    # 4. Huecos: entre fechas consecutivas y al final de la serie
    fechas = list(df["fecha"]) + [fecha_ultima_universo]
    huecos = _huecos_dias_habiles(fechas)
    max_hueco = int(huecos.max()) if len(huecos) else 0
    limite = C.MAX_HUECO_DIAS_HABILES_INDICES if indice else C.MAX_HUECO_DIAS_HABILES
    if indice:
        for i in np.flatnonzero(huecos > C.MAX_HUECO_DIAS_HABILES):
            log.warning("%s: hueco de %d días hábiles tras %s (índice: permitido hasta %d)", ticker,
                        huecos[i], f"{fechas[i]:%Y-%m-%d}", limite)
    if max_hueco > limite:
        i = int(huecos.argmax())
        motivos.append(f"hueco de {max_hueco} días hábiles tras {fechas[i]:%Y-%m-%d}")

    # 5. Saltos diarios > 50%: se marcan para revisión
    variacion = df["adj_close"].pct_change().abs()
    df["revisar"] = variacion > C.UMBRAL_SALTO_DIARIO
    for idx in df.index[df["revisar"]]:
        log.warning("%s: variación diaria de %.0f%% el %s, marcada para revisión", ticker,
                    100 * variacion[idx], f"{df.at[idx, 'fecha']:%Y-%m-%d}")

    valida = not motivos
    resultado = {
        "ticker": ticker,
        "n_dias": len(df),
        "fecha_inicio": df["fecha"].min().date() if len(df) else None,
        "fecha_fin": df["fecha"].max().date() if len(df) else None,
        "duplicados": duplicados,
        "filas_incompletas": incompletas,
        "dias_precio_no_positivo": no_positivos,
        "dias_volumen_cero_eliminados": len(dias_vol_cero),
        "max_hueco_dias_habiles": max_hueco,
        "saltos_marcados_revision": int(df["revisar"].sum()),
        "valida": valida,
        "motivo_exclusion": "; ".join(motivos),
    }
    if valida:
        log.info("%s: serie válida (%d días)", ticker, len(df))
    else:
        log.error("%s: EXCLUIDA del reporte — %s", ticker, resultado["motivo_exclusion"])
    return df, resultado


def validar_universo(largo, tickers):
    """Valida todas las series. Los tickers sin datos cuentan como no válidos.

    Devuelve (precios_validados, resumen, kpi), donde kpi incluye el % de
    series validadas y si se activa la alerta de falla (< 98%).
    """
    fecha_ultima = largo["fecha"].max() if len(largo) else None
    limpias, resumen = [], []
    for t in tickers:
        serie = largo[largo["ticker"] == t]
        if serie.empty:
            resumen.append({"ticker": t, "n_dias": 0, "valida": False, "motivo_exclusion": "sin datos"})
            log.error("%s: EXCLUIDA del reporte — sin datos", t)
            continue
        limpia, res = validar_serie(serie, fecha_ultima)
        resumen.append(res)
        if res["valida"]:
            limpias.append(limpia)

    resumen = pd.DataFrame(resumen)
    pct = resumen["valida"].mean()
    kpi = {"series_validadas": int(resumen["valida"].sum()), "series_totales": len(tickers),
           "pct_validadas": pct, "meta": C.META_PCT_VALIDADAS, "alerta": pct < C.META_PCT_VALIDADAS}
    if kpi["alerta"]:
        log.error("ALERTA: solo %.1f%% de las series pasó las validaciones (meta ≥ %.0f%%)",
                  100 * pct, 100 * C.META_PCT_VALIDADAS)

    validados = pd.concat(limpias, ignore_index=True) if limpias else pd.DataFrame()
    return validados, resumen, kpi


def kpi_columnas_documentadas(df, ruta_diccionario=C.DIR_DOCS / "diccionario_datos.csv"):
    """KPI IL3: % de columnas del dataset que tienen definición y unidad en el
    diccionario de datos. Devuelve (porcentaje, lista de columnas sin documentar)."""
    dic = pd.read_csv(ruta_diccionario)
    documentadas = set(dic.dropna(subset=["definicion", "unidad"])["columna"])
    faltantes = [c for c in df.columns if c not in documentadas]
    return 1 - len(faltantes) / len(df.columns), faltantes


def guardar(crudo, validados, resumen, guardar_raw=True):
    """Guarda la descarga original, los datos validados y el resumen (CSV).
    guardar_raw=False en modo offline (data/raw es la entrada, no se reescribe)."""
    if guardar_raw:
        crudo.to_csv(C.DIR_RAW / "precios_diarios.csv", index=False)
    validados.to_csv(C.DIR_PROCESSED / "precios_validados.csv", index=False)
    resumen.to_csv(C.DIR_PROCESSED / "resumen_validacion.csv", index=False)
    log.info("Archivos guardados en %s", "data/raw y data/processed" if guardar_raw else "data/processed")
