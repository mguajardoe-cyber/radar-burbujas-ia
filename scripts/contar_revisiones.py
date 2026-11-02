# =============================================================================
# Capa 7 — KPIs: frecuencia de uso (IL4)
#
# Propósito: contar las revisiones del reporte que el operador anotó en la hoja
#   "Registro de revisión" de cada Excel semanal y calcular las revisiones por
#   semana. Mientras no haya filas, el KPI queda DEFINIDO (hoy no hay un comité
#   real: el usuario es hipotético).
# Entradas: outputs/reporte_radar_*.xlsx.
# Salidas: tabla por consola (total, semanas con revisión, revisiones por semana).
#
# Uso: python scripts/contar_revisiones.py
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import kpis as K


def main():
    revisiones = K.revisiones_registradas()
    uso = K.kpis_il4(revisiones=revisiones)["uso"]
    print(f"Reportes revisados: {revisiones['reporte'].nunique()} · revisiones anotadas: {len(revisiones)}")
    if uso["valor"] is None:
        print(f"KPI frecuencia de uso [{uso['etiqueta']}]: {uso['texto']}")
    else:
        print(revisiones.to_string(index=False))
        print(f"KPI frecuencia de uso [{uso['etiqueta']}]: {uso['valor']:.1f} revisiones por semana "
              f"({uso['total']} en {uso['semanas']} semanas)")


if __name__ == "__main__":
    main()
