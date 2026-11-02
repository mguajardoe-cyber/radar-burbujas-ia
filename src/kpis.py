# =============================================================================
# Capa 7 — KPIs por nivel de madurez (IL3, IL4, IL5)
#
# Propósito:
#   Calcular los KPIs del producto con una etiqueta que dice cómo se obtuvo
#   cada valor:
#     - MEDIDO:     calculado con datos o logs reales.
#     - DEFINIDO:   meta y forma de medición fijadas, sin datos todavía.
#     - PROYECTADO: calculado con supuestos (parámetros SUPUESTO de config.py).
#   IL3 (calidad de datos), en cada ejecución de main.py:
#     - Cobertura de fuentes: series válidas / series del universo.
#     - Completitud: días válidos / días descargados, por serie y total.
#     - Tasa de duplicidad: filas (ticker, fecha) duplicadas / filas totales.
#     - Campos documentados: columnas en el diccionario / columnas del dataset.
#     - Frescura: días entre la última fecha de datos y la ejecución.
#   IL4 (operación), leyendo las líneas RESUMEN_EJECUCION de los logs:
#     - Tasa de corridas sin error y duración máxima y promedio (MEDIDO).
#     - SLA: % de corridas programadas con reporte listo antes del lunes 08:00
#       en Chile (DEFINIDO hasta que existan corridas programadas).
#     - Frecuencia de uso: revisiones por semana anotadas en la hoja
#       "Registro de revisión" de los reportes (DEFINIDO: hoy no hay usuario real).
#   IL5 (impacto), en lenguaje de negocio (notebook 06c):
#     - Pérdida evitada en US$ por episodio con la regla v2 (PROYECTADO:
#       usa EXPOSICION_USD; la v2 NO está validada fuera de muestra, 1 de 2).
#     - Decisiones habilitadas: episodios rojos por año (MEDIDO en el historial).
#     - Eficiencia operativa: horas de análisis manual reemplazadas al año
#       (PROYECTADO: usa HORAS_ANALISIS_SEMANA) vs. la duración real de main.py.
#
# Entradas:
#   - Descarga cruda, precios validados y tabla de validación (src/ingesta.py).
#   - docs/diccionario_datos.csv, logs/radar_*.log, outputs/reporte_radar_*.xlsx.
#   - outputs/resumen_episodios_v1_v2.csv (notebook 06b) y panel semanal.
#   - Metas y supuestos (marcados SUPUESTO) de src/config.py.
#
# Salidas:
#   - Diccionarios y tablas de KPIs; líneas KPI IL3 / IL4 en el log de main.py.
# =============================================================================

import logging
import re

import pandas as pd

from src import config as C
from src import ingesta as I

log = logging.getLogger("radar.kpis")

MEDIDO, DEFINIDO, PROYECTADO = "MEDIDO", "DEFINIDO", "PROYECTADO"


# --- IL3: calidad de datos ------------------------------------------------------

def cobertura_fuentes(tabla_validacion):
    """Series válidas / series del universo (los tickers sin datos cuentan como no válidos)."""
    validas, total = int(tabla_validacion["valida"].sum()), len(tabla_validacion)
    return {"valor": validas / total if total else 0.0, "validas": validas, "total": total}


def completitud(crudo, validados):
    """Días válidos / días descargados, por serie y total.

    Días descargados = filas de la descarga cruda. Días válidos = filas que
    quedan en los datos validados (una serie excluida aporta 0 días válidos;
    en una serie válida solo se pierden los días con volumen no positivo).
    Devuelve (tabla por ticker, valor total).
    """
    descargados = crudo.groupby("ticker").size().rename("dias_descargados")
    validos = (validados.groupby("ticker").size() if len(validados) else pd.Series(dtype=int)).rename("dias_validos")
    tabla = pd.concat([descargados, validos], axis=1).fillna(0).astype(int)
    tabla["completitud"] = tabla["dias_validos"] / tabla["dias_descargados"]
    total = tabla["dias_validos"].sum() / tabla["dias_descargados"].sum() if len(tabla) else 0.0
    return tabla.reset_index(names="ticker"), total


def tasa_duplicidad(crudo):
    """Filas con (ticker, fecha) repetido / filas totales de la descarga."""
    if crudo.empty:
        return 0.0
    return float(crudo.duplicated(subset=["ticker", "fecha"]).mean())


def campos_documentados(df):
    """Columnas del dataset con definición y unidad en el diccionario / columnas del dataset."""
    pct, faltantes = I.kpi_columnas_documentadas(df)
    return {"valor": pct, "faltantes": faltantes}


def frescura(ultima_fecha_datos, fecha_ejecucion=None):
    """Días calendario entre la última fecha con datos y la fecha de ejecución."""
    fecha_ejecucion = pd.Timestamp.today() if fecha_ejecucion is None else pd.Timestamp(fecha_ejecucion)
    return int((fecha_ejecucion.normalize() - pd.Timestamp(ultima_fecha_datos).normalize()).days)


