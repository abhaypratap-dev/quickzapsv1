from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import os
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "quickzaps-local-development-key")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "django_filters",
    "rest_framework",
    "drf_spectacular",
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


def env_list(name, default=""):
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def postgres_config_from_url(database_url=os.environ.get("DATABASE_URL", "postgres://quickzaps_user:abhay123@localhost:5432/quickzaps")):
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use postgres:// or postgresql:// for deployment.")

    query = parse_qs(parsed.query)
    options = {}
    sslmode = query.get("sslmode", [os.environ.get("DATABASE_SSLMODE", "")])[0]
    if sslmode:
        options["sslmode"] = sslmode

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": parsed.port or 5432,
        "CONN_MAX_AGE": int(os.environ.get("DATABASE_CONN_MAX_AGE", "60")),
        "OPTIONS": options,
    }


def postgres_config_from_env():
    name = os.environ.get("POSTGRES_DB")
    if not name:
        return None
    options = {}
    sslmode = os.environ.get("DATABASE_SSLMODE", "")
    if sslmode:
        options["sslmode"] = sslmode
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DATABASE_CONN_MAX_AGE", "60")),
        "OPTIONS": options,
    }


database_url=os.environ.get("DATABASE_URL", "postgres://quickzaps_user:abhay123@localhost:5432/quickzaps")
postgres_env_config = postgres_config_from_env()
if database_url:
    DATABASES = {"default": postgres_config_from_url(database_url)}
elif postgres_env_config:
    DATABASES = {"default": postgres_env_config}
else:
    if not DEBUG:
        raise ImproperlyConfigured("Set DATABASE_URL or POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD for production.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    origin
    for origin in env_list(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:19006,http://127.0.0.1:19006,http://localhost:8081,http://127.0.0.1:8081,http://localhost:8082,http://127.0.0.1:8082",
    )
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "QuickZaps API",
    "DESCRIPTION": "Django REST API for QuickZaps admin and user panels.",
    "VERSION": "0.1.0",
}

PARTNER_API_DUMMY_MODE = env_bool("PARTNER_API_DUMMY_MODE", True)
PARTNER_API_DUMMY_KEY = os.environ.get("PARTNER_API_DUMMY_KEY", "quickzaps-dummy-key")
PARTNER_API_DUMMY_USER_MOBILE = os.environ.get("PARTNER_API_DUMMY_USER_MOBILE", "9000000004")
PARTNER_API_TIMESTAMP_TOLERANCE_SECONDS = int(os.environ.get("PARTNER_API_TIMESTAMP_TOLERANCE_SECONDS", "600"))
PROVIDER_SANDBOX_MODE = env_bool("PROVIDER_SANDBOX_MODE", True)

FINGPAY_AEPS_DUMMY_MODE = env_bool("FINGPAY_AEPS_DUMMY_MODE", True)
FINGPAY_AEPS_BASE_URL = os.environ.get("FINGPAY_AEPS_BASE_URL", "https://fingpayap.tapits.in").rstrip("/")
FINGPAY_AEPS_ONBOARDING_URL = os.environ.get("FINGPAY_AEPS_ONBOARDING_URL", "").strip()
FINGPAY_AEPS_EKYC_BASE_URL = os.environ.get("FINGPAY_AEPS_EKYC_BASE_URL", "https://fpekyc.tapits.in").rstrip("/")
FINGPAY_AEPS_SUPER_MERCHANT_LOGIN_ID = os.environ.get("FINGPAY_AEPS_SUPER_MERCHANT_LOGIN_ID", "")
FINGPAY_AEPS_SUPER_MERCHANT_PASSWORD = os.environ.get("FINGPAY_AEPS_SUPER_MERCHANT_PASSWORD", "")
FINGPAY_AEPS_SUPER_MERCHANT_ID = int(os.environ.get("FINGPAY_AEPS_SUPER_MERCHANT_ID", "0") or "0")
FINGPAY_AEPS_SECRET_KEY = os.environ.get("FINGPAY_AEPS_SECRET_KEY", "")
FINGPAY_AEPS_PUBLIC_KEY_PEM = os.environ.get("FINGPAY_AEPS_PUBLIC_KEY_PEM", "")
FINGPAY_AEPS_PUBLIC_CERT_PATH = os.environ.get("FINGPAY_AEPS_PUBLIC_CERT_PATH", "")
FINGPAY_AEPS_DEFAULT_DEVICE_IMEI = os.environ.get("FINGPAY_AEPS_DEFAULT_DEVICE_IMEI", "")
FINGPAY_AEPS_DEFAULT_LATITUDE = os.environ.get("FINGPAY_AEPS_DEFAULT_LATITUDE", "28.6139000")
FINGPAY_AEPS_DEFAULT_LONGITUDE = os.environ.get("FINGPAY_AEPS_DEFAULT_LONGITUDE", "77.2090000")
FINGPAY_AEPS_DEFAULT_STATE_CODE = int(os.environ.get("FINGPAY_AEPS_DEFAULT_STATE_CODE", "9") or "9")
FINGPAY_AEPS_DEFAULT_COMPANY_TYPE = int(os.environ.get("FINGPAY_AEPS_DEFAULT_COMPANY_TYPE", "2") or "2")
FINGPAY_AEPS_TIMEOUT_SECONDS = int(os.environ.get("FINGPAY_AEPS_TIMEOUT_SECONDS", "45") or "45")

CASHFREE_DUMMY_MODE = env_bool("CASHFREE_DUMMY_MODE", True)
CASHFREE_ENVIRONMENT = os.environ.get("CASHFREE_ENVIRONMENT", "sandbox").strip().lower()
CASHFREE_CLIENT_ID = os.environ.get("CASHFREE_CLIENT_ID", "")
CASHFREE_CLIENT_SECRET = os.environ.get("CASHFREE_CLIENT_SECRET", "")
CASHFREE_BASE_URL = os.environ.get(
    "CASHFREE_BASE_URL",
    "https://sandbox.cashfree.com/verification" if CASHFREE_ENVIRONMENT != "production" else "https://api.cashfree.com/verification",
)
ONBOARDING_DEFAULT_PASSWORD = os.environ.get("ONBOARDING_DEFAULT_PASSWORD", "Demo@12345")
