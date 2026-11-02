# =============================================================================
# Capa 7 — KPIs: backtest de la regla de alerta (KPI IL5) y tabla de KPIs
#
# Propósito:
#   Medir si seguir el semáforo habría reducido la caída máxima frente a
#   mantener la cartera al 100%. Regla fijada ANTES de ver resultados:
#     - Rojo → exposición 50%. Verde → 100%. Amarillo → mantiene la anterior.
#     - La señal de la semana t (cierre del viernes) se ejecuta al cierre de
#       t+1; la nueva exposición rige desde el retorno de la semana t+2.
#     - La parte no invertida rinde 0% (supuesto conservador).
#     - Costo de transacción: 0% (base) o un % sobre el monto transado,
#       costo × |cambio de exposición| (sensibilidad: 0,1%).
#   Control placebo: reglas aleatorias con el mismo número y duración de
#   episodios de exposición reducida, en fechas al azar (en carteras de
#   varias acciones, por acción).
#   Regla v2 (definida después de evaluar la v1): igual a la v1,
#   pero al terminar un episodio rojo la exposición se mantiene en 50% durante
#   52 semanas de enfriamiento. Se valida fuera de muestra con un criterio de
#   éxito fijado antes de evaluarla. La v1 se conserva.
#
# Entradas:
#   - Retornos semanales y semáforo semanal (src/features.py).
#   - logs/*.log y data/processed/resumen_validacion.csv (tabla de KPIs).
#
# Salidas:
#   - Series de retornos y valor de la cartera con y sin regla.
#   - Métricas: caída máxima, retorno anual compuesto, volatilidad, Sharpe,
#     cambios de exposición, % del tiempo reducida, anticipación del rojo.
#   - Distribución placebo de la caída máxima y percentil de la regla.
#   - Tabla de KPIs IL3, IL4 e IL5.
# =============================================================================

import re

import numpy as np
import pandas as pd

from src import config as C

EXPOSICION_ROJO = 0.5
EXPOSICION_VERDE = 1.0
REZAGO_EJECUCION = 2      # señal en t → rige desde el retorno de t+2
SEMANAS_POR_ANO = C.SEMANAS_POR_ANO


# --- Regla y simulación --------------------------------------------------------

def exposicion_objetivo(colores, inicial=EXPOSICION_VERDE):
    """Exposición que indica el semáforo cada semana (antes del rezago).

    Rojo → 50%, verde → 100%, amarillo → mantiene la exposición anterior.
    """
    expo, salida = inicial, []
    for color in colores:
        if color == "rojo":
            expo = EXPOSICION_ROJO
        elif color == "verde":
            expo = EXPOSICION_VERDE
        salida.append(expo)
    return pd.Series(salida, index=colores.index, name="exposicion_objetivo")


def exposicion_objetivo_v2(colores, enfriamiento=C.SEMANAS_ENFRIAMIENTO, inicial=EXPOSICION_VERDE):
    """Regla v2 con enfriamiento.

    - Rojo → exposición 50%.
    - Al terminar un episodio rojo (el semáforo sale de rojo), la exposición
      sigue en 50% durante `enfriamiento` semanas y luego vuelve a 100%. La
      primera semana fuera de rojo es la semana 1 del enfriamiento.
    - Un rojo nuevo durante el enfriamiento lo interrumpe; el contador parte
      de nuevo cuando ese episodio rojo termine.
    - Amarillo y verde mantienen la exposición vigente mientras dure el
      enfriamiento (y fuera de él, amarillo mantiene y verde vuelve a 100%).
    """
    expo, semanas_enfriamiento, previo, salida = inicial, None, None, []
    for color in colores:
        if color == "rojo":
            expo, semanas_enfriamiento = EXPOSICION_ROJO, None
        else:
            if previo == "rojo":
                semanas_enfriamiento = 0
            if semanas_enfriamiento is not None:
                semanas_enfriamiento += 1
                if semanas_enfriamiento > enfriamiento:
                    expo, semanas_enfriamiento = EXPOSICION_VERDE, None
            if semanas_enfriamiento is None and color == "verde":
                expo = EXPOSICION_VERDE
        previo = color
        salida.append(expo)
    return pd.Series(salida, index=colores.index, name="exposicion_objetivo_v2")


def exposicion_efectiva(objetivo, inicial=EXPOSICION_VERDE):
    """Exposición aplicada al retorno de cada semana: la decidida con la señal
    de dos semanas antes (ejecución al cierre de t+1, rige desde t+2)."""
    return objetivo.shift(REZAGO_EJECUCION).fillna(inicial).rename("exposicion")


