"""
Configuracion del backend de GestuVoz (Django + Django REST Framework).

La unica base de datos es Cloud Firestore (OB2). Django no usa una base de
datos SQL: DATABASES queda vacio y no hay modelos ni migraciones.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Variables locales de desarrollo (en Render se definen en el panel).
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "si"}


def _list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


DEBUG = _bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "solo-desarrollo-no-usar-en-produccion"
    else:
        raise RuntimeError("Falta la variable de entorno DJANGO_SECRET_KEY.")

ALLOWED_HOSTS = _list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,10.0.2.2")
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])

INSTALLED_APPS = [
    # contenttypes y auth solo se cargan porque DRF los importa; no se usan
    # tablas SQL.
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

SILENCED_SYSTEM_CHECKS = [
    # La API se autentica con el token de Firebase en el encabezado
    # Authorization, no con cookies de sesion: CSRF no aplica.
    "security.W003",
    # En Render el servicio corre en un subdominio de onrender.com (dominio
    # ajeno): no corresponde HSTS para subdominios ni la lista de precarga.
    "security.W005",
    "security.W021",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Sin base de datos SQL: todos los datos estan en Cloud Firestore.
DATABASES: dict = {}

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.FirebaseAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "api.errors.exception_handler",
}

# Credenciales de la cuenta de servicio de Firebase (nunca en el repositorio):
# - FIREBASE_CREDENTIALS_FILE: ruta a un archivo JSON (desarrollo local), o
# - FIREBASE_CREDENTIALS_JSON: el contenido del JSON (Render).
FIREBASE_CREDENTIALS_FILE = os.environ.get("FIREBASE_CREDENTIALS_FILE", "")
FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "gestuvoz")
# Cloud Storage for Firebase: imagenes de los pictogramas personalizados.
FIREBASE_STORAGE_BUCKET = os.environ.get("FIREBASE_STORAGE_BUCKET", "")

# Seguridad en produccion (HTTPS, OB2 9.1).
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = _bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