def kpis_il3(crudo, validados, tabla_validacion, fecha_ejecucion=None):
    """Los cinco KPIs IL3 de una ejecución (todos MEDIDOS)."""
    cobertura = cobertura_fuentes(tabla_validacion)
    por_serie, total = completitud(crudo, validados)
    return {
        "cobertura": cobertura,
        "completitud": {"valor": total, "por_serie": por_serie},
        "duplicidad": {"valor": tasa_duplicidad(crudo)},
        "campos": campos_documentados(validados if len(validados) else crudo),
        "frescura": {"valor": frescura(crudo["fecha"].max(), fecha_ejecucion),
                     "ultima_fecha": pd.Timestamp(crudo["fecha"].max()).date()},
    }


def registrar_il3(k):
    """Escribe los KPIs IL3 en el log: una línea legible por KPI y una línea
    KPI_IL3 con todos los valores (para leerla después desde los logs)."""
    cob, com, dup, cam, fre = (k[c] for c in ("cobertura", "completitud", "duplicidad", "campos", "frescura"))
    log.info("KPI IL3 [%s] cobertura de fuentes: %d/%d series válidas (%.1f%%, meta ≥ %.0f%%)", MEDIDO,
             cob["validas"], cob["total"], 100 * cob["valor"], 100 * C.META_PCT_VALIDADAS)
    log.info("KPI IL3 [%s] completitud: %.3f%% de los días descargados son válidos (meta ≥ %.0f%%)", MEDIDO,
             100 * com["valor"], 100 * C.META_COMPLETITUD)
    for _, fila in com["por_serie"].iterrows():
        if fila["completitud"] < 1:
            log.info("    %s: %d de %d días válidos (%.2f%%)", fila["ticker"], fila["dias_validos"],
                     fila["dias_descargados"], 100 * fila["completitud"])
    log.info("KPI IL3 [%s] tasa de duplicidad: %.2f%% de filas (ticker, fecha) repetidas (meta %.0f%%)", MEDIDO,
             100 * dup["valor"], 100 * C.META_DUPLICIDAD)
    log.info("KPI IL3 [%s] campos documentados: %.0f%% de las columnas en el diccionario (meta %.0f%%)%s", MEDIDO,
             100 * cam["valor"], 100 * C.META_CAMPOS_DOCUMENTADOS,
             f"; sin documentar: {', '.join(cam['faltantes'])}" if cam["faltantes"] else "")
    log.info("KPI IL3 [%s] frescura: %d días desde el último dato (%s; meta ≤ %d días)", MEDIDO, fre["valor"],
             fre["ultima_fecha"], C.META_FRESCURA_DIAS)
    # Si la frescura supera la meta, src/monitoreo.py emite el WARNING (alerta de deriva)
    log.info("KPI_IL3 cobertura=%.4f completitud=%.4f duplicidad=%.4f campos=%.4f frescura_dias=%d",
             cob["valor"], com["valor"], dup["valor"], cam["valor"], fre["valor"])


# --- IL4: operación -----------------------------------------------------------------

def leer_ejecuciones(dir_logs=C.DIR_LOGS):
    """Ejecuciones de main.py según las líneas RESUMEN_EJECUCION de los logs.

    Las corridas registradas antes de incorporar el campo origen quedan como
    "no_registrado" (incluyen corridas manuales y de pruebas)."""
    filas = []
    for ruta in sorted(dir_logs.glob("radar_*.log")):
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "RESUMEN_EJECUCION" in linea:
                filas.append({"registrado": linea[:19], **dict(re.findall(r"(\w+)=(\S+)", linea))})
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    for col in ("origen", "fin_utc", "filas"):
        if col not in df.columns:
            df[col] = None
    df["origen"] = df["origen"].fillna("no_registrado")
    df["duracion_s"] = df["duracion_s"].astype(float)
    return df


def reporte_a_tiempo(fin_utc):
    """True si la corrida terminó antes del lunes a las 08:00 en Chile: el
    domingo o el lunes antes de esa hora (la corrida programada parte el
    domingo en la noche, hora de Chile)."""
    local = pd.Timestamp(fin_utc).tz_convert(C.ZONA_HORARIA_COMITE)
    return local.weekday() == 6 or (local.weekday() == 0 and local.hour < C.SLA_HORA_LIMITE_LUNES)


def revisiones_registradas(directorio=C.DIR_OUTPUTS):
    """Filas escritas en la hoja "Registro de revisión" de todos los reportes."""
    from src import reporte as R

    filas = [(ruta.name, *fila) for ruta in sorted(directorio.glob("reporte_radar_*.xlsx"))
             for fila in R.leer_registro(ruta)]
    return pd.DataFrame(filas, columns=["reporte", *R.COLUMNAS_REGISTRO])


