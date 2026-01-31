# File: presentation/constants/timing.py
from typing import Final


class Timing:
    ANIMATION_DURATION_MS: Final[int] = 300
    DEVICE_POLL_INTERVAL_MS: Final[int] = 3000
    GANTT_POLL_INTERVAL_MS: Final[int] = 1000
    DEFERRED_LOAD_DELAY_MS: Final[int] = 50
    DEBOUNCE_DELAY_MS: Final[int] = 100


__all__ = ["Timing"]
