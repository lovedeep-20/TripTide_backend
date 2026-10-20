import httpx
from typing import Any, Dict, Optional
from app.core.config import settings
from app.core.logger import logger


class PKFareProvider:
    """Lightweight PKFare API provider.

    This provider exposes a generic `request` helper that attaches partner
    credentials from environment variables. Convenience wrappers are provided
    for common operations but endpoints can be overridden at call time.
    """

    def __init__(self):
        self.base_url: Optional[str] = settings.PKFARE_BASE_URL
        self.partner_id: Optional[str] = settings.PKFARE_PARTNER_ID
        self.partner_key: Optional[str] = settings.PKFARE_PARTNER_KEY

    def _default_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.partner_id:
            headers["X-Partner-Id"] = self.partner_id
        if self.partner_key:
            headers["X-Partner-Key"] = self.partner_key
        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        if not self.base_url:
            logger.error("PKFare base URL is not configured")
            return {"error": "PKFare base URL is not configured"}

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        req_headers = self._default_headers()
        if headers:
            req_headers.update(headers)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method.upper(), url=url, params=params, json=json, headers=req_headers
                )

            if response.status_code in (200, 201):
                return response.json()

            logger.warning(f"PKFare API {method} {url} -> {response.status_code}: {response.text}")
            try:
                return response.json()
            except Exception:
                return {"error": response.text, "status_code": response.status_code}

        except httpx.RequestError as e:
            logger.error(f"PKFare request failed: {e}")
            return {"error": str(e)}

    # Convenience wrappers (endpoints are configurable at call-time)
    async def search_flights(self, payload: Dict[str, Any], endpoint: str = "/flight/search") -> Dict[str, Any]:
        """Search flights. Provide `payload` as required by PKFare docs."""
        return await self.request("POST", endpoint, json=payload, timeout=60.0)

    async def create_booking(self, payload: Dict[str, Any], endpoint: str = "/booking/create") -> Dict[str, Any]:
        """Create a booking/order on PKFare."""
        return await self.request("POST", endpoint, json=payload, timeout=60.0)

    async def get_booking(self, booking_id: str, endpoint: str = "/booking/") -> Dict[str, Any]:
        """Retrieve booking details. `endpoint` should accept booking id appended."""
        return await self.request("GET", f"{endpoint.rstrip('/')}/{booking_id}")

    async def cancel_booking(self, booking_id: str, endpoint: str = "/booking/cancel") -> Dict[str, Any]:
        """Cancel a booking/order."""
        return await self.request("POST", f"{endpoint.rstrip('/')}/{booking_id}")


# singleton instance
pkfare_provider = PKFareProvider()
