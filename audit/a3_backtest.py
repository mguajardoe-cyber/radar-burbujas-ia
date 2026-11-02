# =============================================================================
# Auditoría — 3. Backtest
# - Prueba de ausencia de sesgo de anticipación (la señal de t afecta desde t+2).
# - Métricas propias (caída máxima, retorno anual, Sharpe) de mantener, v1 y v2
#   en la cartera A, la B, Nikkei 1989 y Bitcoin 2021, comparadas con src.
# - Placebo: conserva número y duración de episodios (por acción en la B);
#   percentiles recalculados con un generador propio y otra semilla.
# - Anticipación del rojo en Nasdaq 2000, Nikkei 1989 y Bitcoin 2021; rojo
#   cerca de los peaks 2007 y 2021 del Nasdaq.
# Requiere: audit/resultados/bsadf_propio.pkl (a2_detector.py).
# Salida: audit/resultados/a3_backtest.json
# =============================================================================

import json

import numpy as np
import pandas as pd

from comun import (RAIZ, DIR_AUDIT, color_bruto, persistir, expo_v1, expo_v2, aplicar_rezago, caida_maxima,
                   retorno_anual, sharpe, tramos, bsadf_semana, VENTANA)
from src import backtest as B, features as F     # solo para comparar

RES = DIR_AUDIT / "resultados"
datos = pd.read_pickle(RES / "bsadf_propio.pkl")
BSADF, LOGP = datos["bsadf"], datos["log_precio"]
cv = json.loads((RAIZ / "data" / "processed" / "cv_bsadf.json").read_text(encoding="utf-8"))["ventana=260"]["valores_criticos"]
AM, RO = cv["0.9"], cv["0.95"]
salida = {}

def niveles(nombre):
    return pd.Series(persistir(color_bruto(BSADF[nombre].to_numpy(), AM, RO), 6), index=BSADF[nombre].index)

# --- 1. Sesgo de anticipación -------------------------------------------------------
# (a) Caso unitario: un único rojo en la semana 10 → la exposición del retorno cambia recién en la semana 12
col = pd.Series(["verde"] * 20); col[10] = "rojo"
efectiva_src = B.exposicion_efectiva(B.exposicion_objetivo(col)).to_numpy()
efectiva_propia = aplicar_rezago(expo_v1([2 if c == "rojo" else 0 for c in col]))
primera_reduccion = int(np.argmax(efectiva_src < 1))
caso_ok = primera_reduccion == 12 and np.allclose(efectiva_src, efectiva_propia)
# (b) Perturbación con datos reales (Nasdaq desde 1990): alterar el futuro desde la semana T
#     no cambia el BSADF de las semanas anteriores a T (la ventana termina en t)
y = LOGP["IXIC_1990"].to_numpy().copy()
T = len(y) - 300
y_alt = y.copy(); y_alt[T:] += np.cumsum(np.random.default_rng(0).normal(0.05, 0.1, len(y) - T))
semanas_prueba = [T - 1, T - 50, T - 150]
pert_ok = all(np.isclose(bsadf_semana(y, t), bsadf_semana(y_alt, t)) for t in semanas_prueba)
# (c) Cambiar el color de la semana k solo altera exposiciones aplicadas desde k+2
niv = niveles("IXIC_1990").to_numpy()
k = 900
niv_alt = niv.copy(); niv_alt[k] = 2
e1, e2 = aplicar_rezago(expo_v1(niv)), aplicar_rezago(expo_v1(niv_alt))
cambios = np.flatnonzero(e1 != e2)
color_ok = len(cambios) == 0 or cambios.min() >= k + 2
salida["sesgo_anticipacion"] = {"caso_unitario_primera_semana_reducida": primera_reduccion, "caso_unitario_ok": bool(caso_ok),
                                "perturbacion_futuro_no_cambia_pasado": bool(pert_ok),
                                "cambio_color_k_afecta_desde": int(cambios.min()) if len(cambios) else None,
                                "k": k, "ok": bool(caso_ok and pert_ok and color_ok)}
print("Sesgo de anticipación:", salida["sesgo_anticipacion"])

# --- 2. Métricas propias -----------------------------------------------------------
def evaluar(nombre, ventana=None):
    """Serie desde su primera semana con señal; ventana = (inicio, fin) opcional."""
    lp, nv = LOGP[nombre], niveles(nombre)
    precio = np.exp(lp.loc[nv.index[0]:])
    r = precio.pct_change().iloc[1:]
    e = {"v1": aplicar_rezago(expo_v1(nv.to_numpy()))[1:], "v2": aplicar_rezago(expo_v2(nv.to_numpy()))[1:]}
    e = {k: pd.Series(v, index=r.index) for k, v in e.items()}
    if ventana:
        r = r.loc[ventana[0]:ventana[1]]
        e = {k: v.loc[r.index] for k, v in e.items()}
    out = {"Mantener 100%": r}
    out.update({k: v * r for k, v in e.items()})
    return {k: {"caida_maxima": caida_maxima(v), "retorno_anual": retorno_anual(v), "sharpe": sharpe(v)}
            for k, v in out.items()}, e, r

