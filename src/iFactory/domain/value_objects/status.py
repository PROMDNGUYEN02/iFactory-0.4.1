from __future__ import annotations

from dataclasses import dataclass

from ..enums.device_status import DeviceStatus


@dataclass(frozen=True, slots=True)
class Status:
    device_status: DeviceStatus

    @classmethod
    def from_code(cls, code: str | None) -> "Status":
        return cls(DeviceStatus.from_code(code))

    @classmethod
    def unknown(cls) -> "Status":
        return cls(DeviceStatus.UNKNOWN)

    @classmethod
    def running(cls) -> "Status":
        return cls(DeviceStatus.RUNNING)

    @property
    def code(self) -> str:
        return self.device_status.code

    @property
    def name(self) -> str:
        return self.device_status.internal_name

    @property
    def is_running(self) -> bool:
        return self.device_status == DeviceStatus.RUNNING

    @property
    def requires_attention(self) -> bool:
        return self.device_status in (DeviceStatus.ALARM, DeviceStatus.STOP)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Status):
            return self.device_status == other.device_status
        if isinstance(other, DeviceStatus):
            return self.device_status == other
        return False

    def __hash__(self) -> int:
        return hash(self.device_status)
