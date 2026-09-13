import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def database_url() -> str:
    value = (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "").strip()
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    return value or f"sqlite:///{os.path.join(BASE_DIR, 'viral_place.db')}"


class Config:
    PRODUCTION = bool(os.environ.get("VERCEL") or os.environ.get("RENDER") or os.environ.get("APP_ENV") == "production")
    SECRET_KEY = os.environ.get("SECRET_KEY") or (None if PRODUCTION else secrets.token_hex(32))
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MAX_CONTENT_LENGTH = 64 * 1024
    MAX_FORM_MEMORY_SIZE = 64 * 1024
    MAX_FORM_PARTS = 80
    TRUSTED_HOSTS = list(filter(None, [os.environ.get("RENDER_EXTERNAL_HOSTNAME"), os.environ.get("VERCEL_URL"), os.environ.get("VERCEL_PROJECT_PRODUCTION_URL"), *os.environ.get("TRUSTED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")]))
    TRUST_PROXY_HEADERS = PRODUCTION
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_NAME = "__Host-briefvora_session" if PRODUCTION else "briefvora_session"
    SESSION_COOKIE_PATH = "/"
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = PRODUCTION
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_REFRESH_EACH_REQUEST = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_NAME = "__Host-briefvora_remember" if PRODUCTION else "briefvora_remember"
    REMEMBER_COOKIE_PATH = "/"
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = PRODUCTION
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 14
    PREFERRED_URL_SCHEME = "https" if PRODUCTION else "http"
    COMPANY_RIB = os.environ.get("COMPANY_RIB", "")
    COMPANY_BANK_NAME = os.environ.get("COMPANY_BANK_NAME", "")
    COMPANY_ACCOUNT_HOLDER = os.environ.get("COMPANY_ACCOUNT_HOLDER", "")
    COMPANY_BANK_CURRENCY = os.environ.get("COMPANY_BANK_CURRENCY", "mad").strip().lower()
    MARKETPLACE_CURRENCY = os.environ.get("MARKETPLACE_CURRENCY", "mad").strip().lower()
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")).rstrip("/")
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "")
    EMAIL_VERIFICATION_REQUIRED = os.environ.get("EMAIL_VERIFICATION_REQUIRED") == "1"
    POLICIES_PUBLISHED = os.environ.get("POLICIES_PUBLISHED") == "1"
    POLICY_VERSION = "2026-09-13"
    BUSINESS_LEGAL_NAME = os.environ.get("BUSINESS_LEGAL_NAME", "")
    BUSINESS_ADDRESS = os.environ.get("BUSINESS_ADDRESS", "")
    BUSINESS_REGISTRATION = os.environ.get("BUSINESS_REGISTRATION", "")
    PRIVACY_REGISTRATION = os.environ.get("PRIVACY_REGISTRATION", "")
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 2
    MAX_OFFER_AMOUNT = int(os.environ.get("MAX_OFFER_AMOUNT", os.environ.get("MAX_OFFER_USD", "1000000")))
