# pylint: disable=redefined-outer-name
from typing import TYPE_CHECKING, Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from multilayer_settings.db import create_session_factory, dbsession_ctx
from multilayer_settings.orm import Base

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


@pytest.fixture(scope="class")
def in_memory_sqlite_db() -> "Engine":
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="class")
def sqlite_session_factory(
    in_memory_sqlite_db: "Engine",
) -> Generator["sessionmaker[Session]", None, None]:
    yield create_session_factory(in_memory_sqlite_db)


@pytest.fixture(name="dbsession", scope="class")
def _dbsession(sqlite_session_factory) -> Generator["Session", None, None]:
    session: "Session" = sqlite_session_factory()
    with dbsession_ctx(sqlite_session_factory, auto_commit=False) as session:
        try:
            yield session
        finally:
            session.rollback()
