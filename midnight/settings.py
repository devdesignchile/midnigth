"""
Django settings for midnight project.

Producción y desarrollo controlados por variables de entorno (.env)
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# =========================
# Paths base
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables de entorno desde .env
load_dotenv(BASE_DIR / ".env")

# =========================
# Seguridad básica
# =========================

# SECRET_KEY: en producción debe venir desde el .env
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-_g^(%h2qn(_0=9u!tw$txz()7_6t^is%w)e=t9we=6_nn3c6xs",
)

# DEBUG: en producción debe ser False
DEBUG = os.getenv("DEBUG", "False") == "True"

# Dominio de producción + IP del VPS
ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,midnight.cl,www.midnight.cl,173.249.16.174"
).split(",")

# CSRF confiables (importante con HTTPS y Cloudflare)
CSRF_TRUSTED_ORIGINS = [
    "https://midnight.cl",
    "https://www.midnight.cl",
]

# =========================
# Aplicaciones
# =========================

INSTALLED_APPS = [
    # Terceros
    "jazzmin",
    "mercadopago",
    "widget_tweaks",

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Apps locales
    "app.places",
    "app.account",
]

# =========================
# Middleware
# =========================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "midnight.urls"

# =========================
# Templates
# =========================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "app.account.context_processors.account_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "midnight.wsgi.application"

# =========================
# Base de datos
# =========================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "midnight_db"),
        "USER": os.getenv("DB_USER", "midnight_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", "rodrigo911891"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# =========================
# Validación de contraseñas
# =========================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========================
# Internacionalización
# =========================

LANGUAGE_CODE = "es-es"     
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# =========================
# Archivos estáticos
# =========================

STATIC_URL = "/static/"

# Carpeta donde collectstatic dejará todo en producción
STATIC_ROOT = BASE_DIR / "staticfiles"

# Carpeta donde tú trabajas los estáticos en desarrollo
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# =========================
# Archivos de usuario (MEDIA) / CDN (R2)
# =========================

# =========================
# Archivos de usuario (MEDIA) / CDN (R2)
# =========================

# =========================
# Archivos de usuario (MEDIA) / CDN (R2)
# =========================

USE_R2 = os.getenv("USE_R2", "False") == "True"

if USE_R2:
    INSTALLED_APPS += ["storages"]

    # Django 5 recomienda usar STORAGES
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    AWS_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "midnight-media")
    AWS_S3_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
    AWS_S3_REGION_NAME = os.getenv("R2_REGION_NAME", "auto")

    # Dominio público del CDN
    AWS_S3_CUSTOM_DOMAIN = "cdn.midnight.cl"

    # URL pública de los media
    MEDIA_URL = "https://cdn.midnight.cl/"
    # En modo R2 NO usamos MEDIA_ROOT local
else:
    # Storage clásico en disco para desarrollo
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"



# =========================
# Default primary key
# =========================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# Autenticación / Login
# =========================

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# =========================
# Jazzmin (Admin bonito)
# =========================

JAZZMIN_SETTINGS = {
    "site_title": "MidNight Admin",
    "site_header": "MidNight",
    "site_brand": "MidNight",
    "welcome_sign": "Bienvenido a MidNight",
    "show_ui_builder": True,
    "theme": "darkly",
    "custom_css": None,
}

# =========================
# MercadoPago
# =========================

# En producción idealmente todo viene del .env
MP_PUBLIC_KEY = os.getenv(
    "MP_PUBLIC_KEY",
    "TEST-0d76855a-8385-4344-8ca1-c55270724d2f",
)
MP_ACCESS_TOKEN = os.getenv(
    "MP_ACCESS_TOKEN",
    "TEST-3898631603914208-110423-bf235168ec42af0dd13bc34270713be8-237407882",
)
MP_CLIENT_ID = os.getenv("MP_CLIENT_ID")
MP_CLIENT_SECRET = os.getenv("MP_CLIENT_SECRET")

# =========================
# Email
# =========================
# Si estás en DEBUG => consola; si no => SMTP real

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "No Reply <no-reply@midnight.local>"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
    DEFAULT_FROM_EMAIL = f"No Reply <{EMAIL_HOST_USER}>"
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
