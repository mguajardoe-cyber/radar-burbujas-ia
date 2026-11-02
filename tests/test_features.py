# =============================================================================
# Pruebas — Capa 3: semáforo con persistencia (src/features.py)
#
# Propósito: verificar que con persistencia de 6 semanas una semana aislada no
#   cambia el color, y que el color sí cambia tras 6 semanas seguidas.
# Entradas: secuencias de colores sintéticas.
# Salidas: resultado de pytest.
# =============================================================================

from src import features as F


def test_una_semana_aislada_no_cambia_el_color():
    # En verde, una semana roja aislada no enciende el rojo
    bruto = ["verde"] * 10 + ["rojo"] + ["verde"] * 10
    assert set(F.aplicar_persistencia(bruto, 6)) == {"verde"}

    # En rojo, una semana verde aislada no lo apaga
    bruto = ["rojo"] * 8 + ["verde"] + ["rojo"] * 8
    salida = F.aplicar_persistencia(bruto, 6)
    assert list(salida[5:]) == ["rojo"] * (len(bruto) - 5)


def test_cambia_de_color_tras_6_semanas_seguidas():
    bruto = ["verde"] * 3 + ["rojo"] * 6
    salida = F.aplicar_persistencia(bruto, 6)
    assert list(salida[:-1]) == ["verde"] * 8   # con 5 semanas rojas todavía no cambia
    assert salida[-1] == "rojo"                 # la sexta semana roja enciende el rojo


def test_mezcla_de_amarillo_y_rojo_sube_al_menor_nivel():
    # 6 semanas sobre el umbral amarillo (algunas en rojo) → amarillo
    bruto = ["verde"] * 2 + ["rojo", "amarillo"] * 3
    assert F.aplicar_persistencia(bruto, 6)[-1] == "amarillo"
