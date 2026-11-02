# =============================================================================
# Capa 3 — Procesamiento: tests de burbuja SADF (Phillips, Wu y Yu, 2011) y
#          BSADF en ventana móvil (Phillips, Shi y Yu, 2015)
#
# Metodología vigente: BSADF en ventana móvil de 260 semanas
# (ver la sección al final del archivo). El SADF anclado al inicio de la serie
# se conserva como referencia (notebooks 01 y 03).
#
# Propósito:
#   Detectar crecimiento explosivo en una serie de precios. Se estima una
#   regresión ADF en ventanas crecientes que parten en la primera observación:
#     Δy_t = α + β·y_{t-1} + Σ φ_i·Δy_{t-i} + ε_t
#   - Caminata aleatoria (sin burbuja): β = 0.
#   - Crecimiento explosivo (burbuja): β > 0 → estadístico t de β grande y positivo.
#   El SADF es el máximo de esos estadísticos (¿hubo burbuja en la muestra?);
#   la secuencia completa de ADF recursivos permite fechar cuándo se enciende
#   y apaga la señal (base del semáforo).
#
# Entradas:
#   - Serie de log-precios (np.ndarray o pd.Series, sin valores faltantes).
#   - Parámetros: ventana mínima r0 = 0,01 + 1,8/√T (docs/metodologia.md); rezagos = 1.
#
# Salidas:
#   - Secuencia de ADF recursivos (pd.Series indexada por fecha de fin de ventana).
#   - Estadístico SADF (float).
#   - Valores críticos por simulación Monte Carlo (SADF y secuencia por fecha).
#   - Secuencia BSADF en ventana móvil y sus valores críticos (únicos para
#     toda acción y semana, porque la ventana es fija).
# =============================================================================

import numpy as np
import pandas as pd


def ventana_minima(T):
    """Ventana mínima de Phillips, Shi y Yu (2015): r0 = 0,01 + 1,8/√T.

    Devuelve la fracción r0 y el número de observaciones n0 = floor(r0·T).
    """
    r0 = 0.01 + 1.8 / np.sqrt(T)
    return r0, int(np.floor(r0 * T))


def _regresores_adf(y, rezagos):
    """Arma la variable dependiente (Δy_t) y la matriz X = [1, y_{t-1}, Δy_{t-1}, ...].

    La fila k corresponde a la observación t = k + rezagos + 1 de la serie y.
    Acepta y de forma (T,) o (n_series, T); las dimensiones iniciales se conservan.
    """
    dy = np.diff(y, axis=-1)
    Y = dy[..., rezagos:]
    columnas = [np.ones_like(Y), y[..., rezagos:-1]]
    for i in range(1, rezagos + 1):
        columnas.append(dy[..., rezagos - i: dy.shape[-1] - i])
    return Y, np.stack(columnas, axis=-1)


def adf_recursivo(y, n0, rezagos=1):
    """Estadístico t de β para cada ventana [0, w), con w = n0, ..., T.

    Usa sumas acumuladas de X'X, X'Y e Y'Y: cada ventana agrega una fila, así
    que todas las regresiones se resuelven de una vez (mismo resultado que
    correr un ADF por ventana, pero mucho más rápido).

    Devuelve un np.ndarray de largo T - n0 + 1 (una posición por ventana).
    Si y tiene forma (n_series, T), procesa todas las series a la vez y
    devuelve (n_series, T - n0 + 1); se usa así en el Monte Carlo.
    """
    y = np.asarray(y, dtype=float)
    Y, X = _regresores_adf(y, rezagos)
    K = X.shape[-1]

    # Acumulados fila a fila (a lo largo del eje del tiempo)
    XX = np.cumsum(X[..., :, None] * X[..., None, :], axis=-3)
    XY = np.cumsum(X * Y[..., None], axis=-2)
    YY = np.cumsum(Y ** 2, axis=-1)

    # Una ventana de w niveles tiene w - rezagos - 1 filas de regresión
    filas = np.arange(n0, y.shape[-1] + 1) - rezagos - 1
    idx = filas - 1
    return _t_beta(XX[..., idx, :, :], XY[..., idx, :], YY[..., idx], filas, K)


