from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from src.models import Base


engine = None


def init_db(db_url: str):
    global engine
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)


def get_db():
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    with Session(engine) as session:
        yield session
