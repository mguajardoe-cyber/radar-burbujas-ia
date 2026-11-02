# =============================================================================
# Orquestador — ejecución semanal completa del Radar de Burbujas IA
#
# Propósito:
#   Ejecutar todo el flujo con un solo comando:
#     ingesta → validación → BSADF + semáforo → variables → perfil de riesgo
#     (K-Means, modelo guardado) → reporte Excel.
#   Modos:
#     python src/main.py            descarga datos nuevos desde Yahoo Finance
#     python src/main.py --offline  usa los CSV de data/raw (reproducible sin internet)
#   --origen manual | programada | pruebas: quién lanzó la corrida (por defecto
#   manual). La ejecución programada (GitHub Actions o Programador de tareas
#   de Windows) usa "programada"; tests/test_main.py usa "pruebas".
#   Si falla la descarga o menos del 98% de las series pasa las validaciones,
#   la ejecución se marca FALLIDA en el log, no se sobrescriben los resultados
#   anteriores y el programa termina con código de salida 1.
#   Las alertas de deriva (src/monitoreo.py: datos desactualizados, cambio de
#   más de 10% en las filas, salto de más de 50% en la última semana) quedan
#   como WARNING en el log y no hacen fallar la ejecución.
#
# Entradas:
#   - Yahoo Finance (modo normal) o data/raw/precios_diarios.csv (offline).
#   - Parámetros de src/config.py.
#
# Salidas:
#   - data/processed/*.csv (datos validados, panel semanal, semáforo actual).
#   - outputs/reporte_radar_AAAA-MM-DD.xlsx
#   - logs/radar_AAAA-MM-DD.log: inicio, fin, duración, tickers procesados y
#     excluidos (con motivo), KPIs IL3 (src/kpis.py) y errores. La línea
#     RESUMEN_EJECUCION alimenta los KPIs IL4.
# =============================================================================

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src import config as C
from src import features as F
from src import ingesta as I
from src import kpis as K
from src import monitoreo as M
from src import perfiles as P
from src import reporte as R

log = logging.getLogger("radar.main")


class EjecucionFallida(Exception):
    """Falla controlada: descarga sin datos o validación bajo la meta."""


def configurar_log():
    """Log en archivo (logs/radar_AAAA-MM-DD.log, se agrega si ya existe) y en consola."""
    ruta = C.DIR_LOGS / f"radar_{datetime.now():%Y-%m-%d}.log"
    formato = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.handlers.clear()
    for manejador in (logging.FileHandler(ruta, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        manejador.setFormatter(formato)
        raiz.addHandler(manejador)
    return ruta


def ejecutar(offline, resumen):
    """Flujo completo. Va completando `resumen` a medida que avanza, para que
    el log tenga los datos disponibles aunque la ejecución falle a mitad."""
    tickers = list(C.UNIVERSO) + list(C.INDICES)
    resumen.update(series_validas=0, series_totales=len(tickers), pct_validas=0.0, excluidos="-", reporte="-",
                   alertas=[])

    # Capa 2: ingesta y validación
    if offline:
        crudo = pd.read_csv(C.DIR_RAW / "precios_diarios.csv", parse_dates=["fecha"])
        log.info("Modo offline: %d filas leídas de data/raw/precios_diarios.csv", len(crudo))
    else:
        crudo = I.descargar(tickers)
    resumen["filas"] = len(crudo)
    if crudo.empty:
        raise EjecucionFallida("la descarga no devolvió datos")
    alertas = resumen["alertas"]

    validados, tabla_validacion, kpi = I.validar_universo(crudo, tickers)
    excluidos = tabla_validacion[~tabla_validacion["valida"]]
    resumen.update(series_validas=kpi["series_validadas"], pct_validas=100 * kpi["pct_validadas"],
                   excluidos=",".join(excluidos["ticker"]) or "-")
    log.info("Tickers procesados: %s", ", ".join(tickers))
    for _, fila in excluidos.iterrows():
        log.error("Ticker excluido: %s — %s", fila["ticker"], fila["motivo_exclusion"])
    # KPIs IL3 y alertas de deriva de los datos (antes de la alerta de falla,
    # para que queden en el log aunque la ejecución falle)
    il3 = K.kpis_il3(crudo, validados, tabla_validacion)
    K.registrar_il3(il3)
    M.alerta_frescura(il3["frescura"]["valor"], il3["frescura"]["ultima_fecha"], alertas)
    M.alerta_filas(len(crudo), M.filas_corrida_anterior(), alertas)
    if kpi["alerta"]:
        raise EjecucionFallida(f"solo {100 * kpi['pct_validadas']:.1f}% de las series pasó las validaciones")
    I.guardar(crudo, validados, tabla_validacion, guardar_raw=not offline)

    # Capa 3: BSADF, semáforo con persistencia y variables
    panel = F.construir_panel(validados)
    actual = F.semaforo_actual(panel)
    # Perfil de riesgo K-Means (descriptivo; no cambia el semáforo)
    actual["perfil_riesgo"] = P.asignar(actual, P.cargar_o_entrenar(panel))
    M.alerta_saltos(panel, alertas)
    F.guardar(panel, actual)
    log.info("Semáforo al %s: %s", f"{actual['fecha'].max():%d-%m-%Y}",
             ", ".join(f"{t} {c}" for t, c in zip(actual["ticker"], actual["semaforo"])))

    # Capa 4: reporte
    resumen["reporte"] = R.generar_reporte(panel, actual).name


def main(argv=None):
    parser = argparse.ArgumentParser(description="Radar de Burbujas IA — ejecución semanal")
    parser.add_argument("--offline", action="store_true", help="usar los CSV de data/raw en vez de descargar")
    parser.add_argument("--origen", choices=["manual", "programada", "pruebas"], default="manual",
                        help="quién lanzó la ejecución (separa las corridas en los KPIs IL4)")
    args = parser.parse_args(argv)

    ruta_log = configurar_log()
    modo = "offline" if args.offline else "normal"
    inicio = time.time()
    log.info("INICIO de la ejecución (modo %s, origen %s)", modo, args.origen)
    estado, codigo = "OK", 0
    resumen = {}
    try:
        ejecutar(args.offline, resumen)
    except EjecucionFallida as e:
        estado, codigo = "FALLIDA", 1
        log.error("EJECUCIÓN FALLIDA: %s. No se actualizaron resultados ni reporte.", e)
    except Exception:
        estado, codigo = "FALLIDA", 1
        log.exception("EJECUCIÓN FALLIDA por error inesperado")
    duracion = time.time() - inicio
    log.info("FIN de la ejecución: estado %s, duración %.1f s", estado, duracion)
    log.info("RESUMEN_EJECUCION estado=%s modo=%s origen=%s fin_utc=%s duracion_s=%.1f series_validas=%s/%s "
             "pct_validas=%.1f filas=%s alertas=%d excluidos=%s reporte=%s", estado, modo, args.origen,
             f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}", duracion, resumen.get("series_validas", 0),
             resumen.get("series_totales", 0), resumen.get("pct_validas", 0.0), resumen.get("filas", 0),
             len(resumen.get("alertas", [])), resumen.get("excluidos", "-"), resumen.get("reporte", "-"))

    # KPIs IL4 con todas las ejecuciones registradas (incluida esta); no cambian el estado
    try:
        K.registrar_il4(K.kpis_il4())
    except Exception:
        log.exception("No se pudieron calcular los KPIs IL4 desde los logs")
    print(f"\nLog: {ruta_log}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