def _t_beta(XX, XY, YY, filas, K):
    """Estadístico t de β (coeficiente de y_{t-1}) a partir de X'X, X'Y, Y'Y
    y el número de filas de cada regresión (MCO con varianza homocedástica)."""
    XX_inv = np.linalg.inv(XX)
    b = np.einsum("...ij,...j->...i", XX_inv, XY)
    ssr = YY - np.einsum("...i,...i->...", b, XY)
    s2 = ssr / (filas - K)
    se_beta = np.sqrt(s2 * XX_inv[..., 1, 1])
    return b[..., 1] / se_beta


def secuencia_adf(serie, n0, rezagos=1):
    """Igual que adf_recursivo, pero devuelve una pd.Series indexada por la
    fecha de término de cada ventana."""
    valores = adf_recursivo(serie.to_numpy(), n0, rezagos)
    return pd.Series(valores, index=serie.index[n0 - 1:], name="adf_recursivo")


def sadf(serie, n0, rezagos=1):
    """Estadístico SADF: máximo de la secuencia de ADF recursivos."""
    return float(np.max(adf_recursivo(np.asarray(serie), n0, rezagos)))


def _simular_secuencias(T, n0, rezagos, n_sim, semilla, lote):
    """Secuencias de ADF recursivos de n_sim caminatas aleatorias de largo T.

    Las series se simulan en lotes de `lote`; los números aleatorios salen en
    el mismo orden que simulando una por una, así que el resultado no depende
    del tamaño del lote. Devuelve un arreglo float32 (n_sim × ventanas) para
    acotar memoria (20.000 sim × 1.650 ventanas ≈ 130 MB).
    """
    rng = np.random.default_rng(semilla)
    secuencias = np.empty((n_sim, T - n0 + 1), dtype=np.float32)
    for ini in range(0, n_sim, lote):
        fin = min(ini + lote, n_sim)
        y = np.cumsum(1.0 / T + rng.standard_normal((fin - ini, T)), axis=1)
        secuencias[ini:fin] = adf_recursivo(y, n0, rezagos)
    return secuencias


def valores_criticos_mc(T, n0, rezagos=1, n_sim=2000, cuantiles=(0.90, 0.95, 0.99), semilla=42,
                        lote=50):
    """Valores críticos por simulación Monte Carlo bajo la hipótesis nula.

    Nula (Phillips, Shi y Yu, 2015): caminata aleatoria con deriva despreciable,
        y_t = T^{-1} + y_{t-1} + ε_t,   ε_t ~ N(0, 1).
    Se simulan n_sim series del mismo largo T y se calcula para cada una la
    secuencia de ADF recursivos.

    Devuelve:
      - cv_sadf: dict {cuantil: valor crítico del SADF (máximo de la secuencia)}.
      - cv_secuencia: np.ndarray (cuantiles × ventanas) con el valor crítico de
        cada ADF recursivo, usado para fechar la señal ventana a ventana.
    """
    secuencias = _simular_secuencias(T, n0, rezagos, n_sim, semilla, lote)
    q = np.array(cuantiles)
    cv_sadf = dict(zip(cuantiles, np.quantile(secuencias.max(axis=1), q)))
    cv_secuencia = np.quantile(secuencias, q, axis=0)
    return cv_sadf, cv_secuencia


def valores_criticos_varios_largos(largos, rezagos=1, n_sim=20000, cuantiles=(0.90, 0.95, 0.99),
                                   semilla=42, lote=50):
    """Valores críticos para varias series de distinto largo con UNA simulación.

    El ADF de la ventana [0, w) no depende del largo total de la serie, así que
    se simula una vez con el largo máximo y, para cada largo T, se toman las
    ventanas n0(T), ..., T. Aproximación: la deriva de la nula se fija en
    1/T_max en vez de 1/T (despreciable frente a shocks de varianza 1).

    largos: iterable de largos T (uno por serie; se aceptan repetidos).
    Devuelve: dict {T: (cv_sadf, cv_secuencia)} con el mismo formato que
    valores_criticos_mc.
    """
    largos = sorted(set(int(T) for T in largos))
    n0_por_largo = {T: ventana_minima(T)[1] for T in largos}
    T_max, n0_min = max(largos), min(n0_por_largo.values())
    secuencias = _simular_secuencias(T_max, n0_min, rezagos, n_sim, semilla, lote)

    q = np.array(cuantiles)
    resultado = {}
    for T, n0 in n0_por_largo.items():
        tramo = secuencias[:, n0 - n0_min: T - n0_min + 1]
        cv_sadf = dict(zip(cuantiles, np.quantile(tramo.max(axis=1), q)))
        resultado[T] = (cv_sadf, np.quantile(tramo, q, axis=0))
    return resultado


