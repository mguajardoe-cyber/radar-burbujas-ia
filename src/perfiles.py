# =============================================================================
# Capa 3 — Procesamiento: perfiles de riesgo con K-Means (Módulo 6)
#
# Propósito:
#   Agrupar las semanas históricas de las 9 acciones (cada acción en cada
#   semana con las 4 variables completas, no solo los 9 puntos de hoy) según
#   BSADF, momentum, volatilidad y beta, estandarizadas (media 0, desviación 1).
#   - k se elige entre 2 y 6 con Silhouette y el método del codo
#     (C.TOLERANCIA_SILHOUETTE; justificación en notebooks/04_kmeans.ipynb).
#   - Cada grupo recibe un nombre en palabras simples según su centroide
#     (variables con z ≥ 0,75: "explosivo", "alcista", "volátil", "sensible al
#     mercado"; si ninguna, "estable" o "moderado").
#   - Cada acción recibe el perfil de su semana actual (centroide más cercano).
#   El modelo (medias, escalas, centroides y nombres) se guarda en JSON y
#   main.py lo reutiliza sin reentrenar; se recalibra cada trimestre
#   (docs/gobernanza.md). Los perfiles son DESCRIPTIVOS: no cambian el
#   semáforo, el backtest ni los KPIs.
#
# Entradas:
#   - Panel semanal (src/features.py) y parámetros de src/config.py.
#
# Salidas:
#   - data/processed/perfiles_kmeans.json (modelo y diagnóstico de k).
#   - Columna perfil_riesgo del semáforo actual (hoja Variables del Excel).
# =============================================================================

import json
import logging

import numpy as np
import pandas as pd

from src import config as C

log = logging.getLogger("radar.perfiles")

VARIABLES = list(C.VARIABLES_PERFIL)
DESCRIPTOR = {"bsadf": "explosivo", "momentum_52s": "alcista", "volatilidad_anual": "volátil",
              "beta_104s": "sensible al mercado"}


def datos_historicos(panel, tickers=None):
    """Semanas de las acciones del universo con las 4 variables completas."""
    tickers = list(C.UNIVERSO) if tickers is None else tickers
    return panel[panel["ticker"].isin(tickers)].dropna(subset=VARIABLES).reset_index(drop=True)


def estandarizar(datos):
    """(matriz estandarizada, medias, desviaciones) con desviación poblacional,
    igual que StandardScaler de scikit-learn."""
    x = datos[VARIABLES].to_numpy(dtype=float)
    media, escala = x.mean(axis=0), x.std(axis=0)
    return (x - media) / escala, media, escala


