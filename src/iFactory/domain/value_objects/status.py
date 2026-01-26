from __future__ import annotations
from dataclasses import dataclass
from ..enums.device_status import DeviceStatus


@dataclass(frozen=True, slots=True)
class Status:
    """Value object wrapping the DeviceStatus enum with business logic capabilities."""

    device_status: DeviceStatus

    @classmethod
    def from_raw(cls, value: str | None) -> Status:
        return cls(DeviceStatus.from_business_term(value))

    @classmethod
    def unknown(cls) -> Status:
        return cls(DeviceStatus.UNKNOWN)

    @property
    def name(self) -> str:
        return self.device_status.value

    @property
    def is_running(self) -> bool:
        return self.device_status == DeviceStatus.RUNNING

    @property
    def requires_attention(self) -> bool:
        return self.device_status in (DeviceStatus.ALARM, DeviceStatus.STOPPED)

    @property
    def implies_downtime(self) -> bool:
        return self.device_status.implies_downtime

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Status):
            return self.device_status == other.device_status
        return False
