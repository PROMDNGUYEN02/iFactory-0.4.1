from dataclasses import dataclass
from datetime import datetime
from typing import List

from iFactory.application.dto.timeline_dto import TimelineDTO, GanttBarDTO


@dataclass(frozen=True)
class GanttBarViewModel:
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    color: str
    tooltip: str


@dataclass(frozen=True)
class GanttViewModel:
    equipment_code: str
    bars: List[GanttBarViewModel]
    window_start: datetime
    window_end: datetime

    @classmethod
    def from_dto(cls, dto: TimelineDTO) -> "GanttViewModel":
        bars_vm = []

        # Determine window from data or defaults
        if dto.bars:
            start = min(b.start_time for b in dto.bars)
            end = max(b.end_time for b in dto.bars)
        else:
            start = datetime.now()
            end = datetime.now()

        for bar in dto.bars:
            bars_vm.append(
                GanttBarViewModel(
                    start_time=bar.start_time,
                    end_time=bar.end_time,
                    duration_seconds=bar.duration_seconds,
                    color=cls._map_color(bar.status_code),
                    tooltip=f"{bar.status_name}: {bar.duration_seconds/60:.1f} min",
                )
            )

        return cls(equipment_code=dto.equipment_code, bars=bars_vm, window_start=start, window_end=end)

    @staticmethod
    def _map_color(status_code: int) -> str:
        # Duplicated mapping logic from DeviceViewModel
        # In a full system, this color map would be a shared UI config service
        mapping = {
            1: "#4CAF50",
            2: "#9E9E9E",
            3: "#FFC107",
            4: "#2196F3",
            5: "#F44336",
        }
        return mapping.get(status_code, "#9E9E9E")
