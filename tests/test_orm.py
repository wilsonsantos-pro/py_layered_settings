# pylint: disable=redefined-outer-name
import contextlib
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import TYPE_CHECKING, Callable, Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from multilayer_settings.orm import Base, Layer, MultilayerSetting

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


@pytest.fixture(scope="class")
def in_memory_sqlite_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@lru_cache
def setup_db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="class")
def sqlite_session_factory(
    in_memory_sqlite_db,
) -> Generator["sessionmaker[Session]", None, None]:
    yield sessionmaker(
        bind=in_memory_sqlite_db, autoflush=False, expire_on_commit=False
    )


def create_session_factory(engine: "Engine") -> "sessionmaker[Session]":
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(name="dbsession", scope="class")
def _dbsession(sqlite_session_factory) -> Generator["Session", None, None]:
    session: "Session" = sqlite_session_factory()
    with dbsession_ctx(sqlite_session_factory, auto_commit=False) as session:
        try:
            yield session
        finally:
            session.rollback()
    # TODO: add fixture that assert db is empty


SessionFactory = Callable[["Engine"], "sessionmaker[Session]"]


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


class Layers(int, Enum):
    SYSTEM = 1
    ACCOUNT = 2
    USER = 3


@dataclass
class User:
    id: int
    account_id: int


