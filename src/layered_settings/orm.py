from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Base(DeclarativeBase):
    pass


class Layer(Base):
    __tablename__ = "settings__layer"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    fallback_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("settings__layer.id"), nullable=True
    )

    # TODO(business rule) only one layer with fallback_id == None can exist
    # that's the default layer


class LayeredSetting(Base):
    __tablename__ = "settings__layered_setting"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    layer_id: Mapped[int] = mapped_column(
        ForeignKey("settings__layer.id"), nullable=False
    )
    # entity_id is null to allow a "default" setting
    # TODO(business rule) don't allow setting creation for entity_id == None, unless
    # it's the default layer
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # parent is the entity in the "upper" layer
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"id={self.id},name={self.name},value={self.value},"
            f"layer_id={self.layer_id},entity_id={self.entity_id},"
            f"parent_id={self.parent_id}"
        )

    @staticmethod
    def get_setting(
        dbsession: "Session",
        name: str,
        layer_id: int,
        entity_id: Optional[int] = None,
        parent_ids: Optional[List[Optional[int]]] = None,
    ) -> Optional["LayeredSetting"]:
        where_clause = [
            LayeredSetting.name == name,
            LayeredSetting.layer_id == layer_id,
        ]
        if entity_id:
            where_clause.append(LayeredSetting.entity_id == entity_id)
        else:
            where_clause.append(LayeredSetting.entity_id.is_(None))

        stmt = select(LayeredSetting).where(*where_clause)
        result = dbsession.scalars(stmt).first()

        # "and entity_id or parent_ids" guarantees that we stop when it's the last layer
        if not result and (entity_id or parent_ids):
            if parent_ids:
                layer_stmt = select(Layer).where(Layer.id == layer_id)
                layer = dbsession.scalars(layer_stmt).first()

                if layer and layer.fallback_id:
                    parent_id = parent_ids[0]
                    parent_ids = parent_ids[1:]

                    return LayeredSetting.get_setting(
                        dbsession,
                        name,
                        layer.fallback_id,
                        entity_id=parent_id,
                        parent_ids=parent_ids,
                    )

            # it's the last/default layer
            layer_stmt = select(Layer).where(Layer.fallback_id.is_(None))
            default_layer = dbsession.scalars(layer_stmt).first()
            if default_layer:
                return LayeredSetting.get_setting(
                    dbsession,
                    name,
                    default_layer.id,
                )
            return None

        return result
