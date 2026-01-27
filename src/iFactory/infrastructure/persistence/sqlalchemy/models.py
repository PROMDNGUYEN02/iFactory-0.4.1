"""
SQLAlchemy ORM Models.
Pure database representation. No business logic.
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DeviceModel(Base):
    """
    Model đại diện cho bảng 'devices'.
    Đổi tên từ DeviceORM -> DeviceModel để khớp với Repository/Mapper.
    """

    __tablename__ = "devices"

    # Lưu ý: Các trường này phải khớp với Mapper
    id = Column(String(50), primary_key=True)
    equip_code = Column(String(50), nullable=False, unique=True)
    equip_status = Column(String(50), nullable=False)  # Lưu giá trị Enum dưới dạng String hoặc Int
    last_update = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)

    # Quan hệ 1-n với StatusPeriodModel
    status_periods = relationship("StatusPeriodModel", back_populates="device", cascade="all, delete-orphan")


class StatusPeriodModel(Base):
    """
    Model đại diện cho bảng 'status_periods'.
    Đổi tên từ StatusPeriodORM -> StatusPeriodModel.
    """

    __tablename__ = "status_periods"

    id = Column(String(50), primary_key=True)
    device_id = Column(String(50), ForeignKey("devices.id"), nullable=False)
    status = Column(String(20), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    # Quan hệ n-1 với DeviceModel
    device = relationship("DeviceModel", back_populates="status_periods")
