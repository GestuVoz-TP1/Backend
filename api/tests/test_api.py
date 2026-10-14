"""Pruebas de la API con Firestore en memoria y tokens de prueba."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from api import firebase
from api.catalog import INTENCIONES_INICIALES
from api.services import CONSENTIMIENTOS, INTERACCIONES, NINOS, PERFILES, VOZ
from api.store import InMemoryStore

BASE = "/api/v1"


def fake_verifier(token: str) -> dict:
    if not token.startswith("token-"):
        raise ValueError("token invalido")
    uid = token.removeprefix("token-")
    return {"uid": uid, "email": f"{uid}@correo.com"}


def iso(dt: datetime) -> str:
    return dt.isoformat()


NOW = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)


def perfil_payload(id_nino: str, ts: datetime = NOW, **overrides) -> dict:
    data = {
        "nivel_apoyo": "Moderado",
        "preferencias_de_comunicacion": {
            "gestos_activados": True,
            "gestos_habilitados": ["gesto-1", "gesto-2"],
            "columnas_tablero": 3,
            "alto_contraste": False,
            "pictogramas": [
                {"id_pictograma": "base-1", "orden": 1},
                {"id_pictograma": "base-2", "orden": 2},
            ],
        },
        "estado_perfil": "activo",
        "nino": {
            "id_nino": id_nino,
            "nombre": "Valentina López",
            "fecha_nacimiento": "2019-05-14",
            "genero": "Femenino",
        },
        "actualizado_en": iso(ts),
    }
    data.update(overrides)
    return data


def consent_payload(estado="otorgado", ts=NOW, retiro=None) -> dict:
    return {
        "estado_consentimiento": estado,
        "fecha_registro": iso(NOW),
        "fecha_retiro": iso(retiro) if retiro else None,
        "actualizado_en": iso(ts),
    }


def interaccion(fecha: datetime, picto="base-5", gesto=None, intencion=None) -> dict:
    return {
        "id_interaccion": str(uuid.uuid4()),
        "fecha_hora": iso(fecha),
        "detalle": "Pictograma seleccionado en el tablero",
        "id_pictograma": picto,
        "id_gesto": gesto,
        "id_intencion": intencion,
    }


class ApiTestCase(SimpleTestCase):
    def setUp(self):
        self.store = InMemoryStore()
        firebase.set_store(self.store)
        firebase.set_token_verifier(fake_verifier)
        self.client = self.client_for("tutor1")

    def tearDown(self):
        firebase.set_store(None)
        firebase.set_token_verifier(None)

    @staticmethod
    def client_for(uid: str) -> APIClient:
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer token-{uid}")
        return c

    def create_profile(self, client=None, consent="otorgado"):
        client = client or self.client
        id_perfil, id_nino = str(uuid.uuid4()), str(uuid.uuid4())
        r = client.put(
            f"{BASE}/perfiles/{id_perfil}/consentimiento",
            consent_payload(consent),
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        if consent == "otorgado":
            r = client.put(
                f"{BASE}/perfiles/{id_perfil}", perfil_payload(id_nino), format="json"
            )
            self.assertEqual(r.status_code, 200, r.content)
        return id_perfil, id_nino


class AutenticacionTests(ApiTestCase):
    def test_salud_sin_token(self):
        r = APIClient().get(f"{BASE}/salud")
        self.assertEqual(r.status_code, 200)

    def test_sin_token_401(self):
        r = APIClient().get(f"{BASE}/perfiles")
        self.assertEqual(r.status_code, 401)

    def test_token_invalido_401(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Bearer falso")
        self.assertEqual(c.get(f"{BASE}/perfiles").status_code, 401)

    def test_yo(self):
        r = self.client.get(f"{BASE}/yo")
        self.assertEqual(r.json(), {"uid": "tutor1", "correo": "tutor1@correo.com"})


class PerfilesTests(ApiTestCase):
    def test_perfil_requiere_consentimiento(self):
        id_perfil = str(uuid.uuid4())
        r = self.client.put(
            f"{BASE}/perfiles/{id_perfil}",
            perfil_payload(str(uuid.uuid4())),
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["error"]["codigo"], "consentimiento_requerido")

    def test_crear_y_listar_perfil_con_nino(self):
        id_perfil, id_nino = self.create_profile()
        perfiles = self.client.get(f"{BASE}/perfiles").json()
        self.assertEqual(len(perfiles), 1)
        p = perfiles[0]
        self.assertEqual(p["id_perfil"], id_perfil)
        self.assertEqual(p["nino"]["nombre"], "Valentina López")
        self.assertEqual(p["nino"]["fecha_nacimiento"], "2019-05-14")
        self.assertEqual(
            p["preferencias_de_comunicacion"]["pictogramas"][0]["id_pictograma"],
            "base-1",
        )
        self.assertNotIn("id_tutor", p)
        self.assertEqual(self.store.get(NINOS, id_nino)["id_tutor"], "tutor1")

    def test_otro_tutor_no_ve_el_perfil(self):
        id_perfil, _ = self.create_profile()
        otro = self.client_for("tutor2")
        self.assertEqual(otro.get(f"{BASE}/perfiles").json(), [])
        self.assertEqual(otro.get(f"{BASE}/perfiles/{id_perfil}").status_code, 404)
        r = otro.put(
            f"{BASE}/perfiles/{id_perfil}/consentimiento",
            consent_payload(ts=NOW + timedelta(days=1)),
            format="json",
        )
        self.assertEqual(r.status_code, 404)
        self.assertEqual(otro.delete(f"{BASE}/perfiles/{id_perfil}").status_code, 404)

    def test_gana_el_ultimo_cambio(self):
        id_perfil, id_nino = self.create_profile()
        viejo = perfil_payload(id_nino, ts=NOW - timedelta(hours=1), nivel_apoyo="Bajo")
        r = self.client.put(f"{BASE}/perfiles/{id_perfil}", viejo, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["actual"]["nivel_apoyo"], "Moderado")
        nuevo = perfil_payload(id_nino, ts=NOW + timedelta(hours=1), nivel_apoyo="Alto")
        r = self.client.put(f"{BASE}/perfiles/{id_perfil}", nuevo, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["nivel_apoyo"], "Alto")

    def test_validaciones(self):
        id_perfil, id_nino = self.create_profile()
        url = f"{BASE}/perfiles/{id_perfil}"
        sin_nombre = perfil_payload(id_nino)
        sin_nombre["nino"] = {**sin_nombre["nino"], "nombre": "  "}
        self.assertEqual(self.client.put(url, sin_nombre, format="json").status_code, 400)
        bebe = perfil_payload(id_nino)
        bebe["nino"] = {**bebe["nino"], "fecha_nacimiento": date.today().isoformat()}
        self.assertEqual(self.client.put(url, bebe, format="json").status_code, 400)
        tamano = perfil_payload(id_nino)
        tamano["preferencias_de_comunicacion"]["columnas_tablero"] = 7
        self.assertEqual(self.client.put(url, tamano, format="json").status_code, 400)

    def test_eliminar_perfil_en_cascada(self):
        id_perfil, id_nino = self.create_profile()
        self.client.put(
            f"{BASE}/perfiles/{id_perfil}/configuracion-voz",
            {"idioma": "es-ES", "velocidad": 0.45, "volumen": 1.0,
             "voz_activada": True, "actualizado_en": iso(NOW)},
            format="json",
        )
        self.client.post(
            f"{BASE}/perfiles/{id_perfil}/interacciones",
            {"interacciones": [interaccion(NOW)]},
            format="json",
        )
        r = self.client.delete(f"{BASE}/perfiles/{id_perfil}")
        self.assertEqual(r.status_code, 204)
        self.assertIsNone(self.store.get(PERFILES, id_perfil))
        self.assertIsNone(self.store.get(NINOS, id_nino))
        self.assertIsNone(self.store.get(VOZ, id_perfil))
        self.assertIsNone(self.store.get(CONSENTIMIENTOS, id_perfil))
        self.assertEqual(self.store.query(INTERACCIONES, []), [])


class ConsentimientoYVozTests(ApiTestCase):
    def test_retiro_bloquea_nuevas_sincronizaciones_sin_borrar(self):
        id_perfil, _ = self.create_profile()
        url_int = f"{BASE}/perfiles/{id_perfil}/interacciones"
        self.client.post(url_int, {"interacciones": [interaccion(NOW)]}, format="json")
        r = self.client.put(
            f"{BASE}/perfiles/{id_perfil}/consentimiento",
            consent_payload("retirado", ts=NOW + timedelta(minutes=5),
                            retiro=NOW + timedelta(minutes=5)),
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        r = self.client.post(url_int, {"interacciones": [interaccion(NOW)]}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(len(self.client.get(url_int).json()), 1)

    def test_retiro_requiere_fecha(self):
        id_perfil, _ = self.create_profile()
        r = self.client.put(
            f"{BASE}/perfiles/{id_perfil}/consentimiento",
            consent_payload("retirado", ts=NOW + timedelta(minutes=1)),
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_no_otorgado_se_registra_pero_no_permite_datos(self):
        id_perfil, _ = self.create_profile(consent="no_otorgado")
        r = self.client.get(f"{BASE}/perfiles/{id_perfil}/consentimiento")
        self.assertEqual(r.json()["estado_consentimiento"], "no_otorgado")
        r = self.client.put(
            f"{BASE}/perfiles/{id_perfil}",
            perfil_payload(str(uuid.uuid4())),
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_voz_valores_permitidos(self):
        id_perfil, _ = self.create_profile()
        url = f"{BASE}/perfiles/{id_perfil}/configuracion-voz"
        mala = {"idioma": "es-ES", "velocidad": 2, "volumen": 1.0,
                "voz_activada": True, "actualizado_en": iso(NOW)}
        self.assertEqual(self.client.put(url, mala, format="json").status_code, 400)
        ingles = {**mala, "velocidad": 0.5, "idioma": "en-US"}
        self.assertEqual(self.client.put(url, ingles, format="json").status_code, 400)
        buena = {**mala, "velocidad": 0.6, "volumen": 0.75}
        r = self.client.put(url, buena, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(url).json()["volumen"], 0.75)


class InteraccionesYReportesTests(ApiTestCase):
    def test_lote_no_duplica_al_reenviar(self):
        id_perfil, _ = self.create_profile()
        url = f"{BASE}/perfiles/{id_perfil}/interacciones"
        lote = {"interacciones": [interaccion(NOW), interaccion(NOW)]}
        r1 = self.client.post(url, lote, format="json").json()
        r2 = self.client.post(url, lote, format="json").json()
        self.assertEqual(r1["creadas"], 2)
        self.assertEqual(r2["creadas"], 0)
        self.assertEqual(r2["ya_existentes"], 2)
        self.assertEqual(len(self.client.get(url).json()), 2)

    def test_filtro_por_fechas_y_detalle(self):
        id_perfil, _ = self.create_profile()
        url = f"{BASE}/perfiles/{id_perfil}/interacciones"
        hoy = interaccion(NOW)
        antes = interaccion(NOW - timedelta(days=10))
        self.client.post(url, {"interacciones": [hoy, antes]}, format="json")
        filtradas = self.client.get(url, {"desde": "2026-10-14", "hasta": "2026-10-14"})
        self.assertEqual([i["id_interaccion"] for i in filtradas.json()],
                         [hoy["id_interaccion"]])
        vacio = self.client.get(url, {"desde": "2020-01-01", "hasta": "2020-01-02"})
        self.assertEqual(vacio.json(), [])
        invertido = self.client.get(url, {"desde": "2026-10-14", "hasta": "2026-10-01"})
        self.assertEqual(invertido.status_code, 400)
        detalle = self.client.get(f"{url}/{hoy['id_interaccion']}")
        self.assertEqual(detalle.json()["id_pictograma"], "base-5")
        self.assertEqual(self.client.get(f"{url}/{uuid.uuid4()}").status_code, 404)

    def test_reporte(self):
        id_perfil, _ = self.create_profile()
        url = f"{BASE}/perfiles/{id_perfil}/interacciones"
        self.client.post(url, {"interacciones": [interaccion(NOW)]}, format="json")
        pocos = self.client.get(f"{BASE}/perfiles/{id_perfil}/reportes").json()
        self.assertFalse(pocos["datos_suficientes_para_frecuencias"])
        self.assertEqual(pocos["mas_frecuentes"], [])
        self.client.post(
            url,
            {"interacciones": [
                interaccion(NOW, picto="base-5"),
                interaccion(NOW, picto="base-9", gesto="gesto-2",
                            intencion="intencion-2"),
            ]},
            format="json",
        )
        rep = self.client.get(f"{BASE}/perfiles/{id_perfil}/reportes").json()
        self.assertEqual(rep["total_interacciones"], 3)
        self.assertEqual(rep["interacciones_por_gesto"], 1)
        self.assertEqual(rep["intenciones_distintas"], 1)
        self.assertEqual(rep["mas_frecuentes"][0],
                         {"id_pictograma": "base-5", "cantidad": 2})
        self.assertEqual(len(rep["actividad_semanal"]), 7)
        self.assertIn("No constituye una evaluación clínica", rep["aviso"])


class PictogramasEIntencionesTests(ApiTestCase):
    def test_pictograma_personalizado(self):
        id_perfil, _ = self.create_profile()
        id_picto = str(uuid.uuid4())
        data = {"nombre": "Mi osito", "mensaje": "Quiero mi osito",
                "id_categoria": 2, "actualizado_en": iso(NOW)}
        sin_perfil = self.client.put(f"{BASE}/pictogramas/{id_picto}", data, format="json")
        self.assertEqual(sin_perfil.status_code, 400)
        url = f"{BASE}/pictogramas/{id_picto}?id_perfil={id_perfil}"
        sin_mensaje = {**data, "mensaje": " "}
        self.assertEqual(self.client.put(url, sin_mensaje, format="json").status_code, 400)
        r = self.client.put(url, data, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["referencia_imagen"])
        self.assertEqual(len(self.client.get(f"{BASE}/pictogramas").json()), 1)
        otro = self.client_for("tutor2")
        self.assertEqual(otro.get(f"{BASE}/pictogramas").json(), [])
        self.assertEqual(otro.delete(f"{BASE}/pictogramas/{id_picto}").status_code, 404)
        self.assertEqual(self.client.delete(f"{BASE}/pictogramas/{id_picto}").status_code, 204)

    def test_intenciones(self):
        for i in INTENCIONES_INICIALES:
            self.store.put_if_newer(
                "intenciones_comunicativas", i["id_intencion"],
                {**i, "actualizado_en": NOW}, "actualizado_en",
            )
        r = self.client.get(f"{BASE}/intenciones").json()
        self.assertEqual([i["id_intencion"] for i in r],
                         ["intencion-1", "intencion-2", "intencion-3", "intencion-4"])
        self.assertEqual(r[1]["mensaje_asociado"], "Quiero agua")
