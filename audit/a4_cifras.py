# =============================================================================
# Auditoría — 4. Cifras públicas
# Recalcula las cifras que faltan (episodios y % en rojo del universo, series en
# rojo desde 2023, falsas alarmas, IL3/IL4 desde archivos y logs) y arma la
# tabla declarado / recalculado / fuente / estado con los resultados de a1-a3.
# Salida: audit/resultados/cifras.csv y cifras.md
# =============================================================================

import json
import math
import re
import time

import numpy as np
import pandas as pd

from comun import RAIZ, DIR_AUDIT, VENTANA, N0, color_bruto, persistir, tramos

RES = DIR_AUDIT / "resultados"
a1 = json.load(open(RES / "a1_datos.json", encoding="utf-8"))
a2 = json.load(open(RES / "a2_detector.json", encoding="utf-8"))
a3 = json.load(open(RES / "a3_backtest.json", encoding="utf-8"))
datos = pd.read_pickle(RES / "bsadf_propio.pkl")
BSADF = datos["bsadf"]
AM, RO = a2["valores_criticos"]["referencia"]["0.9"], a2["valores_criticos"]["referencia"]["0.95"]
UNIVERSO = ["NVDA", "MSFT", "GOOGL", "META", "AMD", "AVGO", "TSM", "ORCL", "AMZN", "^IXIC", "^GSPC"]

# --- Universo: episodios rojos y % de semanas en rojo, bruto vs. persistencia ------------
ep_b = ep_p = sem_b = sem_p = total = 0
rojo_2023_bruto, rojo_2023_pers = [], []
for t in UNIVERSO:
    b = BSADF[t]
    nb = color_bruto(b.to_numpy(), AM, RO)
    npers = persistir(nb, 6)
    ep_b += len(tramos(nb == 2)); ep_p += len(tramos(npers == 2))
    sem_b += int((nb == 2).sum()); sem_p += int((npers == 2).sum()); total += len(nb)
    desde = b.index >= "2023-01-01"
    if b[desde].max() > RO:
        rojo_2023_bruto.append(t)
    if (npers[desde] == 2).any():
        rojo_2023_pers.append(t)
universo = {"episodios_rojos_bruto": ep_b, "episodios_rojos_persistencia": ep_p,
            "pct_rojo_bruto": sem_b / total, "pct_rojo_persistencia": sem_p / total,
            "series_rojo_desde_2023_bruto": rojo_2023_bruto, "series_rojo_desde_2023_persistencia": rojo_2023_pers}
print(universo)

# --- Falsas alarmas (200 series sin burbuja de 1.661 semanas, semilla 2027) -------------
from src import sadf as S   # ADF rápido de src, verificado contra statsmodels en a2
rng = np.random.default_rng(2027)
ep_bruto, ep_pers = [], []
inicio = time.time()
for _ in range(200):
    y = np.cumsum(1 / 1661 + rng.standard_normal(1661))
    bs = S.adf_hacia_atras(np.lib.stride_tricks.sliding_window_view(y, VENTANA), N0).max(axis=-1)
    nb = color_bruto(bs, AM, RO)
    ep_bruto.append(len(tramos(nb == 2))); ep_pers.append(len(tramos(persistir(nb, 6) == 2)))
falsas = {"bruto_media": float(np.mean(ep_bruto)), "bruto_ee": float(np.std(ep_bruto) / math.sqrt(200)),
          "pers_media": float(np.mean(ep_pers)), "pers_ee": float(np.std(ep_pers) / math.sqrt(200)),
          "segundos": time.time() - inicio}
print("Falsas alarmas:", falsas)

# --- IL3 e IL4 desde archivos ------------------------------------------------------------
dic = pd.read_csv(RAIZ / "docs" / "diccionario_datos.csv")
cols = pd.read_csv(RAIZ / "data" / "processed" / "precios_validados.csv", nrows=2).columns
doc = set(dic.dropna(subset=["definicion", "unidad"])["columna"])
pct_cols = np.mean([c in doc for c in cols])
ejec = []
for ruta in sorted((RAIZ / "logs").glob("radar_*.log")):
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "RESUMEN_EJECUCION" in linea:
            ejec.append(dict(re.findall(r"(\w+)=(\S+)", linea)))
