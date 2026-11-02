# =============================================================================
# Pruebas — Orquestador (src/main.py)
#
# Propósito: verificar que el flujo completo se ejecuta sin internet
#   (main.py --offline, con los CSV versionados de data/raw) y termina con
#   código de salida 0. La corrida queda en el log con origen "pruebas", para
#   separarla de las manuales y programadas en los KPIs IL4.
# Entradas: data/raw/precios_diarios.csv y data/processed/cv_bsadf.json.
# Salidas: resultado de pytest. La ejecución escribe su log en logs/ y
#   regenera data/processed y el reporte de outputs/, como una corrida normal.
# =============================================================================

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_main_offline_termina_con_codigo_0():
    resultado = subprocess.run([sys.executable, str(RAIZ / "src" / "main.py"), "--offline", "--origen", "pruebas"],
                               cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert resultado.returncode == 0, resultado.stdout[-2000:] + resultado.stderr[-2000:]
    assert "RESUMEN_EJECUCION estado=OK" in resultado.stdout
