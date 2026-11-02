# =============================================================================
# Auditoría — notebooks ejecutados vs. cifras del README
# Revisa que los 9 notebooks no tengan errores ni celdas sin ejecutar y que
# las cifras clave de sus salidas coincidan con las publicadas en README.md.
# Salida: audit/resultados/notebooks_vs_readme.txt
# =============================================================================

import json
import re

import pandas as pd

from comun import RAIZ, DIR_AUDIT

NOTEBOOKS = ["01_prueba_concepto_sadf", "02_ingesta_y_validacion", "03_features_y_semaforo", "03b_bsadf_ventana_movil",
             "04_kmeans", "06_backtest_kpis", "06b_regla_enfriamiento_fuera_de_muestra", "06c_kpis_negocio", "07_reporte"]
lineas, textos = [], {}
for n in NOTEBOOKS:
    nb = json.load(open(RAIZ / "notebooks" / f"{n}.ipynb", encoding="utf-8"))
    codigo = [c for c in nb["cells"] if c["cell_type"] == "code"]
    errores = sum(o.get("output_type") == "error" for c in codigo for o in c.get("outputs", []))
    sin_ejecutar = sum(c.get("execution_count") is None for c in codigo)
    salidas = []
    for c in codigo:
        for o in c.get("outputs", []):
            salidas.append("".join(o.get("text", "")))
            datos = o.get("data", {})
            salidas.append(re.sub(r"<[^>]+>", " ", "".join(datos.get("text/html", ""))))
            salidas.append("".join(datos.get("text/plain", "")))
    textos[n] = re.sub(r"\s+", " ", " ".join(salidas))
    lineas.append(f"{n}: {len(codigo)} celdas de código, {errores} errores, {sin_ejecutar} sin ejecutar")

def esta(n, patron):
    return re.search(patron, textos[n]) is not None

chequeos = {
    "01: primera señal 12-11-1999": esta("01_prueba_concepto_sadf", r"12-11-1999"),
    "01: caída Nasdaq -77.9%": esta("01_prueba_concepto_sadf", r"-77\.9%"),
    "02: 11/11 series válidas (100%)": esta("02_ingesta_y_validacion", r"100\.0% .{0,20}≥ 98%") or esta("02_ingesta_y_validacion", r"100\.0%"),
    "03b: rojo 11 semanas antes con persistencia (16 bruto)": esta("03b_bsadf_ventana_movil", r"11 semanas antes del peak \(señal bruta: 16"),
    "03b: episodios rojos 204 → 32": esta("03b_bsadf_ventana_movil", r"Señal bruta 204") and esta("03b_bsadf_ventana_movil", r"\(vigente\) 32"),
    "03b: % rojo 6,6% → 4,3%": esta("03b_bsadf_ventana_movil", r"6\.6%") and esta("03b_bsadf_ventana_movil", r"4\.3%"),
    "03b: TSM rojo 23 y AMD amarillo 11": esta("03b_bsadf_ventana_movil", r"TSM Taiwan Semiconductor rojo 23")
                                          and esta("03b_bsadf_ventana_movil", r"AMD Advanced Micro Devices amarillo 11"),
    "06: caída A -73,2% vs -77,4%": esta("06_backtest_kpis", r"-73\.2% vs\. -77\.4%"),
    "06: caída B -43,5% vs -45,4%": esta("06_backtest_kpis", r"-43\.5% vs\. -45\.4%"),
    "06: percentiles placebo 14,4 / 49,0": esta("06_backtest_kpis", r"14\.4 / 49\.0"),
    "06: IL3 100% (11/11)": esta("06_backtest_kpis", r"100% \(11/11\)"),
    "06b: Nikkei -57,7% vs -61,9%, percentil 53,6": esta("06b_regla_enfriamiento_fuera_de_muestra", r"-57\.7% vs\. -61\.9%\); \(b\) percentil placebo = 53\.6"),
    "06b: Bitcoin -53,5% vs -74,2%, percentil 13,2": esta("06b_regla_enfriamiento_fuera_de_muestra", r"-53\.5% vs\. -74\.2%\); \(b\) percentil placebo = 13\.2"),
    "06b: anticipación Nikkei 45 y Bitcoin 42": esta("06b_regla_enfriamiento_fuera_de_muestra", r"anticipación del rojo: 45")
                                                and esta("06b_regla_enfriamiento_fuera_de_muestra", r"anticipación del rojo: 42"),
    "06b: 1 de 2, v2 no validada": esta("06b_regla_enfriamiento_fuera_de_muestra", r"Cumplen \(a\) y \(b\): 1 de 2")
                                   and esta("06b_regla_enfriamiento_fuera_de_muestra", r"NO VALIDADA"),
    "06b: v2 Nasdaq -64,8% (percentil 13,1)": esta("06b_regla_enfriamiento_fuera_de_muestra", r"-64\.8%")
                                               and esta("06b_regla_enfriamiento_fuera_de_muestra", r"13\.1"),
    "04: 9.971 observaciones": esta("04_kmeans", r"4 variables\): 9\.971"),
    "04: k = 3 con silhouette 0,374": esta("04_kmeans", r"\(k = 3,") and esta("04_kmeans", r"\b3 21183\.901 0\.374\b"),
    "06c: pérdida evitada Nasdaq US$12,6 M": esta("06c_kpis_negocio", r"Nasdaq 2000-2002 .{0,120}US\$ 12,6 M"),
    "06c: 1,1 episodios rojos por año (9 acciones)": esta("06c_kpis_negocio", r"1\.1 en las 9 acciones"),
    "07: reporte con 4 hojas": esta("07_reporte", r"\['Semáforo', 'Variables', 'Gráficos', 'Registro de revisión'\]"),
}
readme = (RAIZ / "README.md").read_text(encoding="utf-8")
en_readme = {"−73,2%": "−73,2%" in readme, "−77,4%": "−77,4%" in readme, "−64,8%": "−64,8%" in readme,
             "percentil 14": "percentil 14" in readme, "49": "en el 49" in readme, "13,2": "13,2" in readme,
             "53,6": "53,6" in readme, "11 semanas": "11 semanas" in readme, "45": "**45**" in readme,
             "42": "**42**" in readme, "TSM en rojo, AMD en amarillo": "TSM en rojo, AMD en amarillo" in readme,
             "US$12,6 M": "US$12,6 M" in readme, "1,1 por año": "1,1 por año" in readme,
             "k = 3": "k = 3" in readme, "0,374": "0,374" in readme}
lineas += [f"{'OK ' if v else 'NO '} {k}" for k, v in chequeos.items()]
lineas += [f"{'OK ' if v else 'NO '} README contiene {k}" for k, v in en_readme.items()]
semaforo = pd.read_csv(RAIZ / "data" / "processed" / "semaforo_actual.csv")
lineas.append("Semáforo actual: " + ", ".join(f"{t} {c} {n}" for t, c, n in
                                              zip(semaforo.ticker, semaforo.semaforo, semaforo.semanas_en_estado)))
(DIR_AUDIT / "resultados" / "notebooks_vs_readme.txt").write_text("\n".join(lineas), encoding="utf-8")
print("\n".join(lineas))
