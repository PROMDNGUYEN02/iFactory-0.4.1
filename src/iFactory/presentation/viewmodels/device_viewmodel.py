from dataclasses import dataclass
from iFactory.application.dto.device_dto import DeviceSummaryDTO


@dataclass(frozen=True)
class DeviceViewModel:
    """
    Prepared data for Device Display.
    Includes formatted strings and color codes.
    """

    equipment_code: str
    status_display: str
    status_color: str
    last_updated: str

    @classmethod
    def from_dto(cls, dto: DeviceSummaryDTO) -> "DeviceViewModel":
        return cls(
            equipment_code=dto.equipment_code,
            status_display=dto.status_name.upper(),
            status_color=cls._map_color(dto.status_code),
            last_updated=dto.last_updated.strftime("%H:%M:%S"),
        )

    @staticmethod
    def _map_color(status_code: int) -> str:
        # Declarative mapping for UI purposes only
        # 1=Run (Green), 2=Shutdown (Gray), 3=Stop (Yellow), 5=Alarm (Red)
        mapping = {
            1: "#4CAF50",  # Green
            2: "#9E9E9E",  # Gray
            3: "#FFC107",  # Amber
            4: "#2196F3",  # Blue (Maint)
            5: "#F44336",  # Red
        }
        return mapping.get(status_code, "#9E9E9E")
