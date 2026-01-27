from typing import Dict, Any


class DeviceConfig:
    """
    Configuration specific to device connection parameters.
    """

    def __init__(self, config_data: Dict[str, Any]):
        self._data = config_data

    @property
    def connection_string(self) -> str:
        return self._data.get("connection_string", "")

    @property
    def table_name(self) -> str:
        return self._data.get("table_name", "TT_EQ_STATUS")

    @property
    def poll_interval(self) -> int:
        return self._data.get("poll_interval", 5000)
