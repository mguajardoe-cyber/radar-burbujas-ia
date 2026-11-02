# =============================================================================
# Auditoría — 5. Reproducibilidad (comparación)
# Compara el semáforo actual del repositorio original con el del clon limpio.
# Uso: python a5_comparar.py <semaforo_original.csv> <semaforo_clon.csv>
# =============================================================================

import sys

import pandas as pd

a = pd.read_csv(sys.argv[1]).set_index("ticker").sort_index()
b = pd.read_csv(sys.argv[2]).set_index("ticker").sort_index()
columnas = ["semaforo", "semanas_en_estado", "semaforo_bruto"]
print("semaforo identico:", a[columnas].equals(b[columnas]),
      "| dif max bsadf:", float((a["bsadf"] - b["bsadf"].reindex(a.index)).abs().max()))
