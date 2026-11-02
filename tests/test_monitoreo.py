# =============================================================================
# Pruebas — Capa 6: alertas de deriva (src/monitoreo.py)
#
# Propósito: verificar que las tres alertas (datos desactualizados, variación
#   de filas y salto semanal) se activan sobre sus umbrales y no bajo ellos.
# Entradas: valores y panel sintéticos.
# Salidas: resultado de pytest.
# =============================================================================

import pandas as pd

from src import monitoreo as M


def test_alertas_de_deriva_se_activan_solo_sobre_el_umbral():
    alertas = []
    M.alerta_frescura(7, "2026-10-30", alertas)
    M.alerta_filas(1050, 1000, alertas)                 # +5%: sin alerta
    assert alertas == []

    M.alerta_frescura(8, "2026-10-30", alertas)
    M.alerta_filas(850, 1000, alertas)                  # −15%: alerta
    M.alerta_filas(1000, None, alertas)                 # sin corrida anterior: no compara
    assert len(alertas) == 2

    fechas = pd.to_datetime(["2026-10-23", "2026-10-30"])
    panel = pd.DataFrame({"ticker": ["AAA", "AAA", "BBB", "BBB"], "fecha": list(fechas) * 2,
                          "adj_close": [100.0, 160.0, 100.0, 110.0]})
    M.alerta_saltos(panel, alertas)                     # AAA +60%: alerta; BBB +10%: no
    assert len(alertas) == 3 and "AAA" in alertas[-1]
