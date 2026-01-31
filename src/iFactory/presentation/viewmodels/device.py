# File: presentation/viewmodels/device.py
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class DeviceViewModel:
    device_id: str
    display_name: str
    status_code: int
    status_name: str
    status_color: str
    status_emoji: str
    is_running: bool
    requires_attention: bool
    last_update: Optional[str] = None
    input_count: int = 0
    output_count: int = 0
    error_count: int = 0
    oee: float = 0.0
    yield_rate: float = 0.0
    cycle_time: float = 0.0
    description: str = ""
    material_batch: str = "--"
    feeding_time: str = "--"
    last_error: Optional[str] = None

    @property
    def id(self) -> str:
        return self.device_id

    @property
    def formatted_oee(self) -> str:
        return f"{self.oee:.1f}%"

    @property
    def formatted_yield(self) -> str:
        return f"{self.yield_rate:.1f}%"

    @property
    def formatted_cycle_time(self) -> str:
        return f"{self.cycle_time:.2f}s"

    @staticmethod
    def empty(device_id: str) -> "DeviceViewModel":
        from ..constants.status import Status, StatusCode

        return DeviceViewModel(
            device_id=device_id,
            display_name=device_id,
            status_code=StatusCode.UNKNOWN,
            status_name=Status.get_name(StatusCode.UNKNOWN),
            status_color=Status.get_color(StatusCode.UNKNOWN),
            status_emoji=Status.get_emoji(StatusCode.UNKNOWN),
            is_running=False,
            requires_attention=False,
        )