ejec = pd.DataFrame(ejec)
ejec["duracion_s"] = ejec["duracion_s"].astype(float)
il4 = {"ok": int((ejec["estado"] == "OK").sum()), "total": len(ejec),
       "max_normal": float(ejec.loc[ejec["modo"] == "normal", "duracion_s"].max()),
       "offline_min": float(ejec.loc[ejec["modo"] == "offline", "duracion_s"].min()),
       "offline_max": float(ejec.loc[ejec["modo"] == "offline", "duracion_s"].max())}
print("IL4:", il4)

# --- Configuración declarada (lectura de texto de config.py, sin importarlo) --------------
cfg = (RAIZ / "src" / "config.py").read_text(encoding="utf-8")
def valor(nombre):
    return re.search(rf"^{nombre}\s*=\s*([^\s#]+)", cfg, re.M).group(1)

# --- Tabla de cifras ----------------------------------------------------------------------
M, AN, PL = a3["metricas_propias"], a3["anticipacion"], a3["placebo"]["percentiles_generador_propio_semilla_2026"]
sem = {r["ticker"]: r for r in a2["semaforo_actual"]["tabla"]}
filas = []
def fila(cifra, declarado, recalculado, fuente, ok, nota=""):
    estado = "NO VERIFICABLE" if ok is None else ("OK" if bool(ok) else "DIFERENCIA")   # bool(): acepta booleanos de numpy
    filas.append({"cifra": cifra, "declarado": declarado, "recalculado": recalculado, "fuente": fuente,
                  "estado": estado, "nota": nota})

n = a1["nasdaq"]
fila("Caída del Nasdaq en la puntocom", "−77,9% (5.048 → 1.114)",
     f"{n['caida']:.2%} ({n['cierre_2000_03_10']:.2f} → {n['cierre_2002_10_09']:.2f})", "data/raw/IXIC_desde_1990.csv",
     round(n["caida"] * 100, 1) == -77.9)
o = a1["nasdaq_octubre_2026"]
fila("Variación del Nasdaq en octubre de 2026", "−5,3%", f"{o['variacion']:.2%} ({o['cierre_base']:.2f} → {o['cierre_30_10']:.2f})",
     "data/raw/precios_diarios.csv", round(o["variacion"] * 100, 1) == -5.3)
fila("Universo", "9 acciones + 2 índices", f"{len(a1['validaciones']['tabla'])} series en data/raw (9 + ^IXIC, ^GSPC)",
     "data/raw/precios_diarios.csv", len(a1["validaciones"]["tabla"]) == 11)
fila("Ventana y largo mínimo", "260 y 31", f"{valor('VENTANA_BSADF')} y floor((0,01+1,8/√260)·260) = {N0}", "src/config.py",
     valor("VENTANA_BSADF") == "260" and N0 == 31)
vc = a2["valores_criticos"]
fila("Umbrales amarillo / rojo", "0,36 / 0,69",
     f"{vc['propio']['0.9']:.3f} ± {vc['error_estandar']['0.9']:.3f} / {vc['propio']['0.95']:.3f} ± {vc['error_estandar']['0.95']:.3f} "
     f"(5.000 sim, semilla 2026; z = {vc['z']['0.9']:+.1f} / {vc['z']['0.95']:+.1f})", "audit/a2_detector.py",
     abs(vc["z"]["0.9"]) < 3 and abs(vc["z"]["0.95"]) < 3)
fila("Persistencia", "6 semanas", f"{valor('PERSISTENCIA_SEMANAS')} (log(260) = {math.log(260):.2f})", "src/config.py",
     valor("PERSISTENCIA_SEMANAS") == "6")
fila("Duración de main.py", "14,6 s normal; ~6-11 s offline",
     f"normal máx {il4['max_normal']:.1f} s; offline {il4['offline_min']:.1f}-{il4['offline_max']:.1f} s", "logs/",
     il4["max_normal"] == 14.6 and il4["offline_min"] >= 5.9 and il4["offline_max"] <= 11.5)
fila("Meta de series válidas", "98%", valor("META_PCT_VALIDADAS"), "src/config.py", valor("META_PCT_VALIDADAS") == "0.98")
fila("Semáforo actual", "TSM rojo 23 semanas; AMD amarillo 11",
     f"TSM {sem['TSM']['color_propio']} {sem['TSM']['semanas_propio']}; AMD {sem['AMD']['color_propio']} {sem['AMD']['semanas_propio']}",
     "audit/a2_detector.py", sem["TSM"]["semanas_propio"] == 23 and sem["AMD"]["semanas_propio"] == 11
     and sem["TSM"]["color_propio"] == "rojo" and sem["AMD"]["color_propio"] == "amarillo")
