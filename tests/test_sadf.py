# =============================================================================
# Pruebas — Capa 3: test de burbuja (src/sadf.py)
#
# Propósito: verificar que el ADF rápido (sumas acumuladas) entrega el mismo
#   estadístico que statsmodels.adfuller, tanto en ventanas que parten en el
#   inicio (SADF anclado) como en ventanas que terminan en la última semana
#   (BSADF), y que el BSADF es el máximo de esas regresiones.
# Entradas: caminata aleatoria simulada (semilla fija).
# Salidas: resultado de pytest.
# =============================================================================

import numpy as np
import pandas as pd
import pytest
from statsmodels.tsa.stattools import adfuller

from src import sadf as S


def adf_statsmodels(y):
    return adfuller(y, maxlag=1, autolag=None, regression="c", result_object=False)[0]


@pytest.fixture
def serie():
    rng = np.random.default_rng(123)
    return np.cumsum(0.002 + 0.03 * rng.standard_normal(300))


def test_adf_recursivo_coincide_con_statsmodels(serie):
    n0 = 31
    rapido = S.adf_recursivo(serie, n0)
    for w in (n0, 120, len(serie)):
        assert rapido[w - n0] == pytest.approx(adf_statsmodels(serie[:w]), abs=1e-8)


def test_adf_hacia_atras_coincide_con_statsmodels(serie):
    n0 = 31
    tramo = serie[-260:]
    rapido = S.adf_hacia_atras(tramo, n0)
    for inicio in (0, 100, 260 - n0):
        assert rapido[inicio] == pytest.approx(adf_statsmodels(tramo[inicio:]), abs=1e-8)


def test_bsadf_es_el_maximo_de_las_regresiones(serie):
    ventana = 260
    _, n0 = S.ventana_minima(ventana)
    bsadf = S.bsadf_movil(pd.Series(serie), ventana)
    tramo = serie[-ventana:]
    fuerza_bruta = max(adf_statsmodels(tramo[s:]) for s in range(ventana - n0 + 1))
    assert bsadf.iloc[-1] == pytest.approx(fuerza_bruta, abs=1e-8)
