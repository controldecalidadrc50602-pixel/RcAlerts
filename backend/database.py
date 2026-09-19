import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import urllib.parse

def sanitize_db_url(url: str) -> str:
    if not url or url.startswith("sqlite"):
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    try:
        prefix, _, rest = url.partition("://")
        auth, at, host_part = rest.rpartition("@")
        if at and ":" in auth:
            user, _, pwd = auth.partition(":")
            encoded_pwd = urllib.parse.quote_plus(urllib.parse.unquote_plus(pwd))
            return f"{prefix}://{user}:{encoded_pwd}@{host_part}"
    except Exception:
        pass
    return url

# Detección de entorno serverless (Vercel / AWS Lambda)
is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
default_db = "sqlite:////tmp/omnipulse.db" if is_serverless else "sqlite:///./omnipulse.db"

# Si no hay variable DATABASE_URL, usa SQLite en ./ o /tmp. Con PostgreSQL (Supabase) usa el pooler.
DATABASE_URL = sanitize_db_url(os.getenv("DATABASE_URL", default_db))

# Ajuste para compatibilidad con SQLite (hilos) y URLs de postgresql://
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    connect_args = {}
    if "supabase" in DATABASE_URL and "sslmode" not in DATABASE_URL:
        connect_args["sslmode"] = "require"

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
