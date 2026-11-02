# =============================================================================
# Pruebas — Capa 7: KPIs (src/kpis.py)
#
# Propósito: verificar el cálculo de los KPIs IL3 (completitud, duplicidad,
#   frescura) sobre series sintéticas, el criterio del SLA (lunes 08:00 en
#   Chile) y las etiquetas MEDIDO / DEFINIDO de los KPIs IL4.
# Entradas: series diarias sintéticas (mismo generador que test_ingesta.py) y
#   ejecuciones de ejemplo.
# Salidas: resultado de pytest.
# =============================================================================

import pandas as pd

from src import ingesta as I
from src import kpis as K
from tests.test_ingesta import serie_sintetica


def test_kpis_il3_completitud_duplicidad_y_frescura():
    accion = serie_sintetica("ACC", dias=20)
    accion.loc[3, "volume"] = 0                                  # 1 día eliminado → 19/20 válidos
    duplicada = serie_sintetica("DUP", dias=20)
    duplicada = pd.concat([duplicada, duplicada.iloc[[5]]], ignore_index=True)   # serie excluida
    crudo = pd.concat([accion, duplicada], ignore_index=True)

    validados, tabla, _ = I.validar_universo(crudo, ["ACC", "DUP"])
    k = K.kpis_il3(crudo, validados, tabla, fecha_ejecucion=crudo["fecha"].max() + pd.Timedelta(days=3))

    assert k["cobertura"]["validas"] == 1 and k["cobertura"]["total"] == 2
    por_serie = k["completitud"]["por_serie"].set_index("ticker")
    assert por_serie.loc["ACC", "dias_validos"] == 19 and por_serie.loc["DUP", "dias_validos"] == 0
    assert k["completitud"]["valor"] == 19 / 41
    assert k["duplicidad"]["valor"] == 1 / 41
    assert k["frescura"]["valor"] == 3


def test_sla_reporte_listo_antes_del_lunes_8_en_chile():
    # 16-11-2026 es lunes; en noviembre Chile está en UTC-3
    assert K.reporte_a_tiempo("2026-11-16T02:10:00Z")          # domingo 23:10 en Chile
    assert K.reporte_a_tiempo("2026-11-16T10:59:00Z")          # lunes 07:59
    assert not K.reporte_a_tiempo("2026-11-16T11:01:00Z")      # lunes 08:01


def test_il4_queda_definido_sin_corridas_programadas_ni_revisiones():
    ejecuciones = pd.DataFrame({"estado": ["OK", "OK", "FALLIDA"], "modo": "offline",
                                "origen": ["manual", "pruebas", "manual"], "fin_utc": None,
                                "duracion_s": [2.0, 3.0, 4.0]})
    revisiones = pd.DataFrame(columns=["reporte", "Fecha de la reunión", "Revisor", "Decisión tomada", "Comentarios"])
    k = K.kpis_il4(ejecuciones, revisiones)
    assert k["exito"]["etiqueta"] == K.MEDIDO and k["exito"]["ok"] == 2 and k["exito"]["total"] == 3
    assert k["duracion"]["valor"] == 4.0 and k["duracion"]["promedio"] == 3.0
    assert k["sla"]["etiqueta"] == K.DEFINIDO and k["uso"]["etiqueta"] == K.DEFINIDO
