from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from src.application.interfaces.repository import IRepository
from src.domain.entities.device import Device
from src.infrastructure.database.orm_models import DeviceORM
from src.infrastructure.mappers.device_orm_mapper import to_domain, to_orm
from src.application.exceptions import ApplicationException


class SQLAlchemyDeviceRepository(IRepository[Device, str]):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: str) -> Optional[Device]:
        try:
            result = await self._session.execute(select(DeviceORM).filter_by(id=id))
            orm_device = result.scalars().first()
            if not orm_device:
                return None
            return to_domain(orm_device)
        except SQLAlchemyError as e:
            raise ApplicationException(f"Database error while fetching device: {str(e)}")

    async def save(self, entity: Device) -> None:
        try:
            orm_device = to_orm(entity)
            await self._session.merge(orm_device)
        except SQLAlchemyError as e:
            raise ApplicationException(f"Database error while saving device: {str(e)}")

    async def delete(self, entity: Device) -> None:
        try:
            orm_device = await self._session.get(DeviceORM, entity.id)
            if orm_device:
                await self._session.delete(orm_device)
        except SQLAlchemyError as e:
            raise ApplicationException(f"Database error while deleting device: {str(e)}")