def retornos_regla(retornos, exposicion, costo=0.0):
    """Retorno semanal de la cartera con la regla.

    La parte no invertida rinde 0%. El costo se cobra la semana en que rige la
    nueva exposición, como costo × |cambio de exposición|.
    """
    expo = exposicion.reindex(retornos.index)
    cambio = expo.diff().abs().fillna(0.0)
    return expo * retornos - costo * cambio


def valor_cartera(retornos):
    """Valor acumulado partiendo de 1 (incluye el punto inicial)."""
    valor = (1 + retornos).cumprod()
    inicio = pd.Series([1.0], index=[retornos.index[0] - pd.Timedelta(days=7)])
    return pd.concat([inicio, valor])


def drawdown(retornos):
    """Caída desde el máximo previo, semana a semana."""
    valor = valor_cartera(retornos)
    return valor / valor.cummax() - 1


def metricas(retornos, exposicion=None):
    """Métricas de desempeño de una serie de retornos semanales."""
    valor = valor_cartera(retornos)
    vol = retornos.std() * np.sqrt(SEMANAS_POR_ANO)
    m = {
        "caida_maxima": drawdown(retornos).min(),
        "retorno_anual": valor.iloc[-1] ** (SEMANAS_POR_ANO / len(retornos)) - 1,
        "volatilidad_anual": vol,
        "sharpe": retornos.mean() * SEMANAS_POR_ANO / vol if vol > 0 else np.nan,
        "retorno_total": valor.iloc[-1] - 1,
    }
    if exposicion is not None:
        expo = exposicion.reindex(retornos.index)
        m["cambios_exposicion"] = int((expo.diff().abs() > 0).sum())
        m["pct_tiempo_reducida"] = (expo < EXPOSICION_VERDE).mean()
    return m


def comparar(retornos, exposicion, costo=0.0):
    """Tabla regla vs. mantener el 100% en el periodo de `retornos`."""
    regla = retornos_regla(retornos, exposicion, costo)
    tabla = pd.DataFrame({"Regla": metricas(regla, exposicion),
                          "Mantener 100%": metricas(retornos, pd.Series(1.0, index=retornos.index))})
    return tabla, regla


def cartera_igual_peso(retornos, exposiciones, costo=0.0):
    """Cartera de igual peso con rebalanceo semanal: cada acción es 1/N del
    capital y se invierte según su propia exposición. Devuelve los retornos
    semanales de la cartera con regla y sin regla (100%)."""
    cambio = exposiciones.diff().abs().fillna(0.0)
    regla = (exposiciones * retornos - costo * cambio).mean(axis=1)
    return regla, retornos.mean(axis=1)


def metricas_cartera(retornos_regla_, retornos_bh, exposiciones):
    """Métricas de la cartera de igual peso. Para la regla, los cambios de
    exposición se suman entre acciones y el % del tiempo reducida es el
    promedio entre acciones."""
    regla = metricas(retornos_regla_)
    regla["cambios_exposicion"] = int((exposiciones.diff().abs() > 0).sum().sum())
    regla["pct_tiempo_reducida"] = (exposiciones < EXPOSICION_VERDE).mean().mean()
    bh = metricas(retornos_bh)
    bh["cambios_exposicion"], bh["pct_tiempo_reducida"] = 0, 0.0
    return pd.DataFrame({"Regla": regla, "Mantener 100%": bh})


def episodio(precio, inicio_busqueda, fin_busqueda_peak, fin_busqueda_valle, semanas_previas=52):
    """Define un episodio de caída a partir de los datos:
      - peak: máximo del precio entre inicio_busqueda y fin_busqueda_peak;
      - valle: mínimo posterior al peak hasta fin_busqueda_valle;
      - inicio de la evaluación: `semanas_previas` antes del peak, para incluir
        la fase de alza (donde debería encenderse la señal y donde se paga el
        costo de reducir exposición).
    """
    peak = precio.loc[inicio_busqueda:fin_busqueda_peak].idxmax()
    valle = precio.loc[peak:fin_busqueda_valle].idxmin()
    return {"inicio": peak - pd.Timedelta(weeks=semanas_previas), "peak": peak, "valle": valle,
            "caida_indice": precio.loc[valle] / precio.loc[peak] - 1}


# --- Anticipación ---------------------------------------------------------------

