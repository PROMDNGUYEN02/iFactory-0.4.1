"""
Remote data source interface - Contract for external data fetching.

This interface abstracts the remote database (MSSQL) access,
allowing the application to fetch data without knowing about
connection details or SQL specifics.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Sequence

__all__ = ["RemoteDataSource", "RemoteStatusRecord", "RemoteInputRecord"]


@dataclass(frozen=True, slots=True)
class RemoteStatusRecord:
    """
    Status record from remote data source.

    Represents raw data fetched from MSSQL before transformation
    to domain entities.

    Attributes:
        equip_code: The unique identifier for the equipment.
        equip_status: The raw status code/string from the database.
        last_update: Timestamp of the last update for this record.
        create_date: Timestamp when the record was created.
        start_time: Start time of the status period (if applicable).
        end_time: End time of the status period (if applicable).
    """

    equip_code: str
    equip_status: str
    last_update: Optional[datetime] = None
    create_date: Optional[datetime] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "RemoteStatusRecord":
        """
        Create a RemoteStatusRecord from a database row dictionary.

        Args:
            row: A dictionary representing a row from the remote DB.

        Returns:
            A populated RemoteStatusRecord instance.
        """
        return cls(
            equip_code=row.get("EQUIP_CODE", ""),
            equip_status=str(row.get("EQUIP_STATUS", "0")),
            last_update=row.get("LAST_UPDATE"),
            create_date=row.get("CREATE_DATE"),
            start_time=row.get("START_TIME"),
            end_time=row.get("END_TIME"),
        )


@dataclass(frozen=True, slots=True)
class RemoteInputRecord:
    """
    Input record from remote data source.

    Represents raw material input data from MSSQL.

    Attributes:
        equip_code: The unique identifier for the equipment.
        material_batch: The identifier for the material batch.
        feeding_time: Timestamp when the material was fed.
        create_date: Timestamp when the record was created.
    """

    equip_code: str
    material_batch: str
    feeding_time: Optional[datetime] = None
    create_date: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "RemoteInputRecord":
        """
        Create a RemoteInputRecord from a database row dictionary.

        Args:
            row: A dictionary representing a row from the remote DB.

        Returns:
            A populated RemoteInputRecord instance.
        """
        return cls(
            equip_code=row.get("EQUIP_CODE", ""),
            material_batch=row.get("MATERIAL_BATCH", ""),
            feeding_time=row.get("FEEDING_TIME"),
            create_date=row.get("CREATE_DATE"),
        )


class RemoteDataSource(ABC):
    """
    Abstract interface for remote data source (MSSQL).

    Provides methods to fetch fresh data from the external database.
    Implementation details (connection strings, query optimization)
    are hidden behind this interface.

    Design Notes:
        - All methods are async for non-blocking I/O.
        - Returns simple data records, not domain entities.
        - Transformation to domain happens in application layer.
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to remote data source.

        Raises:
            ConnectionError: If the connection attempt fails.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to remote data source."""

    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to remote data source.

        Returns:
            True if connected and healthy.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform health check on remote connection.

        Returns:
            True if connection is healthy and responsive.
        """

    @abstractmethod
    async def fetch_latest_status(
        self, codes: Optional[Sequence[str]] = None
    ) -> Sequence[RemoteStatusRecord]:
        """
        Fetch latest status for all or specified devices.

        Args:
            codes: Optional filter by equipment codes.
                   If None, fetches all devices.

        Returns:
            Sequence of status records.

        Raises:
            ConnectionError: If not connected.
            RuntimeError: If query execution fails.
        """

    @abstractmethod
    async def fetch_status_since(
        self, since: datetime, codes: Optional[Sequence[str]] = None
    ) -> Sequence[RemoteStatusRecord]:
        """
        Fetch status records changed since timestamp.

        Used for incremental sync.

        Args:
            since: Fetch records updated after this time.
            codes: Optional filter by equipment codes.

        Returns:
            Sequence of status records.
        """

    @abstractmethod
    async def fetch_status_history(
        self, code: str, start: datetime, end: datetime
    ) -> Sequence[RemoteStatusRecord]:
        """
        Fetch status history for a device in time range.

        Args:
            code: Equipment code.
            start: Range start time.
            end: Range end time.

        Returns:
            Sequence of historical status records.
        """

    @abstractmethod
    async def fetch_latest_input(
        self, codes: Optional[Sequence[str]] = None
    ) -> Sequence[RemoteInputRecord]:
        """
        Fetch latest input for all or specified devices.

        Args:
            codes: Optional filter by equipment codes.

        Returns:
            Sequence of input records.
        """

    @abstractmethod
    async def fetch_input_since(
        self, since: datetime, codes: Optional[Sequence[str]] = None
    ) -> Sequence[RemoteInputRecord]:
        """
        Fetch input records changed since timestamp.

        Args:
            since: Fetch records created after this time.
            codes: Optional filter by equipment codes.

        Returns:
            Sequence of input records.
        """

    @abstractmethod
    async def fetch_input_history(
        self, code: str, start: datetime, end: datetime
    ) -> Sequence[RemoteInputRecord]:
        """
        Fetch input history for a device in time range.

        Args:
            code: Equipment code.
            start: Range start time.
            end: Range end time.

        Returns:
            Sequence of historical input records.
        """

    @abstractmethod
    async def get_available_devices(self) -> Sequence[str]:
        """
        Get list of all available device codes.

        Returns:
            Sequence of equipment codes.
        """

    @abstractmethod
    async def get_last_update_time(self) -> Optional[datetime]:
        """
        Get timestamp of most recent data update.

        Returns:
            Latest update timestamp or None if no data exists.
        """
