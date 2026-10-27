"""
Catalogo fijo compartido con la app movil.

Los gestos y los pictogramas iniciales vienen dentro de la app y tienen el
mismo identificador en todos los dispositivos, por lo que no se suben a
Firestore. Convencion de identificadores:

    pictograma inicial  -> "base-<id local>"   (p. ej. "base-12")
    pictograma propio   -> UUID generado por la app
    gesto               -> "gesto-<id local>"  (p. ej. "gesto-1")
    intencion           -> "intencion-<id local>"

Las intenciones comunicativas si se guardan en Firestore (OB2, Figura 7).
Deben coincidir con lib/infrastructure/seed/gesture_seed.dart de la app.
"""

INTENCIONES_INICIALES = [
    {
        "id_intencion": "intencion-1",
        "nombre": "Saludar",
        "descripcion": None,
        "mensaje_asociado": "Hola",
        "id_gesto": "gesto-1",
    },
    {
        "id_intencion": "intencion-2",
        "nombre": "Pedir agua",
        "descripcion": None,
        "mensaje_asociado": "Quiero agua",
        "id_gesto": "gesto-2",
    },
    {
        "id_intencion": "intencion-3",
        "nombre": "Pedir ayuda",
        "descripcion": None,
        "mensaje_asociado": "Necesito ayuda",
        "id_gesto": "gesto-3",
    },
    {
        "id_intencion": "intencion-4",
        "nombre": "Pedir que pare",
        "descripcion": None,
        "mensaje_asociado": "Para, por favor",
        "id_gesto": "gesto-4",
    },
    {
        "id_intencion": "intencion-5",
        "nombre": "Decir que sí",
        "descripcion": None,
        "mensaje_asociado": "Sí",
        "id_gesto": "gesto-5",
    },
    {
        "id_intencion": "intencion-6",
        "nombre": "Decir que no",
        "descripcion": None,
        "mensaje_asociado": "No",
        "id_gesto": "gesto-6",
    },
    {
        "id_intencion": "intencion-7",
        "nombre": "Pedir por favor",
        "descripcion": None,
        "mensaje_asociado": "Por favor",
        "id_gesto": "gesto-7",
    },
    {
        "id_intencion": "intencion-8",
        "nombre": "Avisar que terminó",
        "descripcion": None,
        "mensaje_asociado": "Ya terminé",
        "id_gesto": "gesto-8",
    },
    {
        "id_intencion": "intencion-9",
        "nombre": "Pedir silencio",
        "descripcion": None,
        "mensaje_asociado": "Quiero silencio",
        "id_gesto": "gesto-9",
    },
    {
        "id_intencion": "intencion-10",
        "nombre": "Pedir un descanso",
        "descripcion": None,
        "mensaje_asociado": "Necesito un descanso",
        "id_gesto": "gesto-10",
    },
    {
        "id_intencion": "intencion-11",
        "nombre": "Pedir un abrazo",
        "descripcion": None,
        "mensaje_asociado": "Quiero un abrazo",
        "id_gesto": "gesto-11",
    },
]
