# =============================================================================
# Capa 4 — Salidas: reporte Excel semanal para el comité de inversiones
#
# Propósito:
#   Generar outputs/reporte_radar_AAAA-MM-DD.xlsx (fecha = cierre semanal de
#   los datos) con cuatro hojas:
#     - Semáforo: color por ticker, semanas en el color, BSADF y umbrales.
#     - Variables: momentum, volatilidad, beta y perfil de riesgo (K-Means,
#       src/perfiles.py), con una explicación en palabras simples de por qué
#       cada ticker está en su color.
#     - Gráficos: evolución del BSADF de los tickers en amarillo o rojo frente
#       a los umbrales (gráfico nativo de Excel).
#     - Registro de revisión: tabla en blanco donde el operador anota fecha,
#       revisor y decisión del comité (KPI IL4 de frecuencia de uso). Si el
#       reporte de la semana se regenera, se conservan las filas escritas.
#   Cada hoja lleva un encabezado con la fecha de los datos; la hoja Semáforo
#   incluye además una nota de interpretación.
#
# Entradas:
#   - Panel semanal y semáforo actual (src/features.py).
#
# Salidas:
#   - outputs/reporte_radar_AAAA-MM-DD.xlsx
# =============================================================================

import logging

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src import config as C

log = logging.getLogger("radar.reporte")

COLOR_CELDA = {"verde": "0CA30C", "amarillo": "FAB219", "rojo": "D03B3B"}
COLOR_TEXTO = {"verde": "FFFFFF", "amarillo": "0B0B0B", "rojo": "FFFFFF"}
SEMANAS_GRAFICO = 156          # 3 años de historia en la hoja Gráficos
FILA_TABLA = 6                 # fila donde empieza cada tabla (bajo el encabezado)

NOTA_INTERPRETACION = (
    "Cómo leer el semáforo: el test BSADF busca, en los últimos 5 años de cada acción, el tramo con el "
    "crecimiento más explosivo (un precio que sube porque ya subió). ROJO = evidencia fuerte de burbuja "
    "(supera el valor crítico al 95%): revisar reducir o cubrir la exposición. AMARILLO = señal temprana "
    "(supera el 90%): monitorear. VERDE = sin evidencia. Un color cambia solo si la señal se mantiene 6 "
    "semanas seguidas. El test detecta crecimiento explosivo, no predice la fecha de una caída."
)

HOJA_REGISTRO = "Registro de revisión"
COLUMNAS_REGISTRO = ["Fecha de la reunión", "Revisor", "Decisión tomada", "Comentarios"]
NOTA_REGISTRO = (
    "Para el operador: después de cada reunión, anote una fila por revisión del reporte (fecha, quién lo "
    "revisó y la decisión tomada, por ejemplo \"mantener\", \"reducir TSM a 50%\" o \"sin cambios\"). "
    "Estas filas alimentan el KPI de frecuencia de uso (scripts/contar_revisiones.py). Si el reporte de "
    "la semana se regenera, las filas escritas se conservan."
)


def nombre(ticker):
    return {**C.UNIVERSO, **C.INDICES}.get(ticker, ticker)


