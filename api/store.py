"""
Acceso a los datos (Cloud Firestore).

`DocumentStore` define las operaciones que necesita la logica de negocio.
- `FirestoreStore`: implementacion real con el SDK de Firebase Admin.
- `InMemoryStore`: implementacion en memoria para las pruebas automaticas.

Las fechas se guardan como `datetime` con zona horaria (Firestore las guarda
como Timestamp).
"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

Doc = dict[str, Any]


@dataclass(frozen=True)
class Filter:
    field: str
    op: str  # "==" (unico operador usado)
    value: Any


@dataclass
class WriteResult:
    """Resultado de una escritura condicionada por fecha (gana el ultimo)."""

    applied: bool
    current: Doc


class DocumentStore(Protocol):
    def get(self, collection: str, doc_id: str) -> Doc | None: ...

    def query(self, collection: str, filters: list[Filter]) -> list[Doc]: ...

    def put_if_newer(
        self, collection: str, doc_id: str, data: Doc, ts_field: str
    ) -> WriteResult: ...

    def create_if_absent(self, collection: str, doc_id: str, data: Doc) -> bool: ...

    def delete_many(self, refs: list[tuple[str, str]]) -> None: ...


def _is_newer_or_equal(incoming: datetime, stored: datetime | None) -> bool:
    return stored is None or incoming >= stored


# ---------------------------------------------------------------------------
# Implementacion en memoria (pruebas)
# ---------------------------------------------------------------------------
class InMemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Doc]] = {}
        self._lock = threading.Lock()

    def get(self, collection: str, doc_id: str) -> Doc | None:
        doc = self._data.get(collection, {}).get(doc_id)
        return copy.deepcopy(doc) if doc is not None else None

    def query(self, collection: str, filters: list[Filter]) -> list[Doc]:
        result = []
        for doc in self._data.get(collection, {}).values():
            if all(f.op == "==" and doc.get(f.field) == f.value for f in filters):
                result.append(copy.deepcopy(doc))
        return result

    def put_if_newer(
        self, collection: str, doc_id: str, data: Doc, ts_field: str
    ) -> WriteResult:
        with self._lock:
            col = self._data.setdefault(collection, {})
            stored = col.get(doc_id)
            if stored is not None and not _is_newer_or_equal(
                data[ts_field], stored.get(ts_field)
            ):
                return WriteResult(False, copy.deepcopy(stored))
            col[doc_id] = copy.deepcopy(data)
            return WriteResult(True, copy.deepcopy(data))

    def create_if_absent(self, collection: str, doc_id: str, data: Doc) -> bool:
        with self._lock:
            col = self._data.setdefault(collection, {})
            if doc_id in col:
                return False
            col[doc_id] = copy.deepcopy(data)
            return True

    def delete_many(self, refs: list[tuple[str, str]]) -> None:
        with self._lock:
            for collection, doc_id in refs:
                self._data.get(collection, {}).pop(doc_id, None)


# ---------------------------------------------------------------------------
# Implementacion real (Cloud Firestore)
# ---------------------------------------------------------------------------
class FirestoreStore:
    _BATCH_LIMIT = 450  # Firestore admite hasta 500 escrituras por lote

    def __init__(self, client) -> None:
        self._db = client

    def get(self, collection: str, doc_id: str) -> Doc | None:
        snap = self._db.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def query(self, collection: str, filters: list[Filter]) -> list[Doc]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        q = self._db.collection(collection)
        for f in filters:
            q = q.where(filter=FieldFilter(f.field, f.op, f.value))
        return [snap.to_dict() for snap in q.stream()]

    def put_if_newer(
        self, collection: str, doc_id: str, data: Doc, ts_field: str
    ) -> WriteResult:
        from google.cloud import firestore

        ref = self._db.collection(collection).document(doc_id)
        transaction = self._db.transaction()

        @firestore.transactional
        def _run(tx) -> WriteResult:
            snap = ref.get(transaction=tx)
            stored = snap.to_dict() if snap.exists else None
            if stored is not None and not _is_newer_or_equal(
                data[ts_field], stored.get(ts_field)
            ):
                return WriteResult(False, stored)
            tx.set(ref, data)
            return WriteResult(True, data)

        return _run(transaction)

    def create_if_absent(self, collection: str, doc_id: str, data: Doc) -> bool:
        from google.api_core.exceptions import AlreadyExists

        try:
            self._db.collection(collection).document(doc_id).create(data)
            return True
        except AlreadyExists:
            return False

    def delete_many(self, refs: list[tuple[str, str]]) -> None:
        for start in range(0, len(refs), self._BATCH_LIMIT):
            batch = self._db.batch()
            for collection, doc_id in refs[start : start + self._BATCH_LIMIT]:
                batch.delete(self._db.collection(collection).document(doc_id))
            batch.commit()
