import httpx
from typing import Dict, Any
from src.application.exceptions import ApplicationException


class RemoteApiAdapter:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def fetch_device_status(self, device_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self._base_url}/devices/{device_id}/status", headers=self._headers, timeout=5.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise ApplicationException(f"Remote API error: {e.response.status_code}")
            except httpx.RequestError as e:
                raise ApplicationException(f"Network error while fetching device status: {str(e)}")
