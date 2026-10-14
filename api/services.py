"""
Logica de negocio del backend de GestuVoz.

Reglas:
- RF-12: un tutor solo accede a sus propios perfiles. Si el perfil es de otro
  tutor se responde "no encontrado" (no se revela que existe).
- Consentimiento (OB2 9.1, Ley N.º 29733): sin consentimiento vigente no se
  sincronizan datos del perfil. La decision de consentimiento siempre se
  puede registrar.
- Gana el ultimo cambio: se rechaza una version mas antigua que la guardada.
- Interacciones: se crean una sola vez (reenvios sin conexion no duplican).
- HU025: eliminar un perfil borra sus datos en la nube.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from rest_framework.exceptions import ValidationError

from . import reports
from .errors import ConsentRequired, NotFound, StaleWrite
from .store import DocumentStore, Filter

# Colecciones de Cloud Firestore (OB2, Figura 7) + `ninos`.
PERFILES = "perfiles"
NINOS = "ninos"
PICTOGRAMAS = "pictogramas"
INTENCIONES = "intenciones_comunicativas"
VOZ = "configuraciones_voz"
CONSENTIMIENTOS = "consentimientos"
INTERACCIONES = "interacciones"

TS = "actualizado_en"


def _out(value: Any) -> Any:
    """Convierte fechas a texto ISO para la respuesta JSON."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _out(v) for k, v in value.items() if k != "id_tutor"}
    if isinstance(value, list):
        return [_out(v) for v in value]
    return value


