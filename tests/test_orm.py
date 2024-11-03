# pylint: disable=redefined-outer-name
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import TYPE_CHECKING, Any, Optional

import pytest

from layered_settings.orm import Layer, LayeredSetting
from tests.random_data import random_int

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Layers(int, Enum):
    SYSTEM = 1
    ACCOUNT = 2
    GROUP = 3
    USER = 4


class Settings(str, Enum):
    lights = "lights"


@dataclass
class User:
    id: int
    account_id: int
    group_id: Optional[int] = None


@dataclass
class UserSettingsRepository:
    dbsession: "Session"
    user: User

    @property
    def lights(self):
        return self.get(Settings.lights)

    def get(self, name: Settings) -> Any:
        return LayeredSetting.get_setting(
            self.dbsession,
            name,
            Layers.USER,
            entity_id=self.user.id,
            parent_ids=[self.user.group_id, self.user.account_id],
        )


@dataclass
class SettingsRepository:
    dbsession: "Session"

    @property
    def users(self) -> partial[UserSettingsRepository]:
        return partial(UserSettingsRepository, self.dbsession)


@dataclass
class Group:
    id: int
    account_id: int


class TestLayeredSetting:
    @classmethod
    def _create_layers(cls, dbsession: "Session"):
        cls.layer_system = Layer(id=Layers.SYSTEM, name="system")
        dbsession.add(cls.layer_system)
        dbsession.flush()

        cls.layer_account = Layer(
            id=Layers.ACCOUNT, name="account", fallback_id=cls.layer_system.id
        )
        dbsession.add(cls.layer_account)
        dbsession.flush()

        cls.layer_group = Layer(
            id=Layers.GROUP, name="group", fallback_id=cls.layer_account.id
        )
        dbsession.add(cls.layer_group)
        dbsession.flush()

        cls.layer_user = Layer(
            id=Layers.USER, name="user", fallback_id=cls.layer_group.id
        )
        dbsession.add(cls.layer_user)
        dbsession.flush()

    @classmethod
    def _create_accounts(cls):
        cls.account_1_id = random_int()
        cls.account_2_id = random_int()
        cls.account_3_id = random_int()
        cls.account_4_id = random_int()

    @classmethod
    def _create_users(cls):
        cls.group_2 = Group(id=random_int(), account_id=cls.account_2_id)
        cls.group_4 = Group(id=random_int(), account_id=cls.account_4_id)
        cls.user_1 = User(id=random_int(), account_id=cls.account_1_id)
        cls.user_2 = User(
            id=random_int(), account_id=cls.account_2_id, group_id=cls.group_2.id
        )
        cls.user_3 = User(id=random_int(), account_id=cls.account_3_id)
        cls.user_4 = User(id=random_int(), account_id=cls.account_4_id)

    @classmethod
    def _create_settings(cls, dbsession: "Session"):

        cls.system_setting = LayeredSetting(
            name=Settings.lights,
            value="0",
            layer_id=cls.layer_system.id,
        )
        dbsession.add(cls.system_setting)
        dbsession.flush()

        cls.account_1_setting = LayeredSetting(
            name=Settings.lights,
            value="10",
            layer_id=cls.layer_account.id,
            entity_id=cls.account_1_id,
        )
        dbsession.add(cls.account_1_setting)
        dbsession.flush()

        cls.account_2_setting = LayeredSetting(
            name=Settings.lights,
            value="a20",
            layer_id=cls.layer_account.id,
            entity_id=cls.account_2_id,
        )
        dbsession.add(cls.account_2_setting)
        dbsession.flush()

        # no setting for account 3

        cls.account_4_setting = LayeredSetting(
            name="exclusive4",
            value="50",
            layer_id=cls.layer_account.id,
            entity_id=cls.account_4_id,
        )
        dbsession.add(cls.account_4_setting)
        dbsession.flush()

        cls.user_1_setting = LayeredSetting(
            name=Settings.lights,
            value="70",
            layer_id=cls.layer_user.id,
            entity_id=cls.user_1.id,
            parent_id=cls.user_1.account_id,
        )
        dbsession.add(cls.user_1_setting)
        dbsession.flush()

        cls.group_2_setting = LayeredSetting(
            name=Settings.lights,
            value="g20",
            layer_id=cls.layer_group.id,
            entity_id=cls.group_2.id,
            parent_id=cls.group_2.account_id,
        )
        dbsession.add(cls.group_2_setting)
        dbsession.flush()

        cls.group_4_setting = LayeredSetting(
            name=Settings.lights,
            value="g40",
            layer_id=cls.layer_group.id,
            entity_id=cls.group_4.id,
            parent_id=cls.group_4.account_id,
        )
        dbsession.add(cls.group_4_setting)
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
        result = LayeredSetting.get_setting(
            dbsession, self.system_setting.name, Layers.SYSTEM
        )
        assert result
        assert result.value == self.system_setting.value
        assert result.id == self.system_setting.id

    def test_setting_default_does_not_exist(self, dbsession: "Session"):
        """The setting requested is not set, not even a default.
        Expected: None"""
        result = LayeredSetting.get_setting(dbsession, "whoami", Layers.SYSTEM)
        assert not result

    def test_account_setting_does_not_exist(self, dbsession: "Session"):
        """The setting requested for account is not set, not even a default.
        Expected: None"""
        result = LayeredSetting.get_setting(
            dbsession, "whoami", Layers.ACCOUNT, entity_id=self.account_1_id
        )
        assert not result

    def test_user_setting_does_not_exist(self, dbsession: "Session"):
        """The setting requested for user is not set, not even a default.
        Expected: None"""
        result = LayeredSetting.get_setting(
            dbsession,
            "whoami",
            Layers.USER,
            entity_id=self.user_1.id,
            parent_ids=[self.user_1.group_id, self.user_1.account_id],
        )
        assert not result

    def test_account_setting(self, dbsession: "Session"):
        """Two accounts, each account has its own setting set.
        Expected: get value for the corresponding account."""
        result = LayeredSetting.get_setting(
            dbsession,
            self.account_1_setting.name,
            Layers.ACCOUNT,
            entity_id=self.account_1_id,
        )
        assert result
        assert result.value == self.account_1_setting.value
        assert result.id == self.account_1_setting.id

        result = LayeredSetting.get_setting(
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
        result = LayeredSetting.get_setting(
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
        result = LayeredSetting.get_setting(
            dbsession,
            self.account_4_setting.name,
            Layers.ACCOUNT,
            entity_id=self.account_4_id,
        )
        assert result
        assert result.value == self.account_4_setting.value
        assert result.id == self.account_4_setting.id

    def test_user_with_account_setting(self, dbsession: "Session"):
        """The account has value set, user and group not.
        Expected: get account setting.
        """
        result = LayeredSetting.get_setting(
            dbsession,
            self.account_4_setting.name,
            Layers.USER,
            entity_id=self.user_4.id,
            parent_ids=[self.user_4.group_id, self.user_4.account_id],
        )
        assert result
        assert result.value == self.account_4_setting.value
        assert result.id == self.account_4_setting.id

    def test_user_with_account_and_group_setting(self, dbsession: "Session"):
        """The account and group have value set, user not.
        Expected: get group setting.
        """
        result = LayeredSetting.get_setting(
            dbsession,
            self.account_2_setting.name,
            Layers.USER,
            entity_id=self.user_2.id,
            parent_ids=[self.user_2.group_id, self.user_2.account_id],
        )
        assert result
        assert result.value == self.group_2_setting.value
        assert result.id == self.group_2_setting.id

    def test_user_and_account_without_setting(self, dbsession: "Session"):
        """User, Group and Account don't have an explicit setting value set.
        Expected: get system setting.
        """
        result = LayeredSetting.get_setting(
            dbsession,
            self.system_setting.name,
            Layers.USER,
            entity_id=self.user_3.id,
            parent_ids=[self.user_3.group_id, self.user_3.account_id],
        )
        assert result
        assert result.value == self.system_setting.value
        assert result.id == self.system_setting.id

    def test_user_setting(self, dbsession: "Session"):
        """User has the setting explicitly set.
        Expected: get user setting."""
        result = LayeredSetting.get_setting(
            dbsession,
            self.user_1_setting.name,
            Layers.USER,
            entity_id=self.user_1.id,
            parent_ids=[self.user_1.group_id, self.user_1.account_id],
        )
        assert result
        assert result.value == self.user_1_setting.value
        assert result.id == self.user_1_setting.id

    def test_user_setting_repo(self, dbsession: "Session"):
        """User has the setting explicitly set.
        Expected: get user setting."""
        repo = UserSettingsRepository(dbsession, self.user_1)
        result = repo.lights
        assert result
        assert result.value == self.user_1_setting.value
        assert result.id == self.user_1_setting.id

    def test_user_setting_generic_repo(self, dbsession: "Session"):
        """User has the setting explicitly set.
        Expected: get user setting."""
        repo = SettingsRepository(dbsession)
        result = repo.users(self.user_1).lights
        assert result
        assert result.value == self.user_1_setting.value
        assert result.id == self.user_1_setting.id

        # OR

        result = repo.users(self.user_1).get(Settings.lights)
        assert result.id == self.user_1_setting.id