def episodio(nombre, a, b, c):
    p = np.exp(LOGP[nombre])
    peak = p.loc[a:b].idxmax(); valle = p.loc[peak:c].idxmin()
    return peak - pd.Timedelta(weeks=52), peak, valle

def src_tabla(nombre, ventana=None):
    """Mismas métricas con src (para comparar)."""
    lp, col = LOGP[nombre], pd.Series([F.COLOR[v] for v in niveles(nombre)], index=BSADF[nombre].index)
    ev = B.evaluar_serie(np.exp(lp), col, n_placebo=10)
    t = B.tabla_ventana(ev, *(ventana or (None, None)))
    return {k: {m: float(t.loc[m, k]) for m in ("caida_maxima", "retorno_anual", "sharpe")} for k in t.columns}

EPISODIOS = {
    "Nasdaq completo": ("IXIC_1990", None),
    "Nasdaq 2000-2002": ("IXIC_1990", ("1999-01-01", "2000-12-31", "2003-06-30")),
    "Nasdaq 2007-2009": ("IXIC_1990", ("2007-01-01", "2008-06-30", "2009-12-31")),
    "Nasdaq 2021-2022": ("IXIC_1990", ("2021-01-01", "2022-03-31", "2023-06-30")),
    "Nikkei 1989": ("^N225", ("1989-01-01", "1990-03-31", "1992-12-31")),
    "Bitcoin 2021": ("BTC-USD", ("2021-01-01", "2021-12-31", "2023-06-30")),
}
metricas, ventanas, max_dif = {}, {}, 0.0
for nombre, (serie, busq) in EPISODIOS.items():
    vent = None
    if busq:
        ini, peak, valle = episodio(serie, *busq)
        vent = (ini, valle)
        ventanas[nombre] = {"inicio": str(ini.date()), "peak": str(peak.date()), "valle": str(valle.date())}
    propio, _, _ = evaluar(serie, vent)
    ref = src_tabla(serie, vent)
    max_dif = max(max_dif, max(abs(propio[k][m] - ref[k][m]) for k in propio for m in propio[k]))
    metricas[nombre] = propio

# Cartera B: 9 acciones, igual peso, desde 2018-01-05
ACC = ["NVDA", "MSFT", "GOOGL", "META", "AMD", "AVGO", "TSM", "ORCL", "AMZN"]
rets, expos = {}, {"v1": {}, "v2": {}}
for t in ACC:
    nv = niveles(t)
    precio = np.exp(LOGP[t])
    r = precio.pct_change()
    for regla, f in (("v1", expo_v1), ("v2", expo_v2)):
        e = pd.Series(aplicar_rezago(f(nv.to_numpy())), index=nv.index)
        expos[regla][t] = e.reindex(r.index)
    rets[t] = r
R_B = pd.DataFrame(rets).loc["2018-01-05":]
E_B = {k: pd.DataFrame(v).loc[R_B.index] for k, v in expos.items()}
cartera = {"Mantener 100%": R_B.mean(axis=1), "v1": (E_B["v1"] * R_B).mean(axis=1), "v2": (E_B["v2"] * R_B).mean(axis=1)}
metricas["Cartera B"] = {k: {"caida_maxima": caida_maxima(v), "retorno_anual": retorno_anual(v), "sharpe": sharpe(v)}
                         for k, v in cartera.items()}
salida["metricas_propias"] = metricas
salida["ventanas_episodios"] = ventanas
salida["dif_max_vs_src_series"] = max_dif
print(f"Métricas propias vs src (A, episodios, Nikkei, Bitcoin): dif. máx {max_dif:.2e}")
for n, m in metricas.items():
    print(f"  {n:18s} " + " | ".join(f"{k}: dd {v['caida_maxima']:.1%} ret {v['retorno_anual']:.1%} sh {v['sharpe']:.2f}"
                                     for k, v in m.items()))

# --- 3. Placebo ---------------------------------------------------------------------
def duraciones(mascara):
    return sorted(l for _, l in tramos(mascara))

def revisar_placebo_src(expo):
    reales = duraciones(np.asarray(expo) < 1)
    P = B.exposiciones_placebo(pd.Series(expo), 1000)
    return all(duraciones(fila < 1) == reales for fila in P), len(reales)

_, eA, rA = evaluar("IXIC_1990")
placebo_ok = {f"A {k}": revisar_placebo_src(eA[k].to_numpy()) for k in ("v1", "v2")}
for t in ACC:
    for k in ("v1", "v2"):
        placebo_ok[f"B {t} {k}"] = revisar_placebo_src(E_B[k][t].to_numpy())
todos_ok = all(v[0] for v in placebo_ok.values())
print("Placebo de src conserva número y duración de episodios (A y cada acción de B):", todos_ok)

