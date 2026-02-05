# src/iFactory/presentation/constants/timing.py
"""
Timing Constants for UX Flow - COMPLETE VERSION.

Includes both legacy constants and new progressive loading timings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


# ============================================================================
# Legacy Constants (for backward compatibility)
# ============================================================================


class Timing:
    """Main timing constants class with all values."""

    # Legacy animation timings
    ANIMATION_DURATION_MS: Final[int] = 300
    DEVICE_POLL_INTERVAL_MS: Final[int] = 3000
    GANTT_POLL_INTERVAL_MS: Final[int] = 1000
    DEFERRED_LOAD_DELAY_MS: Final[int] = 50  # <-- This was missing!
    DEBOUNCE_DELAY_MS: Final[int] = 100

    # ========================================================================
    # Progressive Loading Timings
    # ========================================================================

    class Loading:
        """Progressive loading stage targets."""

        # Stage targets (milliseconds)
        SKELETON_TARGET_MS: Final[int] = 0  # Immediate
        STALE_TARGET_MS: Final[int] = 30  # 30ms
        FRESH_TARGET_MS: Final[int] = 150  # 150ms
        LIVE_TARGET_MS: Final[int] = 200  # 200ms

        # Maximum acceptable times
        SKELETON_MAX_MS: Final[int] = 16  # 1 frame
        STALE_MAX_MS: Final[int] = 50  # 50ms
        FRESH_MAX_MS: Final[int] = 300  # 300ms
        LIVE_MAX_MS: Final[int] = 500  # 500ms

        # Gantt chart loading
        GANTT_SKELETON_MS: Final[int] = 0  # Immediate
        GANTT_STALE_MS: Final[int] = 20  # 20ms
        GANTT_FRESH_MS: Final[int] = 250  # 250ms
        GANTT_LIVE_MS: Final[int] = 300  # 300ms

        # Detail panel loading (sections)
        PANEL_SKELETON_MS: Final[int] = 0  # Immediate
        PANEL_AVAILABILITY_MS: Final[int] = 100  # 100ms
        PANEL_MATERIALS_MS: Final[int] = 150  # 150ms
        PANEL_HISTORY_MS: Final[int] = 300  # 300ms
        PANEL_ALERTS_MS: Final[int] = 400  # 400ms
        PANEL_COMPLETE_MS: Final[int] = 500  # 500ms

    # ========================================================================
    # Animation Timings
    # ========================================================================

    class Animation:
        """Animation durations for smooth UX."""

        # Base durations (milliseconds)
        INSTANT: Final[int] = 0
        FAST: Final[int] = 100
        NORMAL: Final[int] = 200
        SLOW: Final[int] = 400
        VERY_SLOW: Final[int] = 600

        # Specific animations
        STATUS_CHANGE: Final[int] = 150  # Status color transition
        SELECTION: Final[int] = 100  # Selection highlight
        HOVER: Final[int] = 80  # Hover effect
        GLOW_PULSE: Final[int] = 500  # Alert pulse cycle

        # Panel animations
        PANEL_EXPAND: Final[int] = 250  # Right panel open
        PANEL_COLLAPSE: Final[int] = 200  # Right panel close
        SIDEBAR_TOGGLE: Final[int] = 200  # Sidebar toggle

        # Skeleton animations
        SKELETON_SHIMMER: Final[int] = 1500  # Shimmer cycle
        SKELETON_FADE_OUT: Final[int] = 150  # Fade to content

        # Toast animations
        TOAST_ENTER: Final[int] = 200  # Toast slide in
        TOAST_EXIT: Final[int] = 150  # Toast slide out

        # Zoom/Pan
        ZOOM_SMOOTH: Final[int] = 150  # Smooth zoom
        PAN_MOMENTUM: Final[int] = 300  # Pan momentum decay

    # ========================================================================
    # Debounce/Throttle Timings
    # ========================================================================

    class Debounce:
        """Debounce and throttle intervals."""

        # Search/filter
        SEARCH_INPUT: Final[int] = 300  # Search debounce
        FILTER_CHANGE: Final[int] = 200  # Filter debounce

        # Scroll
        SCROLL_HANDLER: Final[int] = 100  # Scroll event throttle
        SCROLL_END_DETECT: Final[int] = 150  # Detect scroll stop

        # Resize
        RESIZE_HANDLER: Final[int] = 100  # Resize throttle
        LAYOUT_RECALC: Final[int] = 150  # Layout recalculation

        # Device loading
        LOAD_DEBOUNCE: Final[int] = 150  # Load request debounce
        BATCH_COLLECT: Final[int] = 50  # Collect batch requests

        # State persistence
        STATE_SAVE: Final[int] = 1000  # Save state debounce

        # Click detection
        DOUBLE_CLICK_WINDOW: Final[int] = 250  # Double-click detection

    # ========================================================================
    # Cache Timings
    # ========================================================================

    class Cache:
        """Cache TTL (Time To Live) values."""

        # Device status cache
        DEVICE_FRESH_TTL: Final[int] = 5  # 5 seconds fresh
        DEVICE_STALE_TTL: Final[int] = 300  # 5 minutes stale

        # Gantt data cache
        GANTT_FRESH_TTL: Final[int] = 10  # 10 seconds fresh
        GANTT_STALE_TTL: Final[int] = 600  # 10 minutes stale

        # Material inputs cache
        MATERIAL_FRESH_TTL: Final[int] = 60  # 1 minute fresh
        MATERIAL_STALE_TTL: Final[int] = 3600  # 1 hour stale

        # Availability cache
        AVAILABILITY_FRESH_TTL: Final[int] = 30  # 30 seconds fresh
        AVAILABILITY_STALE_TTL: Final[int] = 300  # 5 minutes stale

        # History cache
        HISTORY_FRESH_TTL: Final[int] = 60  # 1 minute fresh
        HISTORY_STALE_TTL: Final[int] = 1800  # 30 minutes stale

        # Background refresh threshold (percentage of fresh TTL)
        REFRESH_THRESHOLD: Final[float] = 0.8  # Refresh at 80% of fresh TTL

    # ========================================================================
    # Update Intervals
    # ========================================================================

    class Update:
        """Periodic update intervals."""

        # Live updates
        LIVE_POLL_FAST: Final[int] = 1000  # 1 second (visible devices)
        LIVE_POLL_NORMAL: Final[int] = 3000  # 3 seconds (standard)
        LIVE_POLL_SLOW: Final[int] = 10000  # 10 seconds (background)

        # Health checks
        CONNECTION_CHECK: Final[int] = 5000  # 5 seconds
        STALE_CHECK: Final[int] = 10000  # 10 seconds
        CLEANUP_CHECK: Final[int] = 60000  # 1 minute

        # Sync intervals
        SYNC_INTERVAL: Final[int] = 3000  # 3 seconds
        SYNC_RETRY_MIN: Final[int] = 1000  # 1 second min
        SYNC_RETRY_MAX: Final[int] = 30000  # 30 seconds max

        # Panel refresh
        PANEL_REFRESH: Final[int] = 3000  # 3 seconds

    # ========================================================================
    # Viewport Timings
    # ========================================================================

    class Viewport:
        """Viewport and scroll-related timings."""

        # Prefetch
        PREFETCH_DISTANCE_PX: Final[int] = 200  # Prefetch zone distance
        PREFETCH_DELAY_MS: Final[int] = 50  # Delay after scroll stop

        # Visibility
        VISIBILITY_DEBOUNCE_MS: Final[int] = 100  # Visibility check debounce
        OFFSCREEN_PAUSE_DELAY_MS: Final[int] = 500  # Delay before pausing
        OFFSCREEN_CLEANUP_MS: Final[int] = 30000  # Cleanup after 30 seconds

        # Memory management
        MEMORY_CACHE_DURATION_MS: Final[int] = 30000  # Keep in memory 30 seconds

    # ========================================================================
    # Retry Timings
    # ========================================================================

    class Retry:
        """Retry and backoff timings."""

        # Base delays
        BASE_DELAY_MS: Final[int] = 1000  # 1 second base
        MAX_DELAY_MS: Final[int] = 30000  # 30 seconds max

        # Attempts
        MAX_ATTEMPTS: Final[int] = 3  # Maximum retry attempts

        # Exponential factor
        BACKOFF_MULTIPLIER: Final[float] = 2.0  # Double each retry
        JITTER_FACTOR: Final[float] = 0.25  # ±25% jitter

        # Cooldown
        ERROR_COOLDOWN_MS: Final[int] = 5000  # Cooldown after error
        CIRCUIT_BREAKER_RESET_MS: Final[int] = 30000  # Circuit reset time


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

# For code that imports these directly
LoadingTiming = Timing.Loading
AnimationTiming = Timing.Animation
DebounceTiming = Timing.Debounce
CacheTiming = Timing.Cache
UpdateInterval = Timing.Update
ViewportTiming = Timing.Viewport
RetryTiming = Timing.Retry


# ============================================================================
# Helper Functions
# ============================================================================


def calculate_backoff_delay(
    attempt: int,
    base_delay: int = None,
    max_delay: int = None,
    multiplier: float = None,
    jitter: float = None,
) -> int:
    """
    Calculate exponential backoff delay with jitter.

    Args:
        attempt: Current attempt number (1-based)
        base_delay: Base delay in milliseconds
        max_delay: Maximum delay in milliseconds
        multiplier: Exponential multiplier
        jitter: Jitter factor (0.0 to 1.0)

    Returns:
        Delay in milliseconds
    """
    import random

    # Use defaults from Retry class
    base_delay = base_delay or Timing.Retry.BASE_DELAY_MS
    max_delay = max_delay or Timing.Retry.MAX_DELAY_MS
    multiplier = multiplier or Timing.Retry.BACKOFF_MULTIPLIER
    jitter = jitter or Timing.Retry.JITTER_FACTOR

    delay = base_delay * (multiplier ** (attempt - 1))
    delay = min(delay, max_delay)

    # Apply jitter
    if jitter > 0:
        jitter_range = delay * jitter
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, int(delay))


def is_within_timing_budget(
    elapsed_ms: float,
    target_ms: int,
    tolerance: float = 0.2,
) -> bool:
    """
    Check if elapsed time is within acceptable range of target.

    Args:
        elapsed_ms: Actual elapsed time
        target_ms: Target time
        tolerance: Acceptable tolerance (0.0 to 1.0)

    Returns:
        True if within budget
    """
    max_allowed = target_ms * (1 + tolerance)
    return elapsed_ms <= max_allowed


__all__ = [
    # Main class
    "Timing",
    # Backward compatibility aliases
    "LoadingTiming",
    "AnimationTiming",
    "DebounceTiming",
    "CacheTiming",
    "UpdateInterval",
    "ViewportTiming",
    "RetryTiming",
    # Helper functions
    "calculate_backoff_delay",
    "is_within_timing_budget",
]
