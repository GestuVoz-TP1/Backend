"""Carga en Firestore el catalogo de intenciones comunicativas."""

from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from api import firebase
from api.catalog import INTENCIONES_INICIALES
from api.services import INTENCIONES, TS


class Command(BaseCommand):
    help = "Carga o actualiza las intenciones comunicativas en Firestore."

    def handle(self, *args, **options):
        store = firebase.get_store()
        now = datetime.now(timezone.utc)
        for intencion in INTENCIONES_INICIALES:
            store.put_if_newer(
                INTENCIONES, intencion["id_intencion"], {**intencion, TS: now}, TS
            )
            self.stdout.write(f"  {intencion['id_intencion']}: {intencion['nombre']}")
        self.stdout.write(
            self.style.SUCCESS(f"{len(INTENCIONES_INICIALES)} intenciones cargadas.")
        )
