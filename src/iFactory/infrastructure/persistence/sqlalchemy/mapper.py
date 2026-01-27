"""
Infrastructure Mapper for Database ORM.
Strictly bi-directional static mapping between Domain and Persistence.
No side effects, no database queries.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence
from uuid import uuid4

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.status_period import StatusPeriod

from .models import DeviceModel, StatusPeriodModel


class OrmDeviceMapper:
    """
    Translates between Domain Aggregates/Value Objects and SQLAlchemy Models.
    All methods are static and side-effect free.
    """

    # =========================================================================
    # Device Entity Mapping
    # =========================================================================

    @staticmethod
    def to_entity(model: Optional[DeviceModel]) -> Optional[Device]:
        """Convert ORM DeviceModel to Domain Device entity."""
        if model is None:
            return None

        try:
            device = Device.create(
                code=model.equip_code,
                raw_status=model.equip_status,
                last_update=model.last_update,
            )

            if model.name or model.description:
                device.update_metadata(
                    name=model.name,
                    description=model.description,
                )

            return device

        except Exception:
            return None

    @staticmethod
    def to_entities(models: Sequence[DeviceModel]) -> List[Device]:
        """Convert sequence of ORM models to Domain entities."""
        result = []
        for model in models:
            entity = OrmDeviceMapper.to_entity(model)
            if entity is not None:
                result.append(entity)
        return result

    @staticmethod
    def to_model(entity: Device) -> DeviceModel:
        """Convert Domain Device entity to ORM DeviceModel."""
        return DeviceModel(
            id=entity.code,
            equip_code=entity.code,
            equip_status=entity.status,
            last_update=entity.last_update or datetime.now(),
            is_active=entity.is_active,
            name=entity.name,
            description=entity.description,
        )

    @staticmethod
    def to_models(entities: Sequence[Device]) -> List[DeviceModel]:
        """Convert sequence of Domain entities to ORM models."""
        return [OrmDeviceMapper.to_model(e) for e in entities]

    # =========================================================================
    # StatusPeriod Value Object Mapping
    # =========================================================================

    @staticmethod
    def to_period_entity(model: Optional[StatusPeriodModel]) -> Optional[StatusPeriod]:
        """Convert ORM StatusPeriodModel to Domain StatusPeriod."""
        if model is None:
            return None

        try:
            return StatusPeriod.create(
                code=model.device_id,
                raw_status=model.status,
                start=model.start_time,
                end=model.end_time,
                id=model.id,
            )
        except Exception:
            return None

    @staticmethod
    def to_period_entities(models: Sequence[StatusPeriodModel]) -> List[StatusPeriod]:
        """Convert sequence of ORM models to Domain StatusPeriod objects."""
        result = []
        for model in models:
            period = OrmDeviceMapper.to_period_entity(model)
            if period is not None:
                result.append(period)
        return result

    @staticmethod
    def to_period_model(entity: StatusPeriod) -> StatusPeriodModel:
        """Convert Domain StatusPeriod to ORM StatusPeriodModel."""
        return StatusPeriodModel(
            id=entity.id or str(uuid4()),
            device_id=entity.device_code,
            status=entity.status_code,
            start_time=entity.start_time,
            end_time=entity.end_time,
        )

    @staticmethod
    def to_period_models(periods: Sequence[StatusPeriod]) -> List[StatusPeriodModel]:
        """Convert sequence of Domain StatusPeriod objects to ORM models."""
        return [OrmDeviceMapper.to_period_model(p) for p in periods]


__all__ = ["OrmDeviceMapper"]
