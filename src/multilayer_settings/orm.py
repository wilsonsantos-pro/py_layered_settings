from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Base(DeclarativeBase):
    pass


class Layer(Base):
    __tablename__ = "settings__layer"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    fallback_id: Mapped[Optional[int]] = mapped_column(ForeignKey("settings__layer.id"))

    # TODO: business rule::only one layer with fallback_id == None can exist
    # that's the default layer


class SettingGroup(Base):
    __tablename__ = "settings__group"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class MultilayerSetting(Base):
    __tablename__ = "settings__multilayer_setting"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(200))
    layer_id: Mapped[int] = mapped_column(ForeignKey("settings__layer.id"))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("settings__group.id"))

    @staticmethod
    def get_setting(
        dbsession: "Session",
        name: str,
        layer_id: int,
        entity_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> Optional["MultilayerSetting"]:
        return MultilayerSetting._get_setting(
            dbsession, name, layer_id, entity_id, group_id
        )

    @staticmethod
    def get_setting_default(
        dbsession: "Session",
        name: str,
    ) -> Optional["MultilayerSetting"]:
        layer_stmt = select(Layer).where(Layer.fallback_id.is_(None))
        layer = dbsession.scalars(layer_stmt).first()
        if layer:
            return MultilayerSetting._get_setting(dbsession, name, layer.id)
        return None

    @staticmethod
    def _get_setting(
        dbsession: "Session",
        name: str,
        layer_id: int,
        entity_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> Optional["MultilayerSetting"]:
        where_clause = [
            MultilayerSetting.name == name,
            MultilayerSetting.layer_id == layer_id,
        ]
        if group_id:
            where_clause.append(MultilayerSetting.group_id == group_id)
        else:
            where_clause.append(MultilayerSetting.group_id.is_(None))
        if entity_id:
            where_clause.append(MultilayerSetting.entity_id == entity_id)
        stmt = select(MultilayerSetting).where(*where_clause)
        result = dbsession.scalars(stmt).first()

        if not result and (entity_id or group_id):
            layer_stmt = select(Layer).where(Layer.id == layer_id)
            layer = dbsession.scalars(layer_stmt).first()

            if layer:
                if layer.fallback_id:
                    return MultilayerSetting._get_setting(
                        dbsession, name, layer.fallback_id, group_id=group_id
                    )
                # it's the last/default layer
                return MultilayerSetting._get_setting(
                    dbsession,
                    name,
                    layer.id,
                )
            return None

        return result