def anticipacion_rojo(colores, fecha_peak, max_semanas=52):
    """Semanas entre el inicio del último episodio rojo (con persistencia)
    que empezó en o antes del peak y el peak.

    - Si el rojo está vigente en el peak, cuenta desde el inicio de ese
      episodio, aunque haya empezado hace más de `max_semanas`.
    - Si el último rojo terminó antes del peak, cuenta solo si empezó en las
      `max_semanas` previas (un rojo más antiguo no anticipa ese peak).
    Devuelve None si no hay señal que cumpla.
    """
    previas = colores.loc[:fecha_peak]
    es_rojo = previas == "rojo"
    inicios = previas.index[es_rojo & ~es_rojo.shift(fill_value=False)]
    if len(inicios) == 0:
        return None
    vigente_en_peak = bool(es_rojo.iloc[-1])
    if not vigente_en_peak and inicios[-1] < fecha_peak - pd.Timedelta(weeks=max_semanas):
        return None
    return (fecha_peak - inicios[-1]).days // 7


# --- Placebo --------------------------------------------------------------------

def episodios(mascara):
    """Duraciones de los tramos consecutivos donde la máscara es verdadera."""
    m = np.asarray(mascara, dtype=bool)
    cambios = np.flatnonzero(np.diff(np.concatenate([[False], m, [False]]).astype(int)))
    return cambios[1::2] - cambios[0::2]


def mascara_aleatoria(n, duraciones, rng):
    """Máscara de largo n con los mismos episodios (duraciones permutadas) en
    posiciones al azar, separados por al menos una semana.

    Las semanas libres se reparten en los k+1 huecos de forma uniforme sobre
    todas las combinaciones posibles: se eligen k separadores distintos entre
    libres + k posiciones (método de "barras y estrellas").
    No usar una multinomial con probabilidades iguales: deja huecos casi del
    mismo tamaño y episodios casi equiespaciados (no al azar).
    """
    duraciones = rng.permutation(duraciones)
    k = len(duraciones)
    libres = n - duraciones.sum() - max(k - 1, 0)       # semanas libres tras exigir separación de 1
    if k == 0 or libres < 0:
        return np.zeros(n, dtype=bool)
    separadores = np.sort(rng.choice(libres + k, size=k, replace=False))
    huecos = np.diff(np.concatenate([[-1], separadores])) - 1    # hueco antes de cada episodio (≥ 0)
    huecos[1:] += 1
    mascara, pos = np.zeros(n, dtype=bool), 0
    for hueco, dur in zip(huecos[:k], duraciones):
        pos += hueco
        mascara[pos:pos + dur] = True
        pos += dur
    return mascara


def exposiciones_placebo(exposicion, n=1000, semilla=C.SEMILLA_MC):
    """Matriz (n × semanas) de exposiciones aleatorias con el mismo número y
    duración de episodios reducidos que `exposicion`."""
    rng = np.random.default_rng(semilla)
    duraciones = episodios(exposicion.to_numpy() < EXPOSICION_VERDE)
    return np.array([np.where(mascara_aleatoria(len(exposicion), duraciones, rng), EXPOSICION_ROJO, EXPOSICION_VERDE)
                     for _ in range(n)])


def caida_maxima_matriz(retornos_matriz):
    """Caída máxima de cada fila de una matriz (n × semanas) de retornos."""
    valor = np.cumprod(1 + retornos_matriz, axis=1)
    valor = np.concatenate([np.ones((valor.shape[0], 1)), valor], axis=1)
    return (valor / np.maximum.accumulate(valor, axis=1) - 1).min(axis=1)


def percentil_placebo(caida_real, caidas_placebo):
    """% de reglas placebo con una caída máxima MENOS severa que la regla real.
    Bajo = la regla real está entre las mejores (la señal aporta).
    Devuelve NaN ("no aplica") si todas las reglas placebo dan la misma caída
    que la real: ocurre cuando la regla nunca reduce la exposición y los
    placebos quedan idénticos a ella, así que no hay nada que comparar."""
    caidas_placebo = np.asarray(caidas_placebo)
    if np.allclose(caidas_placebo, caida_real):
        return np.nan
    return 100 * np.mean(caidas_placebo > caida_real)


# --- Evaluación de reglas v1 y v2 sobre una serie ---------------------------------

def objetivo_regla(colores, regla, enfriamiento=C.SEMANAS_ENFRIAMIENTO):
    """Exposición objetivo según la regla: "v1" o "v2" (con enfriamiento)."""
    if regla == "v1":
        return exposicion_objetivo(colores)
    return exposicion_objetivo_v2(colores, enfriamiento)


def evaluar_serie(precio, colores, reglas=("v1", "v2"), enfriamiento=C.SEMANAS_ENFRIAMIENTO,
                  n_placebo=1000, semilla=C.SEMILLA_MC):
    """Prepara la evaluación de una serie desde su primera semana con señal.

    Devuelve un dict con los retornos semanales y, por regla, la exposición
    efectiva (con el rezago de ejecución) y 1.000 exposiciones placebo con el
    mismo número y duración de episodios reducidos en el periodo completo.
    """
    retornos = precio.pct_change().loc[colores.index[0]:].iloc[1:]
    evaluacion = {"retornos": retornos, "reglas": {}}
    for regla in reglas:
        expo = exposicion_efectiva(objetivo_regla(colores, regla, enfriamiento)).reindex(retornos.index)
        expo = expo.fillna(EXPOSICION_VERDE)
        evaluacion["reglas"][regla] = {"exposicion": expo,
                                       "placebos": exposiciones_placebo(expo, n_placebo, semilla)}
    return evaluacion


