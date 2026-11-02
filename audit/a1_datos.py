# =============================================================================
# Auditoría — 1. Datos
# Recalcula desde data/raw las validaciones de cada serie (código propio) y las
# compara con data/processed/resumen_validacion.csv; contrasta cierres y caídas
# del Nasdaq declarados.
# Salida: audit/resultados/a1_datos.json
# =============================================================================

import json

import numpy as np
import pandas as pd

from comun import RAIZ, DIR_AUDIT, leer_crudo, es_indice

salida = {}
crudo = leer_crudo("precios_diarios.csv")
declarado = pd.read_csv(RAIZ / "data" / "processed" / "resumen_validacion.csv").set_index("ticker")
ultima = crudo["fecha"].max()

filas = []
for t, g in crudo.groupby("ticker"):
    g = g.sort_values("fecha")
    duplicados = int(g["fecha"].duplicated().sum())
    no_pos = int((g[["open", "high", "low", "close", "adj_close"]] <= 0).any(axis=1).sum())
    vol0 = 0 if es_indice(t) else int((g["volume"] <= 0).sum())
    if not es_indice(t):
        g = g[g["volume"] > 0]
    fechas = list(g["fecha"].values.astype("datetime64[D]")) + [np.datetime64(ultima.date())]
    huecos = np.busday_count(fechas[:-1], fechas[1:]) - 1
    limite = 10 if es_indice(t) else 5
    saltos = int((g["adj_close"].pct_change().abs() > 0.5).sum())
    valida = duplicados == 0 and no_pos == 0 and huecos.max() <= limite
    d = declarado.loc[t]
    filas.append({"ticker": t, "n_dias": len(g), "n_dias_declarado": int(d["n_dias"]),
                  "vol0_eliminados": vol0, "vol0_eliminados_declarado": int(d["dias_volumen_cero_eliminados"]),
                  "max_hueco": int(huecos.max()), "max_hueco_declarado": int(d["max_hueco_dias_habiles"]),
                  "saltos": saltos, "saltos_declarado": int(d["saltos_marcados_revision"]),
                  "valida": bool(valida), "valida_declarado": bool(d["valida"])})
tabla = pd.DataFrame(filas).set_index("ticker")
coinciden = all((tabla[c] == tabla[f"{c}_declarado"]).all()
                for c in ["n_dias", "vol0_eliminados", "max_hueco", "saltos", "valida"])
print(tabla.to_string())
print("Validaciones coinciden con resumen_validacion.csv:", coinciden)
salida["validaciones"] = {"coinciden": coinciden, "tabla": tabla.reset_index().to_dict("records")}

# Nasdaq: cierres y caída de la puntocom (cierre diario sin ajustar = ajustado en un índice)
ix = leer_crudo("IXIC_desde_1990.csv").set_index("fecha")["close"]
c_peak, c_valle = float(ix.loc["2000-03-10"]), float(ix.loc["2002-10-09"])
peak_fecha = ix.loc["1999":"2001"].idxmax()
valle_fecha = ix.loc[peak_fecha:"2003-12-31"].idxmin()
salida["nasdaq"] = {"cierre_2000_03_10": c_peak, "cierre_2002_10_09": c_valle,
                    "caida": c_valle / c_peak - 1, "peak_diario": str(peak_fecha.date()),
                    "valle_diario": str(valle_fecha.date())}
print(f"Nasdaq 10-03-2000: {c_peak:.2f} | 09-10-2002: {c_valle:.2f} | caída {c_valle / c_peak - 1:.2%} "
      f"(peak diario {peak_fecha.date()}, valle diario {valle_fecha.date()})")

# Octubre 2026: cierre 30-09-2026 vs 30-10-2026
ix_u = crudo[crudo["ticker"] == "^IXIC"].set_index("fecha")["close"]
c_sep = ix_u.loc[:"2026-09-30"]
c_oct = float(ix_u.loc["2026-10-30"])
salida["nasdaq_octubre_2026"] = {"fecha_base": str(c_sep.index[-1].date()), "cierre_base": float(c_sep.iloc[-1]),
                                 "cierre_30_10": c_oct, "variacion": c_oct / float(c_sep.iloc[-1]) - 1}
print(f"Nasdaq {c_sep.index[-1].date()}: {c_sep.iloc[-1]:.2f} → 30-10-2026: {c_oct:.2f} = "
      f"{c_oct / c_sep.iloc[-1] - 1:.2%}")

(DIR_AUDIT / "resultados").mkdir(exist_ok=True)
json.dump(salida, open(DIR_AUDIT / "resultados" / "a1_datos.json", "w", encoding="utf-8"), indent=1,
          ensure_ascii=False, default=str)
