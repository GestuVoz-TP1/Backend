"""
Archivos de los pictogramas personalizados (Cloud Storage for Firebase).

`FileStore` define las operaciones que necesita la logica de negocio.
- `StorageFileStore`: implementacion real con el SDK de Firebase Admin.
- `InMemoryFileStore`: implementacion en memoria para las pruebas automaticas.
"""

from __future__ import annotations

import threading
from typing import Protocol


class FileStore(Protocol):
    def put(self, path: str, data: bytes, content_type: str) -> None: ...

    def get(self, path: str) -> tuple[bytes, str] | None: ...

    def delete(self, path: str) -> None: ...


# ---------------------------------------------------------------------------
# Implementacion en memoria (pruebas)
# ---------------------------------------------------------------------------
class InMemoryFileStore:
    def __init__(self) -> None:
        self._files: dict[str, tuple[bytes, str]] = {}
        self._lock = threading.Lock()

    def put(self, path: str, data: bytes, content_type: str) -> None:
        with self._lock:
            self._files[path] = (bytes(data), content_type)

    def get(self, path: str) -> tuple[bytes, str] | None:
        return self._files.get(path)

    def delete(self, path: str) -> None:
        with self._lock:
            self._files.pop(path, None)

    def paths(self) -> list[str]:
        return sorted(self._files)


# ---------------------------------------------------------------------------
# Implementacion real (Cloud Storage for Firebase)
# ---------------------------------------------------------------------------
class StorageFileStore:
    def __init__(self, bucket) -> None:
        self._bucket = bucket

    def put(self, path: str, data: bytes, content_type: str) -> None:
        blob = self._bucket.blob(path)
        blob.cache_control = "private, max-age=31536000"
        blob.upload_from_string(data, content_type=content_type)

    def get(self, path: str) -> tuple[bytes, str] | None:
        from google.api_core.exceptions import NotFound

        blob = self._bucket.blob(path)
        try:
            data = blob.download_as_bytes()
        except NotFound:
            return None
        return data, blob.content_type or "application/octet-stream"

    def delete(self, path: str) -> None:
        from google.api_core.exceptions import NotFound

        try:
            self._bucket.blob(path).delete()
        except NotFound:
            pass
