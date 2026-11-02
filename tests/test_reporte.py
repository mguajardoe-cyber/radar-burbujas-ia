# =============================================================================
# Pruebas — Capa 4: reporte Excel (src/reporte.py)
#
# Propósito: verificar que el reporte trae la hoja "Registro de revisión" y que,
#   si el reporte de la semana se regenera, se conservan las revisiones que el
#   operador ya anotó (evidencia del KPI IL4 de frecuencia de uso).
# Entradas: data/processed/panel_semanal.csv y semaforo_actual.csv (versionados).
# Salidas: resultado de pytest (el reporte de prueba se escribe en una carpeta
#   temporal, no en outputs/).
# =============================================================================

import pandas as pd
from openpyxl import load_workbook

from src import config as C
from src import reporte as R


def test_registro_de_revision_se_conserva_al_regenerar(tmp_path):
    panel = pd.read_csv(C.DIR_PROCESSED / "panel_semanal.csv", parse_dates=["fecha"])
    actual = pd.read_csv(C.DIR_PROCESSED / "semaforo_actual.csv", parse_dates=["fecha"])
    ruta = R.generar_reporte(panel, actual, directorio=tmp_path)
    assert R.HOJA_REGISTRO in load_workbook(ruta).sheetnames and R.leer_registro(ruta) == []

    libro = load_workbook(ruta)
    libro[R.HOJA_REGISTRO].append(["2026-11-09", "Operador", "Reducir TSM a 50%", "prueba"])
    libro.save(ruta)
    R.generar_reporte(panel, actual, directorio=tmp_path)
    assert R.leer_registro(ruta) == [("2026-11-09", "Operador", "Reducir TSM a 50%", "prueba")]
