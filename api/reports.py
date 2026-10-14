"""
Generacion de reportes (OB2: componente "Generacion de reportes"; E6).

Resumen DESCRIPTIVO del uso de la aplicacion. No realiza evaluaciones ni
interpretaciones clinicas.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")
MIN_REGISTROS_FRECUENCIAS = 3  # HU031, criterio 2
AVISO = "Resumen descriptivo de uso. No constituye una evaluación clínica."


def local_day(dt: datetime) -> date:
    return dt.astimezone(LIMA).date()


def build_report(
    interacciones: list[dict], *, today: date | None = None
) -> dict:
    """Construye el resumen de un conjunto de interacciones ya filtrado."""
    today = today or datetime.now(LIMA).date()
    semana = [today - timedelta(days=6 - i) for i in range(7)]
    por_dia_semana = Counter()
    por_dia = Counter()
    frecuencias = Counter()
    intenciones = set()
    gestos = 0

    for it in interacciones:
        dia = local_day(it["fecha_hora"])
        por_dia[dia.isoformat()] += 1
        if dia in semana:
            por_dia_semana[dia] += 1
        frecuencias[it["id_pictograma"]] += 1
        if it.get("id_gesto"):
            gestos += 1
        if it.get("id_intencion"):
            intenciones.add(it["id_intencion"])

    total = len(interacciones)
    suficientes = total >= MIN_REGISTROS_FRECUENCIAS
    return {
        "total_interacciones": total,
        "interacciones_por_gesto": gestos,
        "interacciones_por_pictograma": total - gestos,
        "intenciones_distintas": len(intenciones),
        "actividad_semanal": [
            {"fecha": d.isoformat(), "cantidad": por_dia_semana[d]} for d in semana
        ],
        "por_dia": [
            {"fecha": k, "cantidad": v} for k, v in sorted(por_dia.items())
        ],
        "datos_suficientes_para_frecuencias": suficientes,
        "mas_frecuentes": [
            {"id_pictograma": pid, "cantidad": n}
            for pid, n in frecuencias.most_common(8)
        ]
        if suficientes
        else [],
        "aviso": AVISO,
    }
