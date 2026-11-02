# =============================================================================
# Pruebas — Capa 3: perfiles de riesgo K-Means (src/perfiles.py)
#
# Propósito: verificar que K-Means es reproducible con la semilla fija (mismos
#   centroides y nombres al reentrenar) y que el modelo guardado asigna un
#   perfil a todas las acciones del universo en la semana actual.
# Entradas: data/processed/panel_semanal.csv, semaforo_actual.csv y
#   perfiles_kmeans.json (versionados).
# Salidas: resultado de pytest.
# =============================================================================

import json

import numpy as np
import pandas as pd

from src import config as C
from src import perfiles as P


def test_kmeans_reproducible_con_la_semilla():
    panel = pd.read_csv(C.DIR_PROCESSED / "panel_semanal.csv", parse_dates=["fecha"])
    a = P.ajustar(panel, k=3, ks=(3,))
    b = P.ajustar(panel, k=3, ks=(3,))
    assert np.allclose(a["centroides_z"], b["centroides_z"])
    assert a["nombres"] == b["nombres"] and a["tamanos"] == b["tamanos"]


def test_perfil_asignado_a_todas_las_acciones():
    modelo = json.loads(C.RUTA_PERFILES.read_text(encoding="utf-8"))
    actual = pd.read_csv(C.DIR_PROCESSED / "semaforo_actual.csv", parse_dates=["fecha"])
    acciones = actual[actual["ticker"].isin(C.UNIVERSO)]
    perfiles = P.asignar(acciones, modelo)
    assert len(acciones) == len(C.UNIVERSO)
    assert perfiles.isin(modelo["nombres"]).all()