fila("Anticipación puntocom", "11 semanas (16 sin persistencia)",
     f"{AN['Nasdaq 2000-2002']} ({AN['Nasdaq 2000-2002 sin persistencia']} sin persistencia)", "audit/a3_backtest.py",
     AN["Nasdaq 2000-2002"] == 11 and AN["Nasdaq 2000-2002 sin persistencia"] == 16)
rc = a3["rojo_cerca_peaks_sin_burbuja"]
fila("Falsas burbujas en 2008 y 2022 (Nasdaq)", "0",
     f"semanas en rojo con persistencia: 2007-2009 = {rc['Nasdaq 2007-2009']['semanas_rojo_persistente']}, "
     f"2021-2022 = {rc['Nasdaq 2021-2022']['semanas_rojo_persistente']} (bruto: {rc['Nasdaq 2007-2009']['semanas_rojo_bruto']} y "
     f"{rc['Nasdaq 2021-2022']['semanas_rojo_bruto']})", "audit/a3_backtest.py",
     rc["Nasdaq 2007-2009"]["semanas_rojo_persistente"] == 0 and rc["Nasdaq 2021-2022"]["semanas_rojo_persistente"] == 0)
fila("Anticipación Nikkei 1989", "45 semanas", str(AN["Nikkei 1989"]), "audit/a3_backtest.py", AN["Nikkei 1989"] == 45)
fila("Anticipación Bitcoin 2021", "42 semanas", str(AN["Bitcoin 2021"]), "audit/a3_backtest.py", AN["Bitcoin 2021"] == 42)
validas = sum(r["valida"] for r in a1["validaciones"]["tabla"])
fila("IL3", "11/11 válidas; 100% de columnas documentadas", f"{validas}/11; {pct_cols:.0%}", "a1 + docs/diccionario_datos.csv",
     validas == 11 and pct_cols == 1)
fila("IL4 (según logs)", "6/6 sin error", f"{il4['ok']}/{il4['total']} sin error", "logs/", il4["ok"] == il4["total"],
     "El total crece con cada ejecución; se actualiza en el cierre")
fila("Episodios rojos del universo", "204 → 32", f"{universo['episodios_rojos_bruto']} → {universo['episodios_rojos_persistencia']}",
     "audit/a4_cifras.py", universo["episodios_rojos_bruto"] == 204 and universo["episodios_rojos_persistencia"] == 32)
fila("% de semanas en rojo del universo", "6,6% → 4,3%",
     f"{universo['pct_rojo_bruto']:.1%} → {universo['pct_rojo_persistencia']:.1%}", "audit/a4_cifras.py",
     round(universo["pct_rojo_bruto"] * 100, 1) == 6.6 and round(universo["pct_rojo_persistencia"] * 100, 1) == 4.3)
fila("Falsas alarmas por serie sin burbuja", "16,9 → 2,7",
     f"{falsas['bruto_media']:.1f} ± {falsas['bruto_ee']:.1f} → {falsas['pers_media']:.1f} ± {falsas['pers_ee']:.1f} (200 sim, semilla 2027)",
     "audit/a4_cifras.py", abs(falsas["bruto_media"] - 16.9) < 3 * falsas["bruto_ee"] + 0.05
     and abs(falsas["pers_media"] - 2.7) < 3 * falsas["pers_ee"] + 0.05)
fila("Series en rojo desde 2023", "8 de 11 (señal bruta)",
     f"bruta: {len(rojo_2023_bruto)} ({', '.join(rojo_2023_bruto)}); con persistencia: {len(rojo_2023_pers)}",
     "audit/a4_cifras.py", len(rojo_2023_bruto) == 8,
     "La cifra declarada usa la señal bruta; con persistencia el número es distinto")

# Tabla de caídas y percentiles (declarado = outputs/resumen_episodios_v1_v2.csv y resúmenes)
decl = pd.read_csv(RAIZ / "outputs" / "resumen_episodios_v1_v2.csv")
decl = decl.set_index("episodio")
mapa = {"Nasdaq 2000-2002": "Nasdaq 2000-2002", "Nasdaq 2007-2009": "Nasdaq 2007-2009", "Nasdaq 2021-2022": "Nasdaq 2021-2022",
        "Nasdaq completo": "Nasdaq periodo completo", "Cartera B": "Cartera B 2018-hoy (9 acciones)",
        "Nikkei 1989": "Nikkei 1989", "Bitcoin 2021": "Bitcoin 2021"}