def evaluar_k(z, ks=C.K_CANDIDATOS, semilla=C.SEMILLA_KMEANS):
    """Inercia (codo) y Silhouette para cada k candidato."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    filas = []
    for k in ks:
        km = KMeans(n_clusters=k, n_init=C.N_INIT_KMEANS, random_state=semilla).fit(z)
        filas.append({"k": k, "inercia": km.inertia_, "silhouette": silhouette_score(z, km.labels_)})
    return pd.DataFrame(filas)


def elegir_k(tabla_k, tolerancia=C.TOLERANCIA_SILHOUETTE):
    """El k más grande cuya Silhouette está a menos de `tolerancia` de la máxima."""
    cercanos = tabla_k[tabla_k["silhouette"] >= tabla_k["silhouette"].max() - tolerancia]
    return int(cercanos["k"].max())


def nombrar(centroides, umbral=C.UMBRAL_NOMBRE_PERFIL):
    """Nombre simple de cada perfil a partir de su centroide estandarizado.

    Toma hasta 2 variables con z ≥ umbral (las de mayor z) y las nombra en el
    orden de VARIABLES. Sin variables altas: "estable" si volatilidad y beta
    están bajo el promedio; si no, "moderado". Los nombres repetidos se numeran."""
    nombres = []
    for c in centroides:
        altas = sorted((v for v in range(len(VARIABLES)) if c[v] >= umbral), key=lambda v: -c[v])[:2]
        if altas:
            nombre = "-".join(DESCRIPTOR[VARIABLES[v]] for v in sorted(altas))
        else:
            nombre = "estable" if c[VARIABLES.index("volatilidad_anual")] < 0 and c[VARIABLES.index("beta_104s")] < 0 \
                else "moderado"
        nombres.append(nombre)
    vistos = {}
    for i, n in enumerate(nombres):
        vistos[n] = vistos.get(n, 0) + 1
        if nombres.count(n) > 1:
            nombres[i] = f"{n} {vistos[n]}"
    return nombres


def ajustar(panel, k=None, semilla=C.SEMILLA_KMEANS, ks=C.K_CANDIDATOS):
    """Entrena K-Means sobre el panel histórico. Si k es None, se elige con
    elegir_k entre los candidatos `ks`. Devuelve el modelo como dict
    (serializable en JSON)."""
    from sklearn.cluster import KMeans

    datos = datos_historicos(panel)
    z, media, escala = estandarizar(datos)
    tabla_k = evaluar_k(z, ks=ks, semilla=semilla)
    k = elegir_k(tabla_k) if k is None else k
    km = KMeans(n_clusters=k, n_init=C.N_INIT_KMEANS, random_state=semilla).fit(z)
    # Orden estable de los perfiles: por BSADF del centroide, de menor a mayor
    orden = np.argsort(km.cluster_centers_[:, 0])
    centroides = km.cluster_centers_[orden]
    etiquetas = np.argsort(orden)[km.labels_]
    return {
        "variables": VARIABLES, "k": k, "semilla": semilla, "n_init": C.N_INIT_KMEANS,
        "media": media.tolist(), "escala": escala.tolist(), "centroides_z": centroides.tolist(),
        "nombres": nombrar(centroides), "tamanos": np.bincount(etiquetas, minlength=k).tolist(),
        "diagnostico_k": tabla_k.to_dict(orient="list"), "n_observaciones": len(datos),
        "datos_hasta": f"{pd.Timestamp(datos['fecha'].max()):%Y-%m-%d}",
        "fecha_entrenamiento": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def centroides_originales(modelo):
    """Centroides en las unidades originales de cada variable (para leerlos)."""
    c = np.array(modelo["centroides_z"]) * np.array(modelo["escala"]) + np.array(modelo["media"])
    return pd.DataFrame(c, columns=modelo["variables"], index=modelo["nombres"])


def asignar(datos, modelo):
    """Perfil (nombre) de cada fila: centroide más cercano en el espacio
    estandarizado, igual que KMeans.predict. "sin perfil" si falta una variable."""
    x = datos[modelo["variables"]].to_numpy(dtype=float)
    z = (x - np.array(modelo["media"])) / np.array(modelo["escala"])
    distancias = ((z[:, None, :] - np.array(modelo["centroides_z"])[None, :, :]) ** 2).sum(axis=2)
    nombres = np.array(modelo["nombres"], dtype=object)[distancias.argmin(axis=1)]
    return pd.Series(np.where(np.isnan(x).any(axis=1), "sin perfil", nombres), index=datos.index)


def guardar(modelo, ruta=C.RUTA_PERFILES):
    ruta.write_text(json.dumps(modelo, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Modelo K-Means guardado en %s (k = %d)", ruta.name, modelo["k"])


def cargar_o_entrenar(panel, ruta=C.RUTA_PERFILES):
    """Lee el modelo guardado; si no existe o cambiaron las variables, lo entrena y guarda."""
    if ruta.exists():
        modelo = json.loads(ruta.read_text(encoding="utf-8"))
        if modelo.get("variables") == VARIABLES:
            log.info("Perfiles K-Means: modelo guardado (k = %d, datos hasta %s, entrenado %s)", modelo["k"],
                     modelo["datos_hasta"], modelo["fecha_entrenamiento"])
            return modelo
    log.info("Perfiles K-Means: entrenando el modelo (no había uno guardado)")
    modelo = ajustar(panel)
    guardar(modelo, ruta)
    return modelo
