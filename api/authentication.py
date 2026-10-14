"""
Autenticacion con Firebase Authentication (OB2 RT-04, RF-10, RF-12).

La app inicia sesion con Firebase y envia el token en cada peticion:
    Authorization: Bearer <ID token de Firebase>
El backend verifica el token y usa el UID como identificador del tutor.
"""

from __future__ import annotations

from dataclasses import dataclass

from rest_framework import authentication, exceptions

from . import firebase


@dataclass(frozen=True)
class Tutor:
    """Padre o tutor autenticado (PADRE_TUTOR = usuario de Firebase Auth)."""

    uid: str
    email: str | None

    @property
    def is_authenticated(self) -> bool:
        return True


class FirebaseAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode()
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            raise exceptions.AuthenticationFailed("Encabezado de autorización inválido.")
        try:
            claims = firebase.verify_id_token(parts[1])
        except Exception as exc:  # token vencido, revocado o invalido
            raise exceptions.AuthenticationFailed(
                "La sesión no es válida o expiró. Inicia sesión nuevamente."
            ) from exc
        uid = claims.get("uid") or claims.get("user_id") or claims.get("sub")
        if not uid:
            raise exceptions.AuthenticationFailed("Token sin identificador de usuario.")
        return Tutor(uid=uid, email=claims.get("email")), claims

    def authenticate_header(self, request) -> str:
        return self.keyword