def _num(valor, decimales=2):
    """Número con coma decimal, para los textos en español."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def explicar(fila):
    """Explicación en palabras simples de por qué un ticker está en su color."""
    b, am, ro = fila["bsadf"], fila["cv_bsadf_90"], fila["cv_bsadf_95"]
    color, bruto, n = fila["semaforo"], fila["semaforo_bruto"], int(fila["semanas_en_estado"])
    semanas = f"{n} semana{'s' if n != 1 else ''}"
    p = C.PERSISTENCIA_SEMANAS
    if color == "rojo":
        texto = (f"Crecimiento explosivo: lleva {semanas} en rojo (entró al superar el umbral rojo de "
                 f"{_num(ro)} durante {p} semanas seguidas).")
    elif color == "amarillo":
        texto = (f"Señal temprana: lleva {semanas} en amarillo (entró al superar el umbral amarillo de "
                 f"{_num(am)} durante {p} semanas seguidas).")
    else:
        texto = f"Sin evidencia de burbuja: lleva {semanas} en verde."
    if bruto != color:
        texto += (f" Esta semana el BSADF es {_num(b)} (nivel {bruto}); el color cambia solo si ese nivel se "
                  f"mantiene {p} semanas seguidas.")
    else:
        texto += f" BSADF esta semana: {_num(b)}."

    contexto = []
    if fila["momentum_52s"] > 0.5:
        contexto.append(f"subió {fila['momentum_52s']:.0%} en 12 meses")
    elif fila["momentum_52s"] < -0.2:
        contexto.append(f"cayó {-fila['momentum_52s']:.0%} en 12 meses")
    if fila["volatilidad_anual"] > 0.45:
        contexto.append(f"volatilidad alta ({fila['volatilidad_anual']:.0%} anual)")
    if fila["beta_104s"] > 1.5:
        contexto.append(f"muy sensible al mercado (beta {_num(fila['beta_104s'], 1)})")
    if contexto:
        texto += " Contexto: " + "; ".join(contexto) + "."
    return texto


def _encabezado(hoja, titulo, fecha_datos, nota=None):
    hoja["A1"] = titulo
    hoja["A1"].font = Font(size=14, bold=True)
    hoja["A2"] = f"Datos al cierre del viernes {fecha_datos:%d-%m-%Y} · Fuente: {C.FUENTE}"
    hoja["A2"].font = Font(italic=True, color="52514E")
    if nota:
        hoja["A3"] = nota
        hoja.merge_cells("A3:H4")
        hoja["A3"].alignment = Alignment(wrap_text=True, vertical="top")
        hoja.row_dimensions[3].height = 45
        hoja.row_dimensions[4].height = 45


def _tabla(hoja, df, formatos=None, anchos=None):
    """Escribe un DataFrame desde FILA_TABLA con encabezados en negrita."""
    for j, col in enumerate(df.columns, start=1):
        celda = hoja.cell(row=FILA_TABLA, column=j, value=col)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="52514E")
        celda.alignment = Alignment(wrap_text=True, vertical="center")
    for i, fila in enumerate(df.itertuples(index=False), start=FILA_TABLA + 1):
        for j, valor in enumerate(fila, start=1):
            celda = hoja.cell(row=i, column=j, value=valor)
            if formatos and df.columns[j - 1] in formatos:
                celda.number_format = formatos[df.columns[j - 1]]
    for j, ancho in enumerate(anchos or [], start=1):
        hoja.column_dimensions[get_column_letter(j)].width = ancho


def _colorear(hoja, columna, n_filas):
    for i in range(FILA_TABLA + 1, FILA_TABLA + 1 + n_filas):
        celda = hoja.cell(row=i, column=columna)
        color = celda.value
        celda.fill = PatternFill("solid", fgColor=COLOR_CELDA[color])
        celda.font = Font(bold=True, color=COLOR_TEXTO[color])
        celda.value = color.upper()


def hoja_semaforo(libro, actual, fecha_datos):
    hoja = libro.active
    hoja.title = "Semáforo"
    _encabezado(hoja, "Radar de Burbujas IA — Semáforo semanal", fecha_datos, NOTA_INTERPRETACION)
    df = pd.DataFrame({
        "Ticker": actual["ticker"], "Nombre": actual["ticker"].map(nombre), "Color": actual["semaforo"],
        "Semanas en el color": actual["semanas_en_estado"].astype(int),
        "BSADF esta semana": actual["bsadf"], "Umbral amarillo (cv 90%)": actual["cv_bsadf_90"],
        "Umbral rojo (cv 95%)": actual["cv_bsadf_95"], "Señal bruta de la semana": actual["semaforo_bruto"],
    })
    _tabla(hoja, df, {c: "0.00" for c in ["BSADF esta semana", "Umbral amarillo (cv 90%)", "Umbral rojo (cv 95%)"]},
           [10, 26, 12, 12, 12, 14, 14, 14])
    _colorear(hoja, 3, len(df))
    hoja.freeze_panes = hoja.cell(row=FILA_TABLA + 1, column=1)


def hoja_variables(libro, actual, fecha_datos):
    hoja = libro.create_sheet("Variables")
    _encabezado(hoja, "Variables de riesgo y explicación del color", fecha_datos)
    df = pd.DataFrame({
        "Ticker": actual["ticker"], "Nombre": actual["ticker"].map(nombre), "Color": actual["semaforo"],
        "Momentum 12 meses": actual["momentum_52s"], "Volatilidad anual": actual["volatilidad_anual"],
        "Beta (2 años vs. S&P 500)": actual["beta_104s"],
        "Perfil de riesgo": actual["perfil_riesgo"] if "perfil_riesgo" in actual else "sin perfil",
        "Por qué está en este color": actual.apply(explicar, axis=1),
    })
    _tabla(hoja, df, {"Momentum 12 meses": "0.0%", "Volatilidad anual": "0.0%", "Beta (2 años vs. S&P 500)": "0.00"},
           [10, 26, 12, 12, 12, 12, 22, 90])
    _colorear(hoja, 3, len(df))
    for i in range(FILA_TABLA + 1, FILA_TABLA + 1 + len(df)):
        hoja.cell(row=i, column=7).alignment = Alignment(wrap_text=True, vertical="top")
        hoja.cell(row=i, column=8).alignment = Alignment(wrap_text=True, vertical="top")
        hoja.row_dimensions[i].height = 48


def hoja_graficos(libro, panel, actual, fecha_datos):
    hoja = libro.create_sheet("Gráficos")
    alerta = actual.loc[actual["semaforo"] != "verde", "ticker"].tolist()
    if alerta:
        titulo = "Evolución del BSADF de los tickers en amarillo o rojo"
        seleccion = alerta
    else:
        titulo = "Ningún ticker en amarillo o rojo: se muestran los 3 con mayor BSADF"
        seleccion = actual.nlargest(3, "bsadf")["ticker"].tolist()
    _encabezado(hoja, titulo, fecha_datos)

    datos = (panel[panel["ticker"].isin(seleccion)]
             .pivot(index="fecha", columns="ticker", values="bsadf")[seleccion]
             .tail(SEMANAS_GRAFICO))
    datos["Umbral amarillo"] = actual["cv_bsadf_90"].iloc[0]
    datos["Umbral rojo"] = actual["cv_bsadf_95"].iloc[0]
    tabla = datos.reset_index().rename(columns={"fecha": "Semana"})
    tabla["Semana"] = tabla["Semana"].dt.date
    _tabla(hoja, tabla, {c: "0.00" for c in tabla.columns[1:]} | {"Semana": "dd-mm-yyyy"},
           [12] + [10] * (len(tabla.columns) - 1))

    grafico = LineChart()
    grafico.title = "BSADF semanal vs. umbrales (últimos 3 años)"
    grafico.y_axis.title = "BSADF"
    grafico.x_axis.number_format = "mm-yyyy"
    grafico.height, grafico.width = 10, 24
    ultima = FILA_TABLA + len(tabla)
    grafico.add_data(Reference(hoja, min_col=2, max_col=len(tabla.columns), min_row=FILA_TABLA, max_row=ultima),
                     titles_from_data=True)
    grafico.set_categories(Reference(hoja, min_col=1, min_row=FILA_TABLA + 1, max_row=ultima))
    for serie in grafico.series:
        serie.smooth = False
        serie.graphicalProperties.line.width = 20000
    grafico.series[-2].graphicalProperties.line.solidFill = "C98500"
    grafico.series[-2].graphicalProperties.line.dashStyle = "dash"
    grafico.series[-1].graphicalProperties.line.solidFill = "D03B3B"
    grafico.series[-1].graphicalProperties.line.dashStyle = "dash"
    hoja.add_chart(grafico, f"{get_column_letter(len(tabla.columns) + 2)}{FILA_TABLA}")


def leer_registro(ruta):
    """Filas escritas a mano en la hoja "Registro de revisión" de un reporte
    (fecha, revisor, decisión, comentarios). Devuelve una lista de tuplas; vacía
    si el archivo o la hoja no existen."""
    if not ruta.exists():
        return []
    libro = load_workbook(ruta, read_only=True)
    if HOJA_REGISTRO not in libro.sheetnames:
        return []
    filas = [tuple(fila[:len(COLUMNAS_REGISTRO)])
             for fila in libro[HOJA_REGISTRO].iter_rows(min_row=FILA_TABLA + 1, values_only=True)
             if any(v not in (None, "") for v in fila[:len(COLUMNAS_REGISTRO)])]
    libro.close()
    return filas


def hoja_registro(libro, fecha_datos, previas=()):
    """Hoja en blanco donde el operador anota cada revisión del comité. Si el
    reporte de la semana se regenera, se conservan las filas ya escritas."""
    hoja = libro.create_sheet(HOJA_REGISTRO)
    _encabezado(hoja, "Registro de revisión del comité", fecha_datos, NOTA_REGISTRO)
    _tabla(hoja, pd.DataFrame(list(previas), columns=COLUMNAS_REGISTRO), {"Fecha de la reunión": "dd-mm-yyyy"},
           [18, 22, 40, 50])


def generar_reporte(panel, actual, directorio=C.DIR_OUTPUTS):
    """Genera el Excel semanal y devuelve su ruta."""
    fecha_datos = pd.Timestamp(actual["fecha"].max())
    ruta = directorio / f"reporte_radar_{fecha_datos:%Y-%m-%d}.xlsx"
    previas = leer_registro(ruta)
    if previas:
        log.info("Se conservan %d filas del Registro de revisión de %s", len(previas), ruta.name)
    libro = Workbook()
    hoja_semaforo(libro, actual, fecha_datos)
    hoja_variables(libro, actual, fecha_datos)
    hoja_graficos(libro, panel, actual, fecha_datos)
    hoja_registro(libro, fecha_datos, previas)
    libro.save(ruta)
    log.info("Reporte generado: %s", ruta.name)
    return ruta
