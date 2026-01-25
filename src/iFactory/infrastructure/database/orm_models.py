from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DeviceORM(Base):
    __tablename__ = "devices"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    equipment_code = Column(String(50), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    status_periods = relationship("StatusPeriodORM", back_populates="device", cascade="all, delete-orphan")


class StatusPeriodORM(Base):
    __tablename__ = "status_periods"

    id = Column(String(50), primary_key=True)
    device_id = Column(String(50), ForeignKey("devices.id"), nullable=False)
    status = Column(String(20), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    device = relationship("DeviceORM", back_populates="status_periods")
