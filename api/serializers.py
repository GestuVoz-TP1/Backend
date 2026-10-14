"""
Validacion de los datos que envia la app.

Los campos siguen la estructura de Cloud Firestore de OB2 (Figura 7), mas la
coleccion `ninos` (campos de NINO, Figura 6). Las reglas coinciden con las de
la app movil.
"""

from __future__ import annotations

import re
from datetime import date

from rest_framework import serializers

# Identificadores: UUID generados por la app, o claves de catalogo fijo
# ("base-12", "gesto-1", "intencion-1").
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

ESTADOS_PERFIL = ["activo"]
ESTADOS_CONSENTIMIENTO = ["otorgado", "no_otorgado", "retirado"]
COLUMNAS_TABLERO = [2, 3, 4]  # HU016: grande, mediano, pequeno


def validate_id(value: str) -> str:
    if not ID_PATTERN.match(value or ""):
        raise serializers.ValidationError("Identificador inválido.")
    return value


class IdField(serializers.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 64)
        super().__init__(validators=[validate_id], **kwargs)


def _age(birth: date, today: date) -> int:
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


class NinoSerializer(serializers.Serializer):
    """Coleccion `ninos` (NINO): datos basicos del nino (HU021, HU022)."""

    id_nino = IdField()
    nombre = serializers.CharField(max_length=150, trim_whitespace=True)
    fecha_nacimiento = serializers.DateField()
    genero = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )

    def validate_nombre(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("El nombre del niño es obligatorio.")
        return value.strip()

    def validate_fecha_nacimiento(self, value: date) -> date:
        age = _age(value, date.today())
        if age < 2 or age > 17:
            raise serializers.ValidationError("La edad debe estar entre 2 y 17 años.")
        return value


class PictogramaVisibleSerializer(serializers.Serializer):
    id_pictograma = IdField()
    orden = serializers.IntegerField(min_value=0)


class PreferenciasSerializer(serializers.Serializer):
    """`perfiles.preferencias_de_comunicacion` (RF-09, RF-15, HU004, HU016)."""

    gestos_activados = serializers.BooleanField(default=False)
    gestos_habilitados = serializers.ListField(
        child=IdField(), default=list, max_length=100
    )
    columnas_tablero = serializers.ChoiceField(choices=COLUMNAS_TABLERO, default=3)
    alto_contraste = serializers.BooleanField(default=False)
    pictogramas = PictogramaVisibleSerializer(many=True, default=list, max_length=2000)


class PerfilSerializer(serializers.Serializer):
    """Coleccion `perfiles` + datos del nino (HU021, HU022)."""

    nivel_apoyo = serializers.CharField(
        max_length=100, required=False, allow_null=True, allow_blank=True
    )
    preferencias_de_comunicacion = PreferenciasSerializer()
    estado_perfil = serializers.ChoiceField(choices=ESTADOS_PERFIL, default="activo")
    nino = NinoSerializer()
    actualizado_en = serializers.DateTimeField()


class ConsentimientoSerializer(serializers.Serializer):
    """Coleccion `consentimientos` (HU027, HU028)."""

    estado_consentimiento = serializers.ChoiceField(choices=ESTADOS_CONSENTIMIENTO)
    fecha_registro = serializers.DateTimeField()
    fecha_retiro = serializers.DateTimeField(required=False, allow_null=True)
    actualizado_en = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["estado_consentimiento"] == "retirado" and not attrs.get("fecha_retiro"):
            raise serializers.ValidationError(
                {"fecha_retiro": "Indica la fecha de retiro del consentimiento."}
            )
        return attrs


class ConfiguracionVozSerializer(serializers.Serializer):
    """Coleccion `configuraciones_voz` (HU017)."""

    idioma = serializers.CharField(max_length=20)
    tipo_voz = serializers.CharField(
        max_length=100, required=False, allow_null=True, allow_blank=True
    )
    velocidad = serializers.FloatField(min_value=0.2, max_value=0.8)
    volumen = serializers.FloatField(min_value=0.1, max_value=1.0)
    voz_activada = serializers.BooleanField(default=True)
    actualizado_en = serializers.DateTimeField()

    def validate_idioma(self, value: str) -> str:
        if not value.lower().startswith("es"):
            raise serializers.ValidationError("La voz debe estar en español.")
        return value


class PictogramaSerializer(serializers.Serializer):
    """Coleccion `pictogramas`: pictogramas personalizados (HU012-HU014)."""

    nombre = serializers.CharField(max_length=150)
    mensaje = serializers.CharField(max_length=500)
    id_categoria = serializers.IntegerField(min_value=1)
    # Cloud Storage aun no esta activo: la imagen queda en el dispositivo.
    referencia_imagen = serializers.CharField(
        max_length=500, required=False, allow_null=True, allow_blank=True
    )
    actualizado_en = serializers.DateTimeField()

    def validate_mensaje(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Escribe el mensaje que dirá la voz.")
        return value.strip()


class InteraccionSerializer(serializers.Serializer):
    """Coleccion `interacciones` (RF-13)."""

    id_interaccion = IdField()
    fecha_hora = serializers.DateTimeField()
    detalle = serializers.CharField(
        max_length=1000, required=False, allow_null=True, allow_blank=True
    )
    id_pictograma = IdField()
    id_gesto = IdField(required=False, allow_null=True)
    id_intencion = IdField(required=False, allow_null=True)


class LoteInteraccionesSerializer(serializers.Serializer):
    """Envio por lotes de lo registrado sin conexion."""

    interacciones = InteraccionSerializer(many=True, max_length=500)


class RangoFechasSerializer(serializers.Serializer):
    """Filtro por fechas (HU032). `hasta` es inclusivo."""

    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)

    def validate(self, attrs):
        desde, hasta = attrs.get("desde"), attrs.get("hasta")
        if desde and hasta and desde > hasta:
            raise serializers.ValidationError("El período de fechas no es válido.")
        return attrs
