import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Si no hay variable DATABASE_URL (fase local), usa SQLite. En Vercel/Nube usará PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./omnipulse.db")

# Ajuste para compatibilidad con SQLite (hilos) y URLs antiguas de postgres://
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
