# =============================================================================
# Pruebas — Capa 7: backtest (src/backtest.py)
#
# Propósito: verificar que (1) la señal de la semana t solo afecta la
#   exposición desde el retorno de t+2 (sin sesgo de anticipación) y (2) el
#   placebo conserva número y duración de los episodios y los ubica al azar
#   (no casi equiespaciados; hallazgo C1 de la auditoría).
# Entradas: series sintéticas.
# Salidas: resultado de pytest.
# =============================================================================

import numpy as np
import pandas as pd

from src import backtest as B


def test_senal_de_t_rige_desde_t_mas_2():
    colores = pd.Series(["verde"] * 20)
    colores[10] = "rojo"
    efectiva = B.exposicion_efectiva(B.exposicion_objetivo(colores)).to_numpy()
    assert (efectiva[:12] == 1.0).all()
    assert efectiva[12] == 0.5


def test_placebo_conserva_episodios_y_los_ubica_al_azar():
    rng = np.random.default_rng(0)
    duraciones = np.array([61, 21, 20, 21])
    n = 1661
    inicios = []
    for _ in range(500):
        m = B.mascara_aleatoria(n, duraciones, rng)
        assert sorted(B.episodios(m)) == sorted(duraciones)
        inicios.append(np.flatnonzero(m)[0])
    # Con posiciones al azar, el primer episodio puede empezar en buena parte de la serie
    # (la versión con multinomial lo dejaba siempre entre las semanas ~250 y ~360)
    assert np.ptp(inicios) > 0.4 * (n - duraciones.sum())
