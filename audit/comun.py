# =============================================================================
# Auditoría independiente — funciones propias del auditor
#
# Propósito: reimplementar desde cero, sin importar src/, lo necesario para
#   recalcular resultados: cierre semanal, ADF (MCO con numpy.linalg.lstsq),
#   BSADF en ventana móvil (bucle simple), semáforo, persistencia, reglas de
#   exposición v1/v2 y métricas de desempeño.
# Entradas: CSV de data/raw.
# Salidas: funciones usadas por los scripts audit/a*.py.
# =============================================================================

from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DIR_AUDIT = RAIZ / "audit"
VENTANA = 260
N0 = int(np.floor((0.01 + 1.8 / np.sqrt(VENTANA)) * VENTANA))     # 31


# --- Datos ----------------------------------------------------------------------

def leer_crudo(nombre):
    return pd.read_csv(RAIZ / "data" / "raw" / nombre, parse_dates=["fecha"])


def es_indice(ticker):
    return ticker.startswith("^") or ticker == "000001.SS"


def limpiar(df):
    """Regla vigente: acciones pierden los días con volumen <= 0; índices no."""
    df = df.sort_values("fecha")
    if not es_indice(df["ticker"].iloc[0]):
        df = df[df["volume"] > 0]
    return df


def semanal(df, hasta=None):
    """Último cierre ajustado de cada semana (viernes)."""
    s = limpiar(df).set_index("fecha")["adj_close"].resample("W-FRI").last().dropna()
    return s if hasta is None else s[s.index <= pd.Timestamp(hasta)]


# --- Test ADF y BSADF -------------------------------------------------------------

def adf_t(w):
    """t de beta en Δy_t = a + b·y_{t-1} + c·Δy_{t-1} + e (MCO, varianza clásica)."""
    w = np.asarray(w, dtype=float)
    dy = np.diff(w)
    Y = dy[1:]
    X = np.column_stack([np.ones(len(Y)), w[1:-1], dy[:-1]])
    coef, _, _, _ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ coef
    s2 = resid @ resid / (len(Y) - 3)
    cov = s2 * np.linalg.inv(X.T @ X)
    return coef[1] / np.sqrt(cov[1, 1])


def bsadf_semana(y, t):
    """BSADF de la semana t (índice): máximo del ADF de [s, t], s en las últimas VENTANA semanas."""
    tramo = y[t - VENTANA + 1: t + 1]
    return max(adf_t(tramo[s:]) for s in range(VENTANA - N0 + 1))


def bsadf_serie(log_precio):
    """BSADF de todas las semanas con ventana completa (pd.Series)."""
    y = log_precio.to_numpy()
    idx = range(VENTANA - 1, len(y))
    return pd.Series([bsadf_semana(y, t) for t in idx], index=log_precio.index[VENTANA - 1:])


# --- Semáforo y persistencia -------------------------------------------------------

def color_bruto(b, amarillo, rojo):
    return np.where(b > rojo, 2, np.where(b > amarillo, 1, 0))      # 0 verde, 1 amarillo, 2 rojo


def persistir(niveles, n=6):
    """Escrito de nuevo: el color cambia si las últimas n semanas están todas sobre
    (sube al mínimo) o todas bajo (baja al máximo) el nivel vigente. Parte en verde."""
    estado, salida = 0, []
    for i in range(len(niveles)):
        if i + 1 >= n:
            ult = niveles[i + 1 - n: i + 1]
            if all(v > estado for v in ult):
                estado = min(ult)
            elif all(v < estado for v in ult):
                estado = max(ult)
        salida.append(estado)
    return np.array(salida)


NOMBRE = {0: "verde", 1: "amarillo", 2: "rojo"}


def semanas_en_color(niveles):
    ultimo, n = niveles[-1], 0
    for v in niveles[::-1]:
        if v != ultimo:
            break
        n += 1
    return n


def tramos(mascara):
    """Lista de (inicio, largo) de tramos verdaderos."""
    m = list(mascara) + [False]
    salida, ini = [], None
    for i, v in enumerate(m):
        if v and ini is None:
            ini = i
        if not v and ini is not None:
            salida.append((ini, i - ini))
            ini = None
    return salida


# --- Reglas de exposición y métricas ----------------------------------------------

def expo_v1(niveles):
    e, out = 1.0, []
    for v in niveles:
        e = 0.5 if v == 2 else (1.0 if v == 0 else e)
        out.append(e)
    return np.array(out)


def expo_v2(niveles, enfriamiento=52):
    e, contador, prev, out = 1.0, None, None, []
    for v in niveles:
        if v == 2:
            e, contador = 0.5, None
        else:
            if prev == 2:
                contador = 0
            if contador is not None:
                contador += 1
                if contador > enfriamiento:
                    e, contador = 1.0, None
            if contador is None and v == 0:
                e = 1.0
        prev = v
        out.append(e)
    return np.array(out)


def aplicar_rezago(expo_por_semana, rezago=2):
    """Exposición que rige el retorno de cada semana: la decidida `rezago` semanas antes."""
    e = np.asarray(expo_por_semana, dtype=float)
    return np.concatenate([np.ones(rezago), e[:-rezago]])


def caida_maxima(r):
    v = np.concatenate([[1.0], np.cumprod(1 + np.asarray(r))])
    return float((v / np.maximum.accumulate(v) - 1).min())


def retorno_anual(r):
    return float(np.prod(1 + np.asarray(r)) ** (52 / len(r)) - 1)


def sharpe(r):
    r = np.asarray(r)
    return float(r.mean() * 52 / (r.std(ddof=1) * np.sqrt(52)))
