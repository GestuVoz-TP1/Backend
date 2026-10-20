"""
API REST de GestuVoz (OB2: "API REST y Logica de negocio").

Todas las rutas, salvo /salud, requieren el token de Firebase Authentication.
Las vistas solo validan y delegan en `GestuVozService`.
"""

from __future__ import annotations

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import firebase
from .serializers import (
    ConfiguracionVozSerializer,
    ConsentimientoSerializer,
    LoteInteraccionesSerializer,
    PerfilSerializer,
    PictogramaSerializer,
    RangoFechasSerializer,
    validate_id,
)
from .services import GestuVozService


def _service(request) -> GestuVozService:
    return GestuVozService(
        firebase.get_store(), request.user.uid, files=firebase.get_file_store
    )


def _valid(serializer_cls, data):
    serializer = serializer_cls(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class SaludView(APIView):
    """Comprobacion de disponibilidad (sin autenticacion)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return Response({"estado": "ok", "servicio": "GestuVoz API"})


class YoView(APIView):
    def get(self, request):
        return Response({"uid": request.user.uid, "correo": request.user.email})


class PerfilesView(APIView):
    def get(self, request):
        return Response(_service(request).list_profiles())


class PerfilView(APIView):
    def get(self, request, id_perfil):
        return Response(_service(request).get_profile(validate_id(id_perfil)))

    def put(self, request, id_perfil):
        data = _valid(PerfilSerializer, request.data)
        return Response(_service(request).put_profile(validate_id(id_perfil), data))

    def delete(self, request, id_perfil):
        _service(request).delete_profile(validate_id(id_perfil))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConsentimientoView(APIView):
    def get(self, request, id_perfil):
        return Response(_service(request).get_consent(validate_id(id_perfil)))

    def put(self, request, id_perfil):
        data = _valid(ConsentimientoSerializer, request.data)
        return Response(_service(request).put_consent(validate_id(id_perfil), data))


class ConfiguracionVozView(APIView):
    def get(self, request, id_perfil):
        return Response(_service(request).get_voice(validate_id(id_perfil)))

    def put(self, request, id_perfil):
        data = _valid(ConfiguracionVozSerializer, request.data)
        return Response(_service(request).put_voice(validate_id(id_perfil), data))


class InteraccionesView(APIView):
    def get(self, request, id_perfil):
        rango = _valid(RangoFechasSerializer, request.query_params)
        return Response(
            _service(request).list_interactions(
                validate_id(id_perfil), rango.get("desde"), rango.get("hasta")
            )
        )

    def post(self, request, id_perfil):
        data = _valid(LoteInteraccionesSerializer, request.data)
        result = _service(request).add_interactions(
            validate_id(id_perfil), data["interacciones"]
        )
        return Response(result, status=status.HTTP_201_CREATED)


class InteraccionView(APIView):
    def get(self, request, id_perfil, id_interaccion):
        return Response(
            _service(request).get_interaction(
                validate_id(id_perfil), validate_id(id_interaccion)
            )
        )


class ReporteView(APIView):
    def get(self, request, id_perfil):
        rango = _valid(RangoFechasSerializer, request.query_params)
        return Response(
            _service(request).report(
                validate_id(id_perfil), rango.get("desde"), rango.get("hasta")
            )
        )


class PictogramasView(APIView):
    def get(self, request):
        return Response(_service(request).list_pictograms())


class PictogramaView(APIView):
    """PUT requiere ?id_perfil=... para verificar el consentimiento."""

    def put(self, request, id_pictograma):
        data = _valid(PictogramaSerializer, request.data)
        id_perfil = request.query_params.get("id_perfil", "")
        return Response(
            _service(request).put_pictogram(
                validate_id(id_pictograma), validate_id(id_perfil), data
            )
        )

    def delete(self, request, id_pictograma):
        _service(request).delete_pictogram(validate_id(id_pictograma))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PictogramaImagenView(APIView):
    """Imagen de un pictograma personalizado (Cloud Storage).

    PUT recibe los bytes de la imagen en el cuerpo (JPG, PNG o WebP, hasta
    500 KB) y requiere ?id_perfil=... para verificar el consentimiento.
    """

    def put(self, request, id_pictograma):
        id_perfil = request.query_params.get("id_perfil", "")
        return Response(
            _service(request).put_pictogram_image(
                validate_id(id_pictograma), validate_id(id_perfil), request.body
            )
        )

    def get(self, request, id_pictograma):
        data, content_type = _service(request).get_pictogram_image(
            validate_id(id_pictograma)
        )
        response = HttpResponse(data, content_type=content_type)
        response["Cache-Control"] = "private, max-age=86400"
        return response

    def delete(self, request, id_pictograma):
        return Response(
            _service(request).delete_pictogram_image(validate_id(id_pictograma))
        )


class IntencionesView(APIView):
    def get(self, request):
        return Response(_service(request).list_intentions())
