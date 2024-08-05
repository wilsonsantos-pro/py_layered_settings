# pylint: disable=redefined-outer-name
import contextlib
from enum import Enum
from functools import lru_cache
from typing import TYPE_CHECKING, Callable, Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from multilayer_settings.orm import (Base, Layer, MultilayerSetting,
                                     SettingGroup)

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
    except:
        session.rollback()


class Layers(int, Enum):
    SYSTEM = 1
    ACCOUNT = 2
    USER = 3


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
    def _create_groups(cls, dbsession: "Session"):
        # In this case we create one group per account, so effectively group == account
        cls.account_1 = SettingGroup(name="Account 1")
        dbsession.add(cls.account_1)
        cls.account_2 = SettingGroup(name="Account 2")
        dbsession.add(cls.account_2)
        dbsession.flush()

    @classmethod
    def _create_settings(cls, dbsession: "Session"):
        cls.system_setting = MultilayerSetting(
            name="lights", value="on", layer_id=cls.layer_system.id
        )
        dbsession.add(cls.system_setting)

        cls.account_1_setting = MultilayerSetting(
            name="lights",
            value="on",
            layer_id=cls.layer_account.id,
            entity_id=1,
            group_id=cls.account_1.id,
        )
        dbsession.add(cls.account_1_setting)

        cls.account_2_setting = MultilayerSetting(
            name="lights",
            value="off",
            layer_id=cls.layer_account.id,
            entity_id=2,
            group_id=cls.account_2.id,
        )
        dbsession.add(cls.account_2_setting)

        cls.account_4_setting = MultilayerSetting(
            name="exclusive4",
            value="50",
            layer_id=cls.layer_account.id,
            entity_id=4,
            group_id=4,
        )
        dbsession.add(cls.account_4_setting)

        dbsession.flush()

    @pytest.fixture(scope="class", autouse=True)
    def setup_class(cls, dbsession):
        cls._create_layers(dbsession)
        cls._create_groups(dbsession)
        cls._create_settings(dbsession)
        yield

    def test_setting_default(self, dbsession: "Session"):
        """Get the setting's default.
        Expected: get system setting."""
        result = MultilayerSetting.get_setting_default(dbsession, "lights")
        assert result
        assert result.value == "on"
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
            dbsession, "whoami", Layers.ACCOUNT, entity_id=1
        )
        assert not result

    def test_user_setting_does_not_exist(self, dbsession: "Session"):
        """The setting requested for user is not set, not even a default.
        Expected: None"""
        result = MultilayerSetting.get_setting(
            dbsession, "whoami", Layers.USER, entity_id=1, group_id=1
        )
        assert not result

    def test_account_setting(self, dbsession: "Session"):
        """Two accounts (groups), each account has its own setting set.
        Expected: get system for the corresponding account."""
        result = MultilayerSetting.get_setting(
            dbsession, "lights", Layers.ACCOUNT, group_id=1
        )
        assert result
        assert result.value == "on"
        assert result.id == self.account_1_setting.id

        result = MultilayerSetting.get_setting(
            dbsession, "lights", Layers.ACCOUNT, group_id=2
        )
        assert result
        assert result.value == "off"
        assert result.id == self.account_2_setting.id

    def test_account_without_value(self, dbsession: "Session"):
        """An account doesn't have the value set for the setting.
        Expected: get system setting."""
        result = MultilayerSetting.get_setting(
            dbsession, "lights", Layers.ACCOUNT, entity_id=3, group_id=3  # account 3
        )
        assert result
        assert result.value == "on"
        assert result.id == self.system_setting.id

    def test_account_default_does_not_exist(self, dbsession: "Session"):
        """The setting is only set on this account, default does not exist.
        Expected: get account setting."""
        result = MultilayerSetting.get_setting(
            dbsession,
            "exclusive4",
            Layers.ACCOUNT,
            entity_id=4,
            group_id=4,
        )
        assert result
        assert result.value == "50"
        assert result.id == self.account_4_setting.id

    def test_user_with_account_setting(self, dbsession: "Session"):
        """User belongs to account (group) #2. The account has value set, user not.
        Expected: get the user setting from the account value.
        """
        result = MultilayerSetting.get_setting(
            dbsession,
            "lights",
            Layers.USER,
            entity_id=1,
            group_id=self.account_2.id,
        )
        assert result
        assert result.value == "off"
        assert result.id == self.account_2_setting.id

    def test_user_and_account_without_setting(self, dbsession: "Session"):
        """Both user and account don't have an explicit setting value set.
        Expected: get system setting.
        """
        result = MultilayerSetting.get_setting(
            dbsession, "lights", Layers.USER, entity_id=2, group_id=3  # account #3
        )
        assert result
        assert result.value == "on"
        assert result.id == self.system_setting.id