def kpis_il4(ejecuciones=None, revisiones=None):
    """KPIs IL4. La tasa de éxito y la duración se MIDEN con los logs; el SLA
    queda DEFINIDO mientras no existan corridas programadas y la frecuencia de
    uso queda DEFINIDA mientras nadie anote revisiones en los reportes."""
    ejecuciones = leer_ejecuciones() if ejecuciones is None else ejecuciones
    revisiones = revisiones_registradas() if revisiones is None else revisiones
    k = {}
    if ejecuciones.empty:
        k["exito"] = {"etiqueta": DEFINIDO, "valor": None, "texto": "sin ejecuciones registradas"}
        k["duracion"] = {"etiqueta": DEFINIDO, "valor": None, "texto": "sin ejecuciones registradas"}
    else:
        ok = ejecuciones["estado"] == "OK"
        por_origen = ", ".join(f"{o} {g['estado'].eq('OK').sum()}/{len(g)}"
                               for o, g in ejecuciones.groupby("origen"))
        k["exito"] = {"etiqueta": MEDIDO, "valor": ok.mean(), "ok": int(ok.sum()), "total": len(ok),
                      "tasa_fallos": 1 - ok.mean(), "por_origen": por_origen}
        d = ejecuciones["duracion_s"]
        k["duracion"] = {"etiqueta": MEDIDO, "valor": d.max(), "promedio": d.mean(),
                         "max_normal": d[ejecuciones["modo"] == "normal"].max()}

    programadas = ejecuciones[ejecuciones["origen"] == "programada"] if not ejecuciones.empty else ejecuciones
    if programadas.empty:
        k["sla"] = {"etiqueta": DEFINIDO, "valor": None, "texto": "sin corridas programadas todavía"}
    else:
        a_tiempo = (programadas["estado"] == "OK") & programadas["fin_utc"].map(reporte_a_tiempo)
        k["sla"] = {"etiqueta": MEDIDO, "valor": a_tiempo.mean(), "a_tiempo": int(a_tiempo.sum()),
                    "total": len(programadas)}

    if revisiones.empty:
        k["uso"] = {"etiqueta": DEFINIDO, "valor": None,
                    "texto": "0 revisiones registradas (usuario hipotético: aún no hay comité real)"}
    else:
        semanas = pd.to_datetime(revisiones["Fecha de la reunión"], errors="coerce").dt.to_period("W")
        k["uso"] = {"etiqueta": MEDIDO, "valor": len(revisiones) / max(semanas.nunique(), 1),
                    "total": len(revisiones), "semanas": int(semanas.nunique())}
    return k


def registrar_il4(k):
    """Escribe los KPIs IL4 en el log, con su etiqueta."""
    e, d, s, u = k["exito"], k["duracion"], k["sla"], k["uso"]
    if e["valor"] is None:
        log.info("KPI IL4 [%s] corridas sin error: %s", e["etiqueta"], e["texto"])
    else:
        log.info("KPI IL4 [%s] corridas sin error: %d/%d (%.1f%%; tasa de fallos %.1f%%, meta < %.0f%%); por "
                 "origen: %s", e["etiqueta"], e["ok"], e["total"], 100 * e["valor"], 100 * e["tasa_fallos"],
                 100 * C.META_TASA_FALLOS, e["por_origen"])
        log.info("KPI IL4 [%s] duración: máxima %.1f s, promedio %.1f s (meta < %d s)", d["etiqueta"],
                 d["valor"], d["promedio"], C.META_DURACION_S)
    if s["valor"] is None:
        log.info("KPI IL4 [%s] SLA (reporte antes del lunes %02d:00 en Chile): %s", s["etiqueta"],
                 C.SLA_HORA_LIMITE_LUNES, s["texto"])
    else:
        log.info("KPI IL4 [%s] SLA (reporte antes del lunes %02d:00 en Chile): %d/%d corridas programadas "
                 "(%.0f%%, meta ≥ %.0f%%)", s["etiqueta"], C.SLA_HORA_LIMITE_LUNES, s["a_tiempo"], s["total"],
                 100 * s["valor"], 100 * C.META_SLA)
    if u["valor"] is None:
        log.info("KPI IL4 [%s] frecuencia de uso: %s", u["etiqueta"], u["texto"])
    else:
        log.info("KPI IL4 [%s] frecuencia de uso: %.1f revisiones por semana (%d en %d semanas; meta ≥ %d)",
                 u["etiqueta"], u["valor"], u["total"], u["semanas"], C.META_REVISIONES_SEMANA)


# --- IL5: impacto en lenguaje de negocio ------------------------------------------

