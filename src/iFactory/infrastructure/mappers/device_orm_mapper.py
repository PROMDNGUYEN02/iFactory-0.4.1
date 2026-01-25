from src.domain.entities.device import Device
from src.infrastructure.database.orm_models import DeviceORM


def to_domain(orm_device: DeviceORM) -> Device:
    return Device(
        id=orm_device.id,
        name=orm_device.name,
        equipment_code=orm_device.equipment_code,
        is_active=orm_device.is_active,
        created_at=orm_device.created_at,
        updated_at=orm_device.updated_at,
    )


def to_orm(device: Device) -> DeviceORM:
    return DeviceORM(
        id=device.id,
        name=device.name,
        equipment_code=device.equipment_code,
        is_active=device.is_active,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )
