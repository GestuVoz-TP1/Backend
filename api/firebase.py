"""
Integracion con Firebase (OB2: Firebase Authentication, Cloud Firestore y
Cloud Storage for Firebase).

La credencial de la cuenta de servicio se lee de variables de entorno y nunca
se guarda en el repositorio. La inicializacion es perezosa para que las
pruebas no necesiten credenciales: reemplazan los almacenes y el verificador
de tokens con `set_store`, `set_file_store` y `set_token_verifier`.
"""

from __future__ import annotations

import json
import threading
from typing import Callable

from django.conf import settings

from .files import FileStore, StorageFileStore
from .store import DocumentStore, FirestoreStore

_lock = threading.Lock()
_app = None
_store: DocumentStore | None = None
_file_store: FileStore | None = None
_verifier: Callable[[str], dict] | None = None


def _firebase_app():
    global _app
    with _lock:
        if _app is None:
            import firebase_admin
            from firebase_admin import credentials

            if settings.FIREBASE_CREDENTIALS_JSON:
                cred = credentials.Certificate(
                    json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                )
            elif settings.FIREBASE_CREDENTIALS_FILE:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE)
            else:
                raise RuntimeError(
                    "Configura FIREBASE_CREDENTIALS_FILE o FIREBASE_CREDENTIALS_JSON."
                )
            options = {"projectId": settings.FIREBASE_PROJECT_ID}
            if settings.FIREBASE_STORAGE_BUCKET:
                options["storageBucket"] = settings.FIREBASE_STORAGE_BUCKET
            _app = firebase_admin.initialize_app(cred, options)
        return _app


def get_store() -> DocumentStore:
    global _store
    if _store is None:
        from firebase_admin import firestore

        _store = FirestoreStore(firestore.client(_firebase_app()))
    return _store


def get_file_store() -> FileStore:
    global _file_store
    if _file_store is None:
        if not settings.FIREBASE_STORAGE_BUCKET:
            from .errors import StorageUnavailable

            raise StorageUnavailable()
        from firebase_admin import storage

        _file_store = StorageFileStore(storage.bucket(app=_firebase_app()))
    return _file_store


def verify_id_token(token: str) -> dict:
    """Verifica un token de Firebase Authentication y devuelve sus datos."""
    if _verifier is not None:
        return _verifier(token)
    from firebase_admin import auth

    return auth.verify_id_token(token, app=_firebase_app(), check_revoked=True)


# --- Puntos de reemplazo para pruebas -------------------------------------
def set_store(store: DocumentStore | None) -> None:
    global _store
    _store = store


def set_file_store(store: FileStore | None) -> None:
    global _file_store
    _file_store = store


def set_token_verifier(fn: Callable[[str], dict] | None) -> None:
    global _verifier
    _verifier = fn