RUTA_EPISODIOS = C.DIR_OUTPUTS / "resumen_episodios_v1_v2.csv"


def perdida_evitada(exposicion=C.EXPOSICION_USD, episodios=C.EPISODIOS_PERDIDA_EVITADA, ruta=RUTA_EPISODIOS):
    """PROYECTADO: pérdida evitada por la regla v2 en cada episodio, en US$.

    (caída máxima de mantener − caída máxima de la v2) × exposición, con las
    caídas como magnitudes: cuántos puntos porcentuales menos cayó la cartera
    con la v2, aplicados a una exposición de `exposicion` US$ (SUPUESTO). Las
    caídas y percentiles salen de la tabla de episodios del notebook 06b
    (cifras auditadas, con el placebo corregido)."""
    ep = pd.read_csv(ruta, encoding="utf-8-sig").set_index("episodio").loc[list(episodios)]
    tabla = pd.DataFrame({
        "muestra": ep["muestra"].map({"Dentro": "dentro de muestra", "Fuera": "fuera de muestra"}),
        "anticipacion_rojo_semanas": ep["anticipación del rojo (sem.)"],
        "caida_mantener": ep["caída máx. mantener"].astype(float),
        "caida_v2": ep["caída máx. v2"].astype(float),
    })
    tabla["puntos_evitados"] = tabla["caida_v2"] - tabla["caida_mantener"]      # > 0: la v2 cae menos
    tabla["perdida_evitada_usd"] = tabla["puntos_evitados"] * exposicion
    tabla["percentil_placebo_v2"] = ep["percentil placebo v2"].astype(float)
    tabla["supera_al_azar"] = tabla["percentil_placebo_v2"] < 20                 # criterio (b) fijado antes
    tabla["etiqueta"] = PROYECTADO
    return tabla


def episodios_rojos(panel, tickers):
    """Inicio de cada episodio rojo (semáforo con persistencia) de los tickers."""
    p = panel[panel["ticker"].isin(tickers)].dropna(subset=["semaforo"]).sort_values(["ticker", "fecha"])
    rojo = p["semaforo"].eq("rojo")
    inicio = rojo & ~rojo.groupby(p["ticker"]).shift(fill_value=False)
    return p.loc[inicio, ["ticker", "fecha"]].reset_index(drop=True)


def decisiones_habilitadas(panel, grupos=None):
    """MEDIDO en el historial: episodios rojos por año, es decir, cuántas veces
    al año el comité habría tenido que discutir reducir o cubrir exposición.

    Devuelve (resumen por grupo, tabla de episodios por año calendario). Los
    años se cuentan desde la primera semana con semáforo del grupo."""
    grupos = grupos or {"Universo (9 acciones)": list(C.UNIVERSO), "Nasdaq (^IXIC)": ["^IXIC"]}
    resumen, por_ano = [], {}
    for nombre, tickers in grupos.items():
        con_senal = panel[panel["ticker"].isin(tickers)].dropna(subset=["semaforo"])
        inicio, fin = con_senal["fecha"].min(), con_senal["fecha"].max()
        rojos = episodios_rojos(panel, tickers)
        anos = (fin - inicio).days / 365.25
        conteo = rojos.groupby(rojos["fecha"].dt.year).size().reindex(range(inicio.year, fin.year + 1), fill_value=0)
        por_ano[nombre] = conteo
        resumen.append({"grupo": nombre, "desde": inicio.date(), "hasta": fin.date(), "anos": anos,
                        "episodios_rojos": len(rojos), "por_ano": len(rojos) / anos, "max_en_un_ano": conteo.max(),
                        "anos_sin_rojo": int((conteo == 0).sum()), "etiqueta": MEDIDO})
    return pd.DataFrame(resumen), pd.DataFrame(por_ano)


def eficiencia_operativa(ejecuciones=None, horas_semana=C.HORAS_ANALISIS_SEMANA):
    """PROYECTADO: horas anuales de análisis manual reemplazadas (SUPUESTO
    horas_semana × 52) frente al tiempo real de main.py (duración máxima de
    las corridas con descarga, MEDIDA en los logs, × 52)."""
    ejecuciones = leer_ejecuciones() if ejecuciones is None else ejecuciones
    con_descarga = ejecuciones.loc[ejecuciones["modo"] == "normal", "duracion_s"]
    duracion = con_descarga.max() if len(con_descarga) else ejecuciones["duracion_s"].max()
    horas_manual = horas_semana * C.SEMANAS_POR_ANO
    horas_radar = duracion * C.SEMANAS_POR_ANO / 3600
    return {"horas_manual_ano": horas_manual, "duracion_corrida_s": duracion, "horas_radar_ano": horas_radar,
            "horas_liberadas_ano": horas_manual - horas_radar, "etiqueta": PROYECTADO}
