import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "zafirah.db"

raw_url = os.environ.get("DATABASE_URL", "").strip()
if raw_url:
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://"):]
    if raw_url.startswith("postgresql://"):
        raw_url = "postgresql+psycopg://" + raw_url[len("postgresql://"):]
    DATABASE_URL = raw_url
    IS_SQLITE = False
else:
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    IS_SQLITE = True

class Base(DeclarativeBase):
    pass

engine_kwargs = {"pool_pre_ping": True}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
