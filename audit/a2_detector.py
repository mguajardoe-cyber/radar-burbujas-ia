# =============================================================================
# Auditoría — 2. Detector
# - BSADF con statsmodels.adfuller en un bucle vs. src/sadf.py (panel_semanal.csv)
#   en 30 semanas al azar de 3 tickers.
# - BSADF propio (numpy lstsq) de todas las semanas de todas las series, usado
#   para recalcular el semáforo y en los demás scripts.
# - Valores críticos con semilla 2026 y 5.000 simulaciones vs. cv_bsadf.json,
#   con error Monte Carlo (bootstrap).
# - Persistencia en casos borde construidos a mano (propia y src).
# - Semáforo al 30-10-2026 y semanas en el color.
# Salida: audit/resultados/a2_detector.json y bsadf_propio.pkl
# =============================================================================

import json
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

from comun import (RAIZ, DIR_AUDIT, VENTANA, N0, leer_crudo, semanal, adf_t, bsadf_serie, color_bruto,
                   persistir, semanas_en_color, NOMBRE)

RES = DIR_AUDIT / "resultados"
FECHA_DATOS = "2026-10-30"


def adf_sm(w):
    return adfuller(w, maxlag=1, autolag=None, regression="c", result_object=False)[0]


def series_auditadas():
    crudo = leer_crudo("precios_diarios.csv")
    series = {t: np.log(semanal(g, FECHA_DATOS)) for t, g in crudo.groupby("ticker")}
    series["IXIC_1990"] = np.log(semanal(leer_crudo("IXIC_desde_1990.csv"), FECHA_DATOS))
    fm = leer_crudo("fuera_de_muestra.csv")
    for t in ("^N225", "BTC-USD"):
        series[t] = np.log(semanal(fm[fm["ticker"] == t], FECHA_DATOS))
    return series


def tarea(item):
    nombre, lp = item
    return nombre, bsadf_serie(lp)


def simular_maximo(semilla_lote):
    semilla, n = semilla_lote
    rng = np.random.default_rng(semilla)
    out = []
    for _ in range(n):
        y = np.cumsum(1 / VENTANA + rng.standard_normal(VENTANA))
        out.append(max(adf_t(y[s:]) for s in range(VENTANA - N0 + 1)))
    return out


