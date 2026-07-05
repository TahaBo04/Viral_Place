import os

from dotenv import load_dotenv


load_dotenv()


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def database_url() -> str:
    value = (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "").strip()
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    return value or f"sqlite:///{os.path.join(BASE_DIR, 'viral_place.db')}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "viral-place-local-development-key")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_NAME = "__Host-viral_place_session" if os.environ.get("VERCEL") else "viral_place_session"
    SESSION_COOKIE_PATH = "/"
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = bool(os.environ.get("VERCEL"))
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_NAME = "__Host-viral_place_remember" if os.environ.get("VERCEL") else "viral_place_remember"
    REMEMBER_COOKIE_PATH = "/"
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = bool(os.environ.get("VERCEL"))
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 14
    PREFERRED_URL_SCHEME = "https" if os.environ.get("VERCEL") else "http"
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 2
