# app/db.py
import os
from sqlmodel import SQLModel, create_engine, Session

def _normalize_db_url(url: str) -> str:
    # Railway 可能給 postgres:// 但 SQLAlchemy 要 postgresql://
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL:
    DATABASE_URL = _normalize_db_url(DATABASE_URL)
else:
    # 本機開發用
    DATABASE_URL = "sqlite:///./greenpoints.db"

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

def init_db():
    # 只會建立不存在的表，不會刪資料
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session