for propio, nombre in mapa.items():
    d = decl.loc[nombre]
    m = M[propio]
    dd_decl = [d["caída máx. mantener"], d["caída máx. v1"], d["caída máx. v2"]]
    dd_prop = [m["Mantener 100%"]["caida_maxima"], m["v1"]["caida_maxima"], m["v2"]["caida_maxima"]]
    ok_dd = all(abs(x - y) < 0.0005 for x, y in zip(dd_decl, dd_prop))
    fila(f"Caídas máx. mantener / v1 / v2 — {nombre}", " / ".join(f"{x:.1%}" for x in dd_decl),
         " / ".join(f"{x:.1%}" for x in dd_prop), "audit/a3_backtest.py", ok_dd)
# Percentiles: comparar con el generador propio (semilla distinta) dentro de 3 errores estándar
def comparar_pct(etiqueta, declarado, propio):
    ee = 100 * math.sqrt(max(declarado / 100 * (1 - declarado / 100), 0.01) / 1000) * math.sqrt(2)
    fila(f"Percentil placebo — {etiqueta}", f"{declarado:.1f}", f"{propio:.1f} (generador propio, semilla 2026)",
         "audit/a3_backtest.py", abs(declarado - propio) <= 3 * ee + 0.5, f"tolerancia ±{3 * ee + 0.5:.1f} (error Monte Carlo)")
comparar_pct("Nasdaq completo v1", decl.loc["Nasdaq periodo completo", "percentil placebo v1"], PL["Nasdaq completo v1"])
comparar_pct("Nasdaq completo v2", decl.loc["Nasdaq periodo completo", "percentil placebo v2"], PL["Nasdaq completo v2"])
comparar_pct("Cartera B v1", decl.loc["Cartera B 2018-hoy (9 acciones)", "percentil placebo v1"], PL["Cartera B v1"])
comparar_pct("Cartera B v2", decl.loc["Cartera B 2018-hoy (9 acciones)", "percentil placebo v2"], PL["Cartera B v2"])
comparar_pct("Nikkei 1989 v2", decl.loc["Nikkei 1989", "percentil placebo v2"], PL["Nikkei 1989 v2"])
comparar_pct("Bitcoin 2021 v2", decl.loc["Bitcoin 2021", "percentil placebo v2"], PL["Bitcoin 2021 v2"])
# Retorno anual y Sharpe declarados (cartera A completa y B)
for nombre, ret, sh in (("Nasdaq completo", (0.117, 0.121, 0.111), (0.61, 0.64, 0.63)),
                        ("Cartera B", (0.337, 0.336, 0.315), (1.21, 1.27, 1.31))):
    m = M[nombre]
    rp = [m[k]["retorno_anual"] for k in ("Mantener 100%", "v1", "v2")]
    sp = [m[k]["sharpe"] for k in ("Mantener 100%", "v1", "v2")]
    fila(f"Retorno anual y Sharpe mantener / v1 / v2 — {nombre}",
         " / ".join(f"{x:.1%}" for x in ret) + " · " + " / ".join(f"{x:.2f}" for x in sh),
         " / ".join(f"{x:.1%}" for x in rp) + " · " + " / ".join(f"{x:.2f}" for x in sp), "audit/a3_backtest.py",
         all(abs(x - y) < 0.0005 for x, y in zip(ret, rp)) and all(abs(x - y) < 0.005 for x, y in zip(sh, sp)))

tabla = pd.DataFrame(filas)
tabla.to_csv(RES / "cifras.csv", index=False)
encabezado = "| " + " | ".join(tabla.columns) + " |\n|" + "---|" * len(tabla.columns) + "\n"
cuerpo = "".join("| " + " | ".join(str(v) for v in fila) + " |\n" for fila in tabla.itertuples(index=False))
(RES / "cifras.md").write_text(encabezado + cuerpo, encoding="utf-8")
json.dump({"universo": universo, "falsas_alarmas": falsas, "il4": il4, "pct_columnas": pct_cols},
          open(RES / "a4_extra.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
print(tabla[["cifra", "declarado", "recalculado", "estado"]].to_string())