def tabla_ventana(evaluacion, inicio=None, fin=None, costo=0.0):
    """Métricas de cada regla y de mantener el 100% en [inicio, fin], con el
    percentil placebo de cada regla. Los placebos se generan sobre el periodo
    completo de la serie y se miden dentro de la ventana (mismo método que el
    notebook 06).

    Si la regla no reduce la exposición ni una semana dentro de la ventana,
    el percentil es NaN ("no aplica"): la regla es idéntica a mantener el
    100% y el percentil solo reflejaría empates con los placebos que tampoco
    actuaron allí, no el valor de la señal."""
    retornos = evaluacion["retornos"].loc[inicio:fin]
    en_ventana = evaluacion["retornos"].index.isin(retornos.index)
    columnas = {"Mantener 100%": {**metricas(retornos, pd.Series(EXPOSICION_VERDE, index=retornos.index)),
                                  "percentil_placebo": np.nan}}
    for regla, datos in evaluacion["reglas"].items():
        expo = datos["exposicion"].loc[retornos.index]
        m = metricas(retornos_regla(retornos, expo, costo), expo)
        caidas = caida_maxima_matriz(datos["placebos"][:, en_ventana] * retornos.to_numpy())
        actua = bool((expo < EXPOSICION_VERDE).any())
        m["percentil_placebo"] = percentil_placebo(m["caida_maxima"], caidas) if actua else np.nan
        columnas[regla] = m
    return pd.DataFrame(columnas)


# --- Tabla de KPIs ----------------------------------------------------------------

def leer_ejecuciones(dir_logs=C.DIR_LOGS):
    """Lee las líneas RESUMEN_EJECUCION de los logs de main.py."""
    filas = []
    for ruta in sorted(dir_logs.glob("radar_*.log")):
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "RESUMEN_EJECUCION" in linea:
                filas.append(dict(re.findall(r"(\w+)=(\S+)", linea)))
    return pd.DataFrame(filas)


def tabla_kpis(il5):
    """Tabla de KPIs IL3, IL4 e IL5 con los valores medidos.

    il5: lista de dicts {"KPI", "valor", "meta", "fuente"} con los resultados
    del backtest (se arma en el notebook 06).
    """
    from src import ingesta as I

    resumen = pd.read_csv(C.DIR_PROCESSED / "resumen_validacion.csv")
    validados = pd.read_csv(C.DIR_PROCESSED / "precios_validados.csv", nrows=5)
    pct_cols, _ = I.kpi_columnas_documentadas(validados)
    filas = [
        {"nivel": "IL3", "KPI": "% de series con historia completa y validada",
         "valor": f"{resumen['valida'].mean():.0%} ({resumen['valida'].sum()}/{len(resumen)})",
         "meta": "≥ 98%", "fuente": "resumen_validacion.csv"},
        {"nivel": "IL3", "KPI": "% de columnas documentadas en el diccionario", "valor": f"{pct_cols:.0%}",
         "meta": "100%", "fuente": "docs/diccionario_datos.csv"},
    ]
    ejecuciones = leer_ejecuciones()
    if ejecuciones.empty:
        filas += [{"nivel": "IL4", "KPI": k, "valor": "sin ejecuciones de main.py", "meta": m, "fuente": "logs/"}
                  for k, m in (("% de ejecuciones sin error", "100%"), ("Duración de la ejecución", "< 5 min"))]
    else:
        ok = (ejecuciones["estado"] == "OK").mean()
        duraciones = ejecuciones["duracion_s"].astype(float)
        filas += [
            {"nivel": "IL4", "KPI": "% de ejecuciones sin error",
             "valor": f"{ok:.0%} ({(ejecuciones['estado'] == 'OK').sum()}/{len(ejecuciones)})",
             "meta": "100%", "fuente": "logs/radar_*.log"},
            {"nivel": "IL4", "KPI": "Duración de la ejecución",
             "valor": f"máx. {duraciones.max():.0f} s (mediana {duraciones.median():.0f} s)",
             "meta": "< 5 min", "fuente": "logs/radar_*.log"},
        ]
    filas += [{"nivel": "IL5", **k} for k in il5]
    return pd.DataFrame(filas)
