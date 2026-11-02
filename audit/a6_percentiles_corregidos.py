# =============================================================================
# Auditoría — percentiles placebo antes y después de corregir el hallazgo C1
# Recalcula con src (ya corregido) los percentiles de todos los episodios y
# los compara con los publicados en outputs/resumen_episodios_v1_v2.csv.
# Salida: audit/resultados/percentiles_antes_despues.csv
# =============================================================================

import logging

import numpy as np
import pandas as pd

from comun import RAIZ, DIR_AUDIT
from src import config as C, ingesta as I, features as F, backtest as B

logging.disable(logging.CRITICAL)
antes = pd.read_csv(RAIZ / "outputs" / "resumen_episodios_v1_v2.csv").set_index("episodio")

def serie(archivo, ticker):
    crudo = pd.read_csv(RAIZ / "data" / "raw" / archivo, parse_dates=["fecha"])
    val, _, _ = I.validar_universo(crudo[crudo["ticker"] == ticker], [ticker])
    sem = F.a_semanal(val)
    return sem[ticker], F.senales_bsadf(sem).set_index("fecha")["semaforo"]

filas = []
def agregar(nombre, tabla):
    for regla in ("v1", "v2"):
        filas.append({"episodio": nombre, "regla": regla,
                      "antes": antes.loc[nombre, f"percentil placebo {regla}"],
                      "despues": tabla.loc["percentil_placebo", regla]})

p, c = serie("IXIC_desde_1990.csv", "^IXIC")
ev = B.evaluar_serie(p, c)
agregar("Nasdaq periodo completo", B.tabla_ventana(ev))
for nombre, f in {"Nasdaq 2000-2002": ("1999-01-01", "2000-12-31", "2003-06-30"),
                  "Nasdaq 2007-2009": ("2007-01-01", "2008-06-30", "2009-12-31"),
                  "Nasdaq 2021-2022": ("2021-01-01", "2022-03-31", "2023-06-30")}.items():
    ep = B.episodio(p, *f)
    agregar(nombre, B.tabla_ventana(ev, ep["inicio"], ep["valle"]))
for nombre, ticker, f in (("Nikkei 1989", "^N225", ("1989-01-01", "1990-03-31", "1992-12-31")),
                          ("Bitcoin 2021", "BTC-USD", ("2021-01-01", "2021-12-31", "2023-06-30"))):
    p, c = serie("fuera_de_muestra.csv", ticker)
    ev = B.evaluar_serie(p, c)
    ep = B.episodio(p, *f)
    agregar(nombre, B.tabla_ventana(ev, ep["inicio"], ep["valle"]))

# Cartera B (mismo procedimiento que los notebooks 06 y 06b)
validados = pd.read_csv(C.DIR_PROCESSED / "precios_validados.csv", parse_dates=["fecha"])
panel = F.construir_panel(validados)
acc = list(C.UNIVERSO)
precios = panel.pivot(index="fecha", columns="ticker", values="adj_close")[acc]
colores = panel.pivot(index="fecha", columns="ticker", values="semaforo")[acc]
r = precios.pct_change().loc["2018-01-05":]
tabla_b = {}
for regla in ("v1", "v2"):
    e = pd.DataFrame({t: B.exposicion_efectiva(B.objetivo_regla(colores[t].dropna(), regla)) for t in acc}).reindex(r.index)
    reg, _ = B.cartera_igual_peso(r, e)
    plac = np.mean([B.exposiciones_placebo(e[t], 1000, semilla=C.SEMILLA_MC + i) * r[t].to_numpy()
                    for i, t in enumerate(acc)], axis=0)
    tabla_b[regla] = B.percentil_placebo(B.metricas(reg)["caida_maxima"], B.caida_maxima_matriz(plac))
agregar("Cartera B 2018-hoy (9 acciones)", pd.DataFrame({"v1": [tabla_b["v1"]], "v2": [tabla_b["v2"]]},
                                                        index=["percentil_placebo"]))

res = pd.DataFrame(filas)
res.to_csv(DIR_AUDIT / "resultados" / "percentiles_antes_despues.csv", index=False)
print(res.to_string())
