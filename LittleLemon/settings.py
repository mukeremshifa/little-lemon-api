"""
Django settings for the Little Lemon capstone project.

The backend runs on MySQL. Every environment-specific value — credentials, secret
key, debug flag — is read from the environment (or a local, gitignored ``.env``)
so the same settings module can be promoted to production untouched.

Copy ``.env.example`` to ``.env`` and fill in your database credentials.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present; real environment variables always win.
load_dotenv(BASE_DIR / ".env")


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-dev-only-key-change-me-in-production"
)

# DEBUG is on unless DJANGO_DEBUG is explicitly set to a falsy value.
DEBUG = os.environ.get("DJANGO_DEBUG", "1").lower() in ("1", "true", "yes", "on")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework.authtoken",  # DRF token auth (required by Djoser token endpoints)
    "djoser",                    # User registration / token management endpoints
    # Local
    "LittleLemonAPI",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "LittleLemon.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "LittleLemon.wsgi.application"


# --------------------------------------------------------------------------- #
# Database
#
# MySQL by default, driven by the DB_* variables in .env. Set DB_ENGINE=sqlite to
# fall back to a local SQLite file (handy for a quick run without a DB server).
# --------------------------------------------------------------------------- #
if os.environ.get("DB_ENGINE", "mysql").lower() == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "LittleLemon"),
            "USER": os.environ.get("DB_USER", "root"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {"init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Where django.contrib.auth sends users after login / logout.
LOGIN_REDIRECT_URL = "index"
LOGOUT_REDIRECT_URL = "index"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------- #
# Django REST Framework
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    # Token auth is the primary scheme; session auth keeps the browsable API usable.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}


# --------------------------------------------------------------------------- #
# Djoser  ->  /api/users/ (register), /api/users/me/, /api/token/login/ (token)
# --------------------------------------------------------------------------- #
DJOSER = {
    "USER_ID_FIELD": "id",
    "LOGIN_FIELD": "username",
    "SERIALIZERS": {
        "user": "LittleLemonAPI.serializers.UserSerializer",
        "current_user": "LittleLemonAPI.serializers.UserSerializer",
    },
}