class GestuVozService:
    def __init__(self, store: DocumentStore, tutor_uid: str):
        self.store = store
        self.uid = tutor_uid

    # ------------------------------------------------------------------
    # Pertenencia y consentimiento
    # ------------------------------------------------------------------
    def _owned_profile(self, id_perfil: str) -> dict | None:
        """Devuelve el perfil si es del tutor; None si aun no existe.

        Lanza NotFound si el perfil (o su consentimiento) es de otro tutor.
        """
        perfil = self.store.get(PERFILES, id_perfil)
        if perfil is not None:
            if perfil.get("id_tutor") != self.uid:
                raise NotFound()
            return perfil
        consent = self.store.get(CONSENTIMIENTOS, id_perfil)
        if consent is not None and consent.get("id_tutor") != self.uid:
            raise NotFound()
        return None

    def _existing_profile(self, id_perfil: str) -> dict:
        perfil = self._owned_profile(id_perfil)
        if perfil is None:
            raise NotFound("El perfil no existe.")
        return perfil

    def _require_consent(self, id_perfil: str) -> None:
        self._owned_profile(id_perfil)
        consent = self.store.get(CONSENTIMIENTOS, id_perfil)
        if consent is None or consent.get("estado_consentimiento") != "otorgado":
            raise ConsentRequired()

    def _put(self, collection: str, doc_id: str, data: dict, current_view) -> dict:
        result = self.store.put_if_newer(collection, doc_id, data, TS)
        if not result.applied:
            raise StaleWrite(current_view(result.current))
        return result.current

    # ------------------------------------------------------------------
    # Perfiles + ninos (HU021-HU025)
    # ------------------------------------------------------------------
    def _profile_view(self, perfil: dict) -> dict:
        nino = self.store.get(NINOS, perfil["id_nino"]) if perfil.get("id_nino") else None
        view = _out(perfil)
        view["nino"] = _out(nino) if nino else None
        return view

    def list_profiles(self) -> list[dict]:
        perfiles = self.store.query(PERFILES, [Filter("id_tutor", "==", self.uid)])
        perfiles.sort(key=lambda p: p[TS])
        return [self._profile_view(p) for p in perfiles]

    def get_profile(self, id_perfil: str) -> dict:
        return self._profile_view(self._existing_profile(id_perfil))

    def put_profile(self, id_perfil: str, data: dict) -> dict:
        existing = self._owned_profile(id_perfil)
        self._require_consent(id_perfil)
        nino_in = data["nino"]
        id_nino = nino_in["id_nino"]
        if existing is not None and existing.get("id_nino") != id_nino:
            raise ValidationError({"nino": "Un perfil corresponde a un único niño."})
        nino_stored = self.store.get(NINOS, id_nino)
        if nino_stored is not None and nino_stored.get("id_tutor") != self.uid:
            raise NotFound()

        perfil_doc = {
            "id_perfil": id_perfil,
            "nivel_apoyo": data.get("nivel_apoyo") or None,
            "preferencias_de_comunicacion": data["preferencias_de_comunicacion"],
            "estado_perfil": data["estado_perfil"],
            "id_nino": id_nino,
            "id_tutor": self.uid,
            TS: data[TS],
        }
        self._put(PERFILES, id_perfil, perfil_doc, self._profile_view)
        nino_doc = {
            "id_nino": id_nino,
            "nombre": nino_in["nombre"],
            "fecha_nacimiento": nino_in["fecha_nacimiento"].isoformat(),
            "genero": nino_in.get("genero") or None,
            "id_tutor": self.uid,
            TS: data[TS],
        }
        self.store.put_if_newer(NINOS, id_nino, nino_doc, TS)
        return self.get_profile(id_perfil)

    def delete_profile(self, id_perfil: str) -> None:
        """HU025: elimina el perfil y los datos que le pertenecen."""
        perfil = self._owned_profile(id_perfil)
        consent = self.store.get(CONSENTIMIENTOS, id_perfil)
        if perfil is None and consent is None:
            raise NotFound("El perfil no existe.")
        refs: list[tuple[str, str]] = [
            (INTERACCIONES, it["id_interaccion"])
            for it in self.store.query(
                INTERACCIONES, [Filter("id_perfil", "==", id_perfil)]
            )
        ]
        refs += [(VOZ, id_perfil), (CONSENTIMIENTOS, id_perfil)]
        if perfil is not None:
            if perfil.get("id_nino"):
                refs.append((NINOS, perfil["id_nino"]))
            refs.append((PERFILES, id_perfil))
        self.store.delete_many(refs)

    # ------------------------------------------------------------------
    # Consentimiento (HU027, HU028)
    # ------------------------------------------------------------------
    def get_consent(self, id_perfil: str) -> dict:
        self._owned_profile(id_perfil)
        consent = self.store.get(CONSENTIMIENTOS, id_perfil)
        if consent is None:
            raise NotFound("El perfil aún no tiene una decisión de consentimiento.")
        return _out(consent)

    def put_consent(self, id_perfil: str, data: dict) -> dict:
        self._owned_profile(id_perfil)
        doc = {
            "id_consentimiento": id_perfil,
            "estado_consentimiento": data["estado_consentimiento"],
            "fecha_registro": data["fecha_registro"],
            "fecha_retiro": data.get("fecha_retiro"),
            "id_perfil": id_perfil,
            "id_tutor": self.uid,
            TS: data[TS],
        }
        return _out(self._put(CONSENTIMIENTOS, id_perfil, doc, _out))

    # ------------------------------------------------------------------
    # Configuracion de voz (HU017)
    # ------------------------------------------------------------------
    def get_voice(self, id_perfil: str) -> dict:
        self._existing_profile(id_perfil)
        voz = self.store.get(VOZ, id_perfil)
        if voz is None:
            raise NotFound("El perfil aún no tiene configuración de voz.")
        return _out(voz)

    def put_voice(self, id_perfil: str, data: dict) -> dict:
        self._existing_profile(id_perfil)
        self._require_consent(id_perfil)
        doc = {
            "id_configuracion_voz": id_perfil,
            "idioma": data["idioma"],
            "tipo_voz": data.get("tipo_voz") or None,
            "velocidad": data["velocidad"],
            "volumen": data["volumen"],
            "voz_activada": data["voz_activada"],
            "id_perfil": id_perfil,
            TS: data[TS],
        }
        return _out(self._put(VOZ, id_perfil, doc, _out))

    # ------------------------------------------------------------------
    # Pictogramas personalizados (HU012-HU014)
    # ------------------------------------------------------------------
    def list_pictograms(self) -> list[dict]:
        docs = self.store.query(PICTOGRAMAS, [Filter("id_tutor", "==", self.uid)])
        docs.sort(key=lambda d: d[TS])
        return _out(docs)

    def put_pictogram(self, id_pictograma: str, id_perfil: str, data: dict) -> dict:
        self._existing_profile(id_perfil)
        self._require_consent(id_perfil)
        stored = self.store.get(PICTOGRAMAS, id_pictograma)
        if stored is not None and stored.get("id_tutor") != self.uid:
            raise NotFound()
        doc = {
            "id_pictograma": id_pictograma,
            "nombre": data["nombre"],
            "mensaje": data["mensaje"],
            "id_categoria": data["id_categoria"],
            "referencia_imagen": data.get("referencia_imagen") or None,
            "id_tutor": self.uid,
            TS: data[TS],
        }
        return _out(self._put(PICTOGRAMAS, id_pictograma, doc, _out))

    def delete_pictogram(self, id_pictograma: str) -> None:
        stored = self.store.get(PICTOGRAMAS, id_pictograma)
        if stored is None or stored.get("id_tutor") != self.uid:
            raise NotFound()
        self.store.delete_many([(PICTOGRAMAS, id_pictograma)])

    # ------------------------------------------------------------------
    # Intenciones comunicativas (catalogo)
    # ------------------------------------------------------------------
    def list_intentions(self) -> list[dict]:
        docs = self.store.query(INTENCIONES, [])
        docs.sort(key=lambda d: d.get("id_intencion", ""))
        return _out(docs)

    # ------------------------------------------------------------------
    # Interacciones (RF-13) e historial (HU030-HU033)
    # ------------------------------------------------------------------
    def add_interactions(self, id_perfil: str, items: list[dict]) -> dict:
        self._existing_profile(id_perfil)
        self._require_consent(id_perfil)
        creadas = 0
        for it in items:
            doc = {
                "id_interaccion": it["id_interaccion"],
                "fecha_hora": it["fecha_hora"],
                "detalle": it.get("detalle") or None,
                "id_perfil": id_perfil,
                "id_gesto": it.get("id_gesto"),
                "id_intencion": it.get("id_intencion"),
                "id_pictograma": it["id_pictograma"],
            }
            if self.store.create_if_absent(INTERACCIONES, it["id_interaccion"], doc):
                creadas += 1
        return {"recibidas": len(items), "creadas": creadas,
                "ya_existentes": len(items) - creadas}

    def _interactions(
        self, id_perfil: str, desde: date | None, hasta: date | None
    ) -> list[dict]:
        self._existing_profile(id_perfil)
        docs = self.store.query(INTERACCIONES, [Filter("id_perfil", "==", id_perfil)])
        result = []
        for d in docs:
            dia = reports.local_day(d["fecha_hora"])
            if (desde is None or dia >= desde) and (hasta is None or dia <= hasta):
                result.append(d)
        result.sort(key=lambda d: d["fecha_hora"], reverse=True)
        return result

    def list_interactions(
        self, id_perfil: str, desde: date | None = None, hasta: date | None = None
    ) -> list[dict]:
        return _out(self._interactions(id_perfil, desde, hasta))

    def get_interaction(self, id_perfil: str, id_interaccion: str) -> dict:
        self._existing_profile(id_perfil)
        doc = self.store.get(INTERACCIONES, id_interaccion)
        if doc is None or doc.get("id_perfil") != id_perfil:
            raise NotFound("El registro ya no está disponible.")  # HU033
        return _out(doc)

    def report(
        self, id_perfil: str, desde: date | None = None, hasta: date | None = None
    ) -> dict:
        data = reports.build_report(self._interactions(id_perfil, desde, hasta))
        data["desde"] = desde.isoformat() if desde else None
        data["hasta"] = hasta.isoformat() if hasta else None
        return data
