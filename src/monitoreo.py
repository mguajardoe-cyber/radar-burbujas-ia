# =============================================================================
# Capa 6 — Mantenimiento: alertas de deriva
#
# Propósito:
#   Avisar en el log (nivel WARNING) cuando los datos de una corrida se ven
#   distintos a lo esperado, aunque pasen las validaciones. Las alertas NO
#   hacen fallar la corrida: son una señal para que el operador revise.
#     1. Datos desactualizados: el último dato tiene más de 7 días.
#     2. Variación de más de 10% en las filas descargadas frente a la corrida
#        anterior (posible serie truncada o descarga incompleta).
#     3. Serie con un salto de más de 50% en la última semana (posible error
#        de precio o evento corporativo no ajustado).
#   Cada corrida registra el número de alertas en RESUMEN_EJECUCION (alertas=).
#
# Entradas:
#   - Descarga cruda y panel semanal de la corrida.
#   - logs/radar_*.log (filas de la corrida anterior, vía src/kpis.py).
#   - Umbrales de src/config.py.
#
# Salidas:
#   - Líneas "ALERTA DE DERIVA" en el log; lista de alertas de la corrida.
# =============================================================================

import logging

import pandas as pd

from src import config as C
from src import kpis as K

log = logging.getLogger("radar.monitoreo")


def _alertar(alertas, texto, *args):
    mensaje = texto % args
    log.warning("ALERTA DE DERIVA — %s", mensaje)
    alertas.append(mensaje)


def filas_corrida_anterior(ejecuciones=None):
    """Filas descargadas en la última corrida registrada que informó ese dato
    (las corridas más antiguas no lo registraban). None si no hay."""
    ejecuciones = K.leer_ejecuciones() if ejecuciones is None else ejecuciones
    if ejecuciones.empty:
        return None
    filas = pd.to_numeric(ejecuciones["filas"], errors="coerce").dropna()
    filas = filas[filas > 0]
    return int(filas.iloc[-1]) if len(filas) else None


def alerta_frescura(dias, ultima_fecha, alertas):
    if dias > C.META_FRESCURA_DIAS:
        _alertar(alertas, "datos desactualizados: el último dato es del %s, hace %d días (máximo %d)",
                 ultima_fecha, dias, C.META_FRESCURA_DIAS)


def alerta_filas(filas, filas_previas, alertas):
    if filas_previas is None:
        log.info("Deriva de filas: sin corrida anterior que informe filas; no se compara")
        return
    variacion = filas / filas_previas - 1
    log.info("Deriva de filas: %d filas vs. %d en la corrida anterior (%+.2f%%)", filas, filas_previas,
             100 * variacion)
    if abs(variacion) > C.UMBRAL_VARIACION_FILAS:
        _alertar(alertas, "las filas descargadas variaron %+.1f%% frente a la corrida anterior (%d → %d; "
                 "máximo ±%.0f%%)", 100 * variacion, filas_previas, filas, 100 * C.UMBRAL_VARIACION_FILAS)


def saltos_ultima_semana(panel):
    """Variación del cierre ajustado en la última semana de cada ticker."""
    ultimas = panel.dropna(subset=["adj_close"]).sort_values("fecha").groupby("ticker").tail(2)
    return ultimas.groupby("ticker")["adj_close"].apply(lambda s: s.iloc[-1] / s.iloc[0] - 1 if len(s) == 2 else 0.0)


def alerta_saltos(panel, alertas):
    for ticker, variacion in saltos_ultima_semana(panel).items():
        if abs(variacion) > C.UMBRAL_SALTO_SEMANAL:
            _alertar(alertas, "%s varió %+.0f%% en la última semana (máximo ±%.0f%%): revisar el precio",
                     ticker, 100 * variacion, 100 * C.UMBRAL_SALTO_SEMANAL)
