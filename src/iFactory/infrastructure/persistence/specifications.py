# src/infrastructure/persistence/specifications.py
"""
Specification Pattern for type-safe, composable queries.

Features:
- Type-safe query building
- Composable with AND, OR, NOT
- Reusable across repositories
- SQL-optimized generation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Generic, List, Optional, Sequence, Type, TypeVar, Union

from sqlalchemy import and_, or_, not_, select, Select
from sqlalchemy.sql.elements import BinaryExpression

T = TypeVar("T")
TModel = TypeVar("TModel")


# ============================================================================
# Base Specification
# ============================================================================


class Specification(ABC, Generic[TModel]):
    """
    Abstract base for specifications.

    A specification encapsulates a query criterion that can be:
    - Evaluated against entities
    - Combined with other specifications
    - Converted to SQL expressions

    Usage:
        # Define specification
        class ActiveDevices(Specification[DeviceModel]):
            def to_expression(self) -> BinaryExpression:
                return DeviceModel.is_active == True

        # Compose specifications
        spec = ActiveDevices() & RunningStatus()

        # Use in repository
        devices = await repo.find_by_spec(spec)
    """

    @abstractmethod
    def to_expression(self) -> BinaryExpression:
        """Convert to SQLAlchemy expression."""
        pass

    def is_satisfied_by(self, entity: TModel) -> bool:
        """Check if entity satisfies this specification."""
        # Default implementation for in-memory filtering
        # Override for specific logic
        raise NotImplementedError("Override is_satisfied_by for in-memory filtering")

    def __and__(self, other: "Specification[TModel]") -> "AndSpecification[TModel]":
        return AndSpecification(self, other)

    def __or__(self, other: "Specification[TModel]") -> "OrSpecification[TModel]":
        return OrSpecification(self, other)

    def __invert__(self) -> "NotSpecification[TModel]":
        return NotSpecification(self)


class AndSpecification(Specification[TModel]):
    """Combines two specifications with AND."""

    def __init__(
        self,
        left: Specification[TModel],
        right: Specification[TModel],
    ) -> None:
        self._left = left
        self._right = right

    def to_expression(self) -> BinaryExpression:
        return and_(
            self._left.to_expression(),
            self._right.to_expression(),
        )

    def is_satisfied_by(self, entity: TModel) -> bool:
        return self._left.is_satisfied_by(entity) and self._right.is_satisfied_by(entity)


class OrSpecification(Specification[TModel]):
    """Combines two specifications with OR."""

    def __init__(
        self,
        left: Specification[TModel],
        right: Specification[TModel],
    ) -> None:
        self._left = left
        self._right = right

    def to_expression(self) -> BinaryExpression:
        return or_(
            self._left.to_expression(),
            self._right.to_expression(),
        )

    def is_satisfied_by(self, entity: TModel) -> bool:
        return self._left.is_satisfied_by(entity) or self._right.is_satisfied_by(entity)


class NotSpecification(Specification[TModel]):
    """Negates a specification."""

    def __init__(self, spec: Specification[TModel]) -> None:
        self._spec = spec

    def to_expression(self) -> BinaryExpression:
        return not_(self._spec.to_expression())

    def is_satisfied_by(self, entity: TModel) -> bool:
        return not self._spec.is_satisfied_by(entity)


# ============================================================================
# Device Specifications
# ============================================================================

from iFactory.infrastructure.persistence.sqlalchemy.models import (
    DeviceModel,
    StatusHistoryModel,
)


class DeviceByCode(Specification[DeviceModel]):
    """Specification for device by equipment code."""

    def __init__(self, code: str) -> None:
        self._code = code.upper()

    def to_expression(self) -> BinaryExpression:
        return DeviceModel.equip_code == self._code


class DeviceByCodeIn(Specification[DeviceModel]):
    """Specification for devices with codes in list."""

    def __init__(self, codes: List[str]) -> None:
        self._codes = [c.upper() for c in codes]

    def to_expression(self) -> BinaryExpression:
        return DeviceModel.equip_code.in_(self._codes)


class ActiveDevices(Specification[DeviceModel]):
    """Specification for active devices."""

    def to_expression(self) -> BinaryExpression:
        return and_(
            DeviceModel.is_active == True,
            DeviceModel.is_deleted == False,
        )


class DeviceByStatus(Specification[DeviceModel]):
    """Specification for devices with specific status."""

    def __init__(self, status: int) -> None:
        self._status = status

    def to_expression(self) -> BinaryExpression:
        return DeviceModel.equip_status == self._status


class DevicesWithAlarm(Specification[DeviceModel]):
    """Specification for devices in alarm state."""

    ALARM_STATUS = 5

    def to_expression(self) -> BinaryExpression:
        return DeviceModel.equip_status == self.ALARM_STATUS


class DevicesUpdatedAfter(Specification[DeviceModel]):
    """Specification for devices updated after a timestamp."""

    def __init__(self, after: datetime) -> None:
        self._after = after

    def to_expression(self) -> BinaryExpression:
        return DeviceModel.last_update >= self._after


class DevicesNotUpdatedSince(Specification[DeviceModel]):
    """Specification for stale devices (not updated recently)."""

    def __init__(self, since: datetime) -> None:
        self._since = since

    def to_expression(self) -> BinaryExpression:
        return or_(
            DeviceModel.last_update < self._since,
            DeviceModel.last_update == None,
        )


# ============================================================================
# History Specifications
# ============================================================================


class HistoryByDevice(Specification[StatusHistoryModel]):
    """Specification for history by device code."""

    def __init__(self, code: str) -> None:
        self._code = code.upper()

    def to_expression(self) -> BinaryExpression:
        return StatusHistoryModel.equip_code == self._code


class HistoryInTimeRange(Specification[StatusHistoryModel]):
    """Specification for history within time range."""

    def __init__(self, start: datetime, end: datetime) -> None:
        self._start = start
        self._end = end

    def to_expression(self) -> BinaryExpression:
        return and_(
            StatusHistoryModel.start_time <= self._end,
            or_(
                StatusHistoryModel.end_time >= self._start,
                StatusHistoryModel.end_time == None,
            ),
        )


class HistoryByStatus(Specification[StatusHistoryModel]):
    """Specification for history with specific status."""

    def __init__(self, status: int) -> None:
        self._status = status

    def to_expression(self) -> BinaryExpression:
        return StatusHistoryModel.equip_status == self._status


# ============================================================================
# Query Builder
# ============================================================================


@dataclass
class QueryOptions:
    """Options for query execution."""

    order_by: Optional[str] = None
    order_desc: bool = False
    limit: Optional[int] = None
    offset: Optional[int] = None
    include_deleted: bool = False


class SpecificationQueryBuilder(Generic[TModel]):
    """
    Builds SQLAlchemy queries from specifications.

    Usage:
        builder = SpecificationQueryBuilder(DeviceModel)
        query = builder.build(
            ActiveDevices() & ~DevicesWithAlarm(),
            QueryOptions(order_by="equip_code", limit=100)
        )
        result = await session.execute(query)
    """

    def __init__(self, model_class: Type[TModel]) -> None:
        self._model = model_class

    def build(
        self,
        spec: Optional[Specification[TModel]] = None,
        options: Optional[QueryOptions] = None,
    ) -> Select:
        """Build query from specification and options."""
        query = select(self._model)

        # Apply specification
        if spec:
            query = query.where(spec.to_expression())

        # Apply options
        if options:
            # Ordering
            if options.order_by:
                column = getattr(self._model, options.order_by, None)
                if column is not None:
                    if options.order_desc:
                        query = query.order_by(column.desc())
                    else:
                        query = query.order_by(column)

            # Pagination
            if options.limit:
                query = query.limit(options.limit)
            if options.offset:
                query = query.offset(options.offset)

        return query


__all__ = [
    # Base
    "Specification",
    "AndSpecification",
    "OrSpecification",
    "NotSpecification",
    # Device specs
    "DeviceByCode",
    "DeviceByCodeIn",
    "ActiveDevices",
    "DeviceByStatus",
    "DevicesWithAlarm",
    "DevicesUpdatedAfter",
    "DevicesNotUpdatedSince",
    # History specs
    "HistoryByDevice",
    "HistoryInTimeRange",
    "HistoryByStatus",
    # Query builder
    "QueryOptions",
    "SpecificationQueryBuilder",
]
