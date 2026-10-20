"""Errores de negocio y formato uniforme de respuestas de error."""

from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class NotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No se encontró el recurso."
    default_code = "no_encontrado"


class ConsentRequired(APIException):
    """Sin consentimiento vigente no se sincronizan datos del perfil."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = (
        "El perfil no tiene un consentimiento vigente; sus datos no se "
        "sincronizan con la nube."
    )
    default_code = "consentimiento_requerido"


class StaleWrite(APIException):
    """Gana el ultimo cambio: la version enviada es mas antigua."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Existe una versión más reciente de este dato."
    default_code = "version_desactualizada"

    def __init__(self, current: dict):
        super().__init__()
        self.current = current


class StorageUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "El almacenamiento de imágenes no está disponible."
    default_code = "almacenamiento_no_disponible"


class InvalidImage(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "La imagen debe ser JPG, PNG o WebP."
    default_code = "imagen_invalida"


class ImageTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "La imagen no puede superar los 500 KB."
    default_code = "imagen_muy_grande"


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    code = getattr(exc, "default_code", "error")
    detail = response.data
    if isinstance(detail, dict) and set(detail) == {"detail"}:
        detail = detail["detail"]
    body = {"error": {"codigo": code, "detalle": detail}}
    if isinstance(exc, StaleWrite):
        body["actual"] = exc.current
    return Response(body, status=response.status_code, headers=response.headers)
