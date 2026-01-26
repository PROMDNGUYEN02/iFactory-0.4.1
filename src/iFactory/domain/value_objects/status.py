from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Status:
    """
    Value object representing a canonical machine state.
    Strictly business definitions. No UI colors or strings allowed.
    """

    name: str

    _CANONICAL_STATES = {"unknown", "running", "shutdown", "stopped", "maintenance", "alarm"}

    def __post_init__(self):
        val = self.name.lower()
        if val not in self._CANONICAL_STATES:
            val = "unknown"
        object.__setattr__(self, "name", val)

    @classmethod
    def from_raw(cls, value: str | None) -> Status:
        """Maps shop-floor vernacular to canonical system states."""
        if not value:
            return cls.unknown()

        clean = str(value).strip().lower()

        aliases = {
            "run": "running",
            "active": "running",
            "on": "running",
            "off": "shutdown",
            "idle": "stopped",
            "stop": "stopped",
            "fault": "alarm",
            "error": "alarm",
            "pm": "maintenance",
        }

        canonical_name = aliases.get(clean, clean)
        return cls(canonical_name)

    @classmethod
    def unknown(cls) -> Status:
        return cls("unknown")

    @property
    def is_running(self) -> bool:
        return self.name == "running"

    @property
    def is_alarm(self) -> bool:
        return self.name == "alarm"

    @property
    def is_shutdown(self) -> bool:
        return self.name == "shutdown"

    @property
    def requires_attention(self) -> bool:
        return self.name in ("alarm", "stopped")

    @property
    def implies_downtime(self) -> bool:
        """Business rule: Determine if status constitutes machine downtime."""
        return self.name in ("shutdown", "maintenance", "stopped", "alarm")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Status):
            return self.name == other.name
        return False