# -----------------------------------------------------------------------------
# BSADF en ventana móvil (versión acotada del GSADF de Phillips, Shi y Yu, 2015)
# Metodología vigente del semáforo; las funciones de arriba
# (SADF anclado al inicio de la serie) quedan como referencia.
# -----------------------------------------------------------------------------

def adf_hacia_atras(y, n0, rezagos=1):
    """Estadístico t de β para cada ventana [s, T) que TERMINA en la última
    observación, con inicio s = 0, ..., T - n0 (largos T, ..., n0).

    Las filas de regresión de la ventana [s, T) son las últimas filas de la
    regresión de [0, T): basta acumular X'X, X'Y e Y'Y desde el final (sumas
    de sufijo) para resolver todas las ventanas de una vez.

    Acepta y de forma (T,) o (n_series, T); devuelve (..., T - n0 + 1).
    """
    y = np.asarray(y, dtype=float)
    Y, X = _regresores_adf(y, rezagos)
    K = X.shape[-1]
    N = Y.shape[-1]

    sufijo = lambda a, eje: np.flip(np.cumsum(np.flip(a, axis=eje), axis=eje), axis=eje)
    XX = sufijo(X[..., :, None] * X[..., None, :], -3)
    XY = sufijo(X * Y[..., None], -2)
    YY = sufijo(Y ** 2, -1)

    # La ventana que parte en s usa las filas s, ..., N-1
    inicios = np.arange(0, y.shape[-1] - n0 + 1)
    filas = N - inicios
    return _t_beta(XX[..., inicios, :, :], XY[..., inicios, :], YY[..., inicios], filas, K)


def bsadf_movil(serie, ventana=260, rezagos=1):
    """Secuencia BSADF en ventana móvil.

    Para cada semana t (desde que hay `ventana` observaciones), BSADF_t es el
    máximo del ADF de las regresiones que terminan en t y parten en cualquier
    semana de las últimas `ventana`, con largo mínimo n0 = floor(r0·ventana),
    r0 = 0,01 + 1,8/√ventana.

    Devuelve una pd.Series indexada por fecha (vacía si la serie es más corta
    que la ventana).
    """
    _, n0 = ventana_minima(ventana)
    y = serie.to_numpy(dtype=float)
    if len(y) < ventana:
        return pd.Series(dtype=float, name="bsadf")
    ventanas = np.lib.stride_tricks.sliding_window_view(y, ventana)   # (T - ventana + 1, ventana)
    bsadf = adf_hacia_atras(ventanas, n0, rezagos).max(axis=-1)
    return pd.Series(bsadf, index=serie.index[ventana - 1:], name="bsadf")


def valores_criticos_bsadf(ventana=260, rezagos=1, n_sim=20000, cuantiles=(0.90, 0.95, 0.99),
                           semilla=42, lote=500):
    """Valores críticos del BSADF en ventana móvil por Monte Carlo.

    Nula (Phillips, Shi y Yu, 2015) sobre una ventana: y_t = ventana^{-1} + y_{t-1} + ε_t.
    Como la ventana tiene siempre el mismo largo, la distribución del BSADF
    es la misma para toda acción y semana: se simula una sola vez.

    Devuelve dict {cuantil: valor crítico}.
    """
    _, n0 = ventana_minima(ventana)
    rng = np.random.default_rng(semilla)
    maximos = np.empty(n_sim)
    for ini in range(0, n_sim, lote):
        fin = min(ini + lote, n_sim)
        y = np.cumsum(1.0 / ventana + rng.standard_normal((fin - ini, ventana)), axis=1)
        maximos[ini:fin] = adf_hacia_atras(y, n0, rezagos).max(axis=-1)
    return dict(zip(cuantiles, np.quantile(maximos, np.array(cuantiles))))


def primera_senal(secuencia, cv):
    """Primera fecha en que la secuencia de ADF supera su valor crítico.

    cv puede ser un escalar o un arreglo del mismo largo que la secuencia.
    Devuelve None si la señal nunca se enciende.
    """
    encendida = secuencia > cv
    return encendida.idxmax() if encendida.any() else None