def placebo_propio(expo, n, rng):
    """Generador propio: episodios con las mismas duraciones en orden aleatorio; los
    huecos (≥1 entre episodios) se reparten con cortes uniformes ordenados."""
    dur = np.array(duraciones(np.asarray(expo) < 1))
    N, K = len(expo), len(dur)
    libres = N - dur.sum() - (K - 1)
    filas = []
    for _ in range(n):
        d = rng.permutation(dur)
        cortes = np.sort(rng.integers(0, libres + 1, size=K))
        huecos = np.diff(np.concatenate([[0], cortes]))
        huecos[1:] += 1
        m, pos = np.zeros(N, bool), 0
        for h, l in zip(huecos, d):
            pos += h; m[pos:pos + l] = True; pos += l
        filas.append(np.where(m, 0.5, 1.0))
    return np.array(filas)

def percentil(real, placebo):
    return 100 * np.mean(np.asarray(placebo) > real)

rng = np.random.default_rng(2026)
percentiles = {}
for regla in ("v1", "v2"):
    P = placebo_propio(eA[regla].to_numpy(), 1000, rng)
    caidas = [caida_maxima(fila * rA.to_numpy()) for fila in P]
    percentiles[f"Nasdaq completo {regla}"] = percentil(metricas["Nasdaq completo"][regla]["caida_maxima"], caidas)
for nombre in ("Nikkei 1989", "Bitcoin 2021"):
    serie, busq = EPISODIOS[nombre]
    _, e, r = evaluar(serie)
    ini, valle = ventanas[nombre]["inicio"], ventanas[nombre]["valle"]
    mask = (r.index >= ini) & (r.index <= valle)
    P = placebo_propio(e["v2"].to_numpy(), 1000, rng)
    caidas = [caida_maxima(fila[mask] * r.to_numpy()[mask]) for fila in P]
    percentiles[f"{nombre} v2"] = percentil(metricas[nombre]["v2"]["caida_maxima"], caidas)
# Cartera B, placebo propio por acción
P_B = {k: {t: placebo_propio(E_B[k][t].to_numpy(), 1000, rng) for t in ACC} for k in ("v1", "v2")}
for k in ("v1", "v2"):
    port = np.mean([P_B[k][t] * R_B[t].to_numpy() for t in ACC], axis=0)
    percentiles[f"Cartera B {k}"] = percentil(metricas["Cartera B"][k]["caida_maxima"], [caida_maxima(f) for f in port])
salida["placebo"] = {"src_conserva_episodios": todos_ok, "detalle": {k: v[0] for k, v in placebo_ok.items()},
                     "percentiles_generador_propio_semilla_2026": percentiles}
print("Percentiles con generador propio (semilla 2026):", {k: round(v, 1) for k, v in percentiles.items()})

# --- 4. Anticipación y rojo cerca de peaks sin burbuja --------------------------------
def anticipacion(nombre, peak):
    nv = niveles(nombre).loc[:peak]
    rojo = (nv == 2).to_numpy()
    inicios = [i for i in range(len(rojo)) if rojo[i] and (i == 0 or not rojo[i - 1])]
    if not inicios:
        return None
    inicio = nv.index[inicios[-1]]
    if not rojo[-1] and inicio < peak - pd.Timedelta(weeks=52):
        return None
    return (peak - inicio).days // 7

anticip = {}
for nombre, serie in (("Nasdaq 2000-2002", "IXIC_1990"), ("Nikkei 1989", "^N225"), ("Bitcoin 2021", "BTC-USD")):
    anticip[nombre] = anticipacion(serie, pd.Timestamp(ventanas[nombre]["peak"]))
nv_ix = niveles("IXIC_1990")
nv_bruto = pd.Series(color_bruto(BSADF["IXIC_1990"].to_numpy(), AM, RO), index=BSADF["IXIC_1990"].index)
# Sin persistencia: inicio del tramo rojo bruto que contiene el peak
peak_2000 = pd.Timestamp(ventanas["Nasdaq 2000-2002"]["peak"])
b = nv_bruto.loc[:peak_2000]
i = len(b) - 1
while i >= 0 and b.iloc[i] == 2:
    i -= 1
anticip["Nasdaq 2000-2002 sin persistencia"] = (peak_2000 - b.index[i + 1]).days // 7 if i < len(b) - 1 else None
rojo_cerca = {}
for nombre in ("Nasdaq 2007-2009", "Nasdaq 2021-2022"):
    v = ventanas[nombre]
    tramo = nv_ix.loc[v["inicio"]:v["valle"]]
    tramo_b = nv_bruto.loc[v["inicio"]:v["valle"]]
    rojo_cerca[nombre] = {"semanas_rojo_persistente": int((tramo == 2).sum()),
                          "semanas_rojo_bruto": int((tramo_b == 2).sum()), "max_nivel_persistente": int(tramo.max())}
salida["anticipacion"] = anticip
salida["rojo_cerca_peaks_sin_burbuja"] = rojo_cerca
print("Anticipación (semanas):", anticip)
print("Rojo en ventanas 2007-2009 y 2021-2022 del Nasdaq:", rojo_cerca)

json.dump(salida, open(RES / "a3_backtest.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
