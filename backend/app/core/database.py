from collections.abc import Generator

from sqlalchemy import create_engine
from sqlmodel import Session

from app.core.config import settings

engine = create_engine(settings.database_url)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
