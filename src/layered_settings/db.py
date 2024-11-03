import contextlib
from typing import TYPE_CHECKING, Generator

from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


def create_session_factory(
    engine: "Engine",
    /,
    autoflush: bool = False,
    expire_on_commit: bool = False,
    **sessionmaker_kw,
) -> "sessionmaker[Session]":
    return sessionmaker(
        bind=engine,
        autoflush=autoflush,
        expire_on_commit=expire_on_commit,
        **sessionmaker_kw,
    )


@contextlib.contextmanager
def dbsession_ctx(
    session_factory: "sessionmaker[Session]", auto_commit: bool = True
) -> Generator["Session", None, None]:
    session: "Session" = session_factory()
    try:
        yield session
        if auto_commit:
            session.commit()
    except:  # pylint: disable=bare-except
        session.rollback()
