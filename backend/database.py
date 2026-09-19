import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import re
import urllib.parse

def sanitize_db_url(url: str) -> str:
    if not url or url.startswith("sqlite"):
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
        
    # Auto-conmutación de conexión directa IPv6 a Pooler IPv4 resiliente en Vercel
    match = re.search(r'@db\.([a-z0-9]+)\.supabase\.co(?::5432)?', url)
    if match:
        project_ref = match.group(1)
        url = url.replace(match.group(0), '@aws-0-us-east-2.pooler.supabase.com:5432')
        if f"postgres.{project_ref}" not in url and "://postgres:" in url:
            url = url.replace("://postgres:", f"://postgres.{project_ref}:", 1)
            
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