class TestMultilayerSetting:
    @classmethod
    def _create_layers(cls, dbsession: "Session"):
        cls.layer_system = Layer(name="system")
        dbsession.add(cls.layer_system)
        dbsession.flush()

        cls.layer_account = Layer(name="account", fallback_id=cls.layer_system.id)
        dbsession.add(cls.layer_account)
        dbsession.flush()

        cls.layer_user = Layer(name="user", fallback_id=cls.layer_account.id)
        dbsession.add(cls.layer_user)
        dbsession.flush()

    @classmethod
    def _create_accounts(cls):
        cls.account_1_id = 1
        cls.account_2_id = 2
        cls.account_3_id = 3
        cls.account_4_id = 4

    @classmethod
    def _create_users(cls):
        cls.user_1 = User(id=1, account_id=cls.account_1_id)
        cls.user_2 = User(id=2, account_id=cls.account_2_id)
        cls.user_3 = User(id=3, account_id=cls.account_3_id)

    @classmethod
    def _create_settings(cls, dbsession: "Session"):

        cls.system_setting = MultilayerSetting(
            name="lights",
            value="0",
            layer_id=cls.layer_system.id,
        )
        dbsession.add(cls.system_setting)

        cls.account_1_setting = MultilayerSetting(
            name="lights",
            value="10",
            layer_id=cls.layer_account.id,
            entity_id=1,
        )
        dbsession.add(cls.account_1_setting)

        cls.account_2_setting = MultilayerSetting(
            name="lights",
            value="20",
            layer_id=cls.layer_account.id,
            entity_id=2,
        )
        dbsession.add(cls.account_2_setting)

        # no setting for account 3

        cls.account_4_setting = MultilayerSetting(
            name="exclusive4",
            value="50",
            layer_id=cls.layer_account.id,
            entity_id=cls.account_4_id,
        )
        dbsession.add(cls.account_4_setting)

        cls.user_1_setting = MultilayerSetting(
            name="lights",
            value="70",
            layer_id=cls.layer_user.id,
            entity_id=cls.user_1.id,
            parent_id=cls.user_1.account_id,
        )
        dbsession.add(cls.user_1_setting)

        dbsession.flush()

    @classmethod
    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls, dbsession):
        cls._create_layers(dbsession)
        cls._create_accounts()
        cls._create_users()
        cls._create_settings(dbsession)
        yield

    def test_setting_default(self, dbsession: "Session"):
        """Get the setting's default.
        Expected: get system setting."""
        result = MultilayerSetting.get_setting_default(
            dbsession, self.system_setting.name
        )
        assert result
        assert result.value == self.system_setting.value
        assert result.id == self.system_setting.id

    def test_setting_default_does_not_exist(self, dbsession: "Session"):
        """The setting requested is not set, not even a default.
        Expected: None"""
        result = MultilayerSetting.get_setting_default(dbsession, "whoami")
        assert not result

    def test_account_setting_does_not_exist(self, dbsession: "Session"):
        """The setting requested for account is not set, not even a default.
        Expected: None"""
        result = MultilayerSetting.get_setting(
            dbsession, "whoami", Layers.ACCOUNT, entity_id=self.account_1_id
        )
        assert not result

    def test_user_setting_does_not_exist(self, dbsession: "Session"):
        """The setting requested for user is not set, not even a default.
        Expected: None"""
        result = MultilayerSetting.get_setting(
            dbsession,
            "whoami",
            Layers.USER,
            entity_id=self.user_1.id,
            parent_id=self.user_1.account_id,
        )
        assert not result

    def test_account_setting(self, dbsession: "Session"):
        """Two accounts, each account has its own setting set.
        Expected: get value for the corresponding account."""
        result = MultilayerSetting.get_setting(
            dbsession,
            self.account_1_setting.name,
            Layers.ACCOUNT,
            entity_id=self.account_1_id,
        )
        assert result
        assert result.value == self.account_1_setting.value
        assert result.id == self.account_1_setting.id

        result = MultilayerSetting.get_setting(
            dbsession,
            self.account_2_setting.name,
            Layers.ACCOUNT,
            entity_id=self.account_2_id,
        )
        assert result
        assert result.value == self.account_2_setting.value
        assert result.id == self.account_2_setting.id

    def test_account_without_value(self, dbsession: "Session"):
        """An account doesn't have the value set for the setting.
        Expected: get system setting."""
        result = MultilayerSetting.get_setting(
            dbsession,
            self.system_setting.name,
            Layers.ACCOUNT,
            entity_id=self.account_3_id,
        )
        assert result
        assert result.value == self.system_setting.value
        assert result.id == self.system_setting.id

    def test_account_value_and_default_does_not_exist(self, dbsession: "Session"):
        """The setting is only set on this account, default does not exist.
        Expected: get account setting."""
        result = MultilayerSetting.get_setting(
            dbsession,
            self.account_4_setting.name,
            Layers.ACCOUNT,
            entity_id=self.account_4_id,
        )
        assert result
        assert result.value == self.account_4_setting.value
        assert result.id == self.account_4_setting.id

    def test_user_with_account_setting(self, dbsession: "Session"):
        """User belongs to account #2. The account has value set, user not.
        Expected: get the user setting from the account value.
        """
        result = MultilayerSetting.get_setting(
            dbsession,
            self.account_2_setting.name,
            Layers.USER,
            entity_id=self.user_2.id,
            parent_id=self.user_2.account_id,
        )
        assert result
        assert result.value == self.account_2_setting.value
        assert result.id == self.account_2_setting.id

    def test_user_and_account_without_setting(self, dbsession: "Session"):
        """Both user and account don't have an explicit setting value set.
        Expected: get system setting.
        """
        result = MultilayerSetting.get_setting(
            dbsession,
            self.system_setting.name,
            Layers.USER,
            entity_id=self.user_3.id,
            parent_id=self.user_3.account_id,
        )
        assert result
        assert result.value == self.system_setting.value
        assert result.id == self.system_setting.id

    def test_user_setting(self, dbsession: "Session"):
        """User has the setting explicitly set.
        Expected: get user setting."""
        result = MultilayerSetting.get_setting(
            dbsession,
            self.user_1_setting.name,
            Layers.USER,
            entity_id=self.user_1.id,
            parent_id=self.user_1.account_id,
        )
        assert result
        assert result.value == self.user_1_setting.value
        assert result.id == self.user_1_setting.id