if __name__ == "__main__":
    salida = {}
    series = series_auditadas()

    # 1) adfuller en bucle vs src en 30 semanas al azar de 3 tickers
    panel = pd.read_csv(RAIZ / "data" / "processed" / "panel_semanal.csv", parse_dates=["fecha"])
    rng = np.random.default_rng(2026)
    comparacion = []
    for t in ("NVDA", "^IXIC", "TSM"):
        lp = series[t]
        y = lp.to_numpy()
        semanas = rng.choice(np.arange(VENTANA - 1, len(y)), size=30, replace=False)
        ref = panel[panel["ticker"] == t].set_index("fecha")["bsadf"]
        for i in semanas:
            tramo = y[i - VENTANA + 1: i + 1]
            b_sm = max(adf_sm(tramo[s:]) for s in range(VENTANA - N0 + 1))
            b_np = max(adf_t(tramo[s:]) for s in range(VENTANA - N0 + 1))
            comparacion.append({"ticker": t, "fecha": str(lp.index[i].date()), "bsadf_statsmodels": b_sm,
                                "bsadf_numpy_propio": b_np, "bsadf_src": float(ref.loc[lp.index[i]])})
    comp = pd.DataFrame(comparacion)
    dif_src = (comp["bsadf_statsmodels"] - comp["bsadf_src"]).abs().max()
    dif_np = (comp["bsadf_statsmodels"] - comp["bsadf_numpy_propio"]).abs().max()
    print(f"BSADF adfuller vs src: {len(comp)} semanas, dif. máx {dif_src:.2e}; adfuller vs numpy propio {dif_np:.2e}")
    salida["bsadf_vs_src"] = {"semanas": len(comp), "dif_max_src": dif_src, "dif_max_numpy_propio": dif_np}

    # 2) BSADF propio de todas las series (en paralelo)
    inicio = time.time()
    with Pool() as pool:
        bsadf = dict(pool.map(tarea, list(series.items())))
    print(f"BSADF propio de {len(bsadf)} series en {time.time() - inicio:.0f} s")
    pd.to_pickle({"bsadf": bsadf, "log_precio": series}, RES / "bsadf_propio.pkl")
    dif_panel = max((bsadf[t] - panel[panel["ticker"] == t].set_index("fecha")["bsadf"].reindex(bsadf[t].index)).abs().max()
                    for t in panel["ticker"].unique())
    print(f"BSADF propio vs panel_semanal.csv (todas las semanas del universo): dif. máx {dif_panel:.2e}")
    salida["bsadf_propio_vs_panel"] = dif_panel

    # 3) Valores críticos: semilla 2026, 5.000 simulaciones
    inicio = time.time()
    lotes = [(2026 + i, 625) for i in range(8)]
    with Pool() as pool:
        maximos = np.concatenate(pool.map(simular_maximo, lotes))
    q = {0.90: float(np.quantile(maximos, 0.90)), 0.95: float(np.quantile(maximos, 0.95))}
    boot = np.random.default_rng(1).choice(maximos, size=(2000, len(maximos)), replace=True)
    se = {0.90: float(np.quantile(boot, 0.90, axis=1).std()), 0.95: float(np.quantile(boot, 0.95, axis=1).std())}
    ref = json.loads((RAIZ / "data" / "processed" / "cv_bsadf.json").read_text(encoding="utf-8"))["ventana=260"]
    cv_ref = {0.90: ref["valores_criticos"]["0.9"], 0.95: ref["valores_criticos"]["0.95"]}
    # Error conjunto: SE con 5.000 y SE de la referencia (20.000 ≈ SE/2)
    z = {k: (q[k] - cv_ref[k]) / np.sqrt(se[k] ** 2 + (se[k] / 2) ** 2) for k in q}
    print(f"Valores críticos (5.000 sim, semilla 2026, {time.time() - inicio:.0f} s): "
          + "; ".join(f"{k:.0%}: {q[k]:.3f} ± {se[k]:.3f} vs. {cv_ref[k]:.3f} (z = {z[k]:+.2f})" for k in q))
    salida["valores_criticos"] = {"propio": q, "error_estandar": se, "referencia": cv_ref, "z": z,
                                  "lotes_semillas": "2026-2033, 625 c/u"}

    # 4) Persistencia en casos borde (esperado escrito a mano)
    from src import features as F   # solo para comparar contra src
    V, A, R = 0, 1, 2
    casos = {
        "rojo aislado en verde": ([V] * 8 + [R] + [V] * 8, [V] * 17),
        "5 rojos no bastan, 6 sí": ([V] * 3 + [R] * 6, [V] * 8 + [R]),
        "verde aislado no apaga rojo": ([R] * 7 + [V] + [R] * 4, [V] * 5 + [R] * 7),
        "alternancia A/R sube a amarillo": ([V] * 2 + [R, A] * 3, [V] * 7 + [A]),
        "baja de rojo a amarillo": ([R] * 6 + [A] * 6, [V] * 5 + [R] * 6 + [A]),
        "baja de rojo a verde con mezcla": ([R] * 6 + [A, V, A, V, A, V], [V] * 5 + [R] * 6 + [A]),
        "serie empieza en rojo parte en verde": ([R] * 3, [V] * 3),
    }
    resultado_casos = {}
    for nombre, (entrada, esperado) in casos.items():
        propio = list(persistir(entrada, 6))
        src = [F.NIVEL[c] for c in F.aplicar_persistencia([NOMBRE[v] for v in entrada], 6)]
        resultado_casos[nombre] = {"esperado": esperado, "propio": propio, "src": src,
                                   "ok": propio == esperado and src == esperado}
        print(f"Persistencia — {nombre}: {'OK' if resultado_casos[nombre]['ok'] else 'FALLA'}")
    salida["persistencia_casos"] = resultado_casos

    # 5) Semáforo al 30-10-2026 y semanas en el color (propio)
    actual_decl = pd.read_csv(RAIZ / "data" / "processed" / "semaforo_actual.csv").set_index("ticker")
    filas = []
    for t in actual_decl.index:
        niv_b = color_bruto(bsadf[t].to_numpy(), cv_ref[0.90], cv_ref[0.95])
        niv = persistir(niv_b, 6)
        filas.append({"ticker": t, "color_propio": NOMBRE[niv[-1]], "color_declarado": actual_decl.loc[t, "semaforo"],
                      "semanas_propio": semanas_en_color(niv),
                      "semanas_declarado": int(actual_decl.loc[t, "semanas_en_estado"]),
                      "bruto_propio": NOMBRE[niv_b[-1]], "bruto_declarado": actual_decl.loc[t, "semaforo_bruto"]})
    sem = pd.DataFrame(filas).set_index("ticker")
    sem_ok = bool((sem["color_propio"] == sem["color_declarado"]).all()
                  and (sem["semanas_propio"] == sem["semanas_declarado"]).all()
                  and (sem["bruto_propio"] == sem["bruto_declarado"]).all())
    print(sem.to_string())
    print("Semáforo al 30-10-2026 coincide:", sem_ok)
    salida["semaforo_actual"] = {"coincide": sem_ok, "tabla": sem.reset_index().to_dict("records")}

    json.dump(salida, open(RES / "a2_detector.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
