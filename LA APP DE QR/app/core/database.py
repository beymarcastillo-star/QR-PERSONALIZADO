from sqlalchemy import text
from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

def _migrar() -> None:
    """Agrega las columnas nuevas a una base SQLite creada con la versión anterior."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    nuevas = {"style": "TEXT DEFAULT 'cuadrado'", "shape": "TEXT DEFAULT 'ninguna'",
              "color": "TEXT DEFAULT '#111827'", "ref_image": "TEXT", "qr_file": "TEXT"}
    with engine.begin() as conn:
        existentes = {fila[1] for fila in conn.execute(text("PRAGMA table_info(qritem)"))}
        if not existentes:
            return
        for nombre, definicion in nuevas.items():
            if nombre not in existentes:
                conn.execute(text(f"ALTER TABLE qritem ADD COLUMN {nombre} {definicion}"))

def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrar()

def get_session():
    with Session(engine) as session:
        yield session