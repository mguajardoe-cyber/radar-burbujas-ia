# =============================================================================
# Pruebas — Capa 2: validaciones de datos (src/ingesta.py)
#
# Propósito: verificar que la validación detecta fechas duplicadas y precios
#   no positivos (la serie se excluye), y que a los índices no se les exige
#   volumen positivo.
# Entradas: series diarias sintéticas.
# Salidas: resultado de pytest.
# =============================================================================

import numpy as np
import pandas as pd

from src import ingesta as I


def serie_sintetica(ticker="TEST", dias=30):
    fechas = pd.bdate_range("2024-01-01", periods=dias)
    precio = 100 + np.arange(dias, dtype=float)
    return pd.DataFrame({"ticker": ticker, "fecha": fechas, "open": precio, "high": precio + 1,
                         "low": precio - 1, "close": precio, "adj_close": precio, "volume": 1000})


def test_serie_limpia_es_valida():
    df = serie_sintetica()
    _, resultado = I.validar_serie(df, df["fecha"].max())
    assert resultado["valida"]


def test_detecta_fechas_duplicadas():
    df = serie_sintetica()
    df = pd.concat([df, df.iloc[[5]]], ignore_index=True)
    _, resultado = I.validar_serie(df, df["fecha"].max())
    assert not resultado["valida"]
    assert resultado["duplicados"] == 1
    assert "duplicadas" in resultado["motivo_exclusion"]


def test_detecta_precios_no_positivos():
    df = serie_sintetica()
    df.loc[10, "close"] = 0.0
    df.loc[11, "adj_close"] = -5.0
    _, resultado = I.validar_serie(df, df["fecha"].max())
    assert not resultado["valida"]
    assert resultado["dias_precio_no_positivo"] == 2
    assert "no positivos" in resultado["motivo_exclusion"]


def test_volumen_cero_se_elimina_en_acciones_y_no_en_indices():
    accion = serie_sintetica("ACC")
    accion.loc[3, "volume"] = 0
    limpia, resultado = I.validar_serie(accion, accion["fecha"].max())
    assert resultado["valida"] and resultado["dias_volumen_cero_eliminados"] == 1
    assert len(limpia) == len(accion) - 1

    indice = serie_sintetica("^IDX")
    indice["volume"] = 0
    limpio, resultado = I.validar_serie(indice, indice["fecha"].max())
    assert resultado["valida"] and len(limpio) == len(indice)
