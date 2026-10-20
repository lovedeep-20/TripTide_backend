import base64
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any
from app.core.config import settings
from app.core.logger import logger


class SabreAuthProvider:
    """Handles Sabre OAuth Token Management"""

    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self.auth_url = settings.SABRE_BASE_URL+"/v2/auth/token"

    async def get_access_token(self) -> str:
        """Retrieve and cache Sabre OAuth access token"""

        # Return cached token if still valid
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        logger.info("Requesting new Sabre access token")

        # Prepare Authorization header (Base64 clientID:clientSecret)
        auth_string = f"{settings.SABRE_CLIENT_ID}:{settings.SABRE_CLIENT_SECRET}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.auth_url,
                data="grant_type=client_credentials",
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]

                # Expires in seconds, subtract 60 buffer
                self.token_expiry = datetime.now() + timedelta(
                    seconds=data.get("expires_in", 300) - 60
                )

                logger.info("Sabre token generated successfully")
                return self.access_token

            logger.error(f"Failed to obtain Sabre token: {response.text}")
            raise Exception("Sabre Authentication Failed")


class SabreProvider:
    """Sabre main service provider — Similar structure to AmadeusProvider"""

    def __init__(self):
        self.auth = SabreAuthProvider()
        self.base_url = settings.SABRE_BASE_URL

    async def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers with bearer token"""
        token = await self.auth.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def _send_request(self, method: str, endpoint: str, **kwargs):
        """Wrapper for Sabre API requests"""
        headers = await self._get_headers()
        
        # Merge with any additional headers passed in kwargs
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )

        if response.status_code in (200, 201):
            return response.json()

        logger.error(f"Sabre API error {response.status_code}: {response.text}")
        return {"error": response.text}

    # ---------------------------------------------------
    # 🔹 Location Search (Airports, Cities)
    # ---------------------------------------------------
    async def search_locations(self, keyword: str, limit: int = 10) -> Dict[str, Any]:
        """
        Sabre API: Airport and City Search
        Endpoint: /v1/lists/utilities/geoservices/autocomplete
        """

        logger.info(f"Searching Sabre locations for keyword: {keyword}")

        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/v1/lists/utilities/geoservices/autocomplete",
                params={"query": keyword, "limit": limit},
                headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Found {len(data.get('Response', []))} locations")
                return data

            logger.error(f"Sabre location search failed: {response.text}")
            return {"Response": []}

    # ---------------------------------------------------
    # 🔹 Flight Search (Low Fare Search)
    # ---------------------------------------------------
    async def search_flights( self, origin: str, destination: str, departure_date: str, return_date: str, adults: int = 1) -> Dict[str, Any]:
        """
        Sabre Low Fare Flight Search
        Endpoint: /v5/offers/shop
        """

        logger.info(f"Searching flights {origin} → {destination}")

        payload = {
            "OTA_AirLowFareSearchRQ": {
                "OriginDestinationInformation": [
                    {
                        "DepartureDateTime": departure_date,
                        "OriginLocation": {"LocationCode": origin},
                        "DestinationLocation": {"LocationCode": destination}
                    },
                    {
                        "DepartureDateTime": return_date,
                        "OriginLocation": {"LocationCode": destination},
                        "DestinationLocation": {"LocationCode": origin}
                    }
                ],
                "TravelPreferences": {"MaxStopsQuantity": 2},
                "TravelerInfoSummary": {
                    "AirTravelerAvail": [{"PassengerTypeQuantity": [{
                        "Code": "ADT", "Quantity": adults
                    }]}]
                },
                "Version": "3.5.0"
            }
        }

        return await self._send_request(
            "POST",
            "/v5/offers/shop",
            json=payload
        )

    # ---------------------------------------------------
    # 🔹 Hotel Search
    # ---------------------------------------------------
    async def search_hotels(self, city_code: str, check_in: str, check_out: str) -> Dict[str, Any]:
        """
        Sabre Hotel Search
        Endpoint: /v1.0.0/shop/hotels
        """

        logger.info(f"Searching hotels in {city_code}")

        headers = await self._get_headers()

        params = {
            "city": city_code,
            "checkin": check_in,
            "checkout": check_out,
            "radius": 20,
            "radiusunit": "KM",
            "maxresults": 10
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self.base_url}/v1.0.0/shop/hotels",
                params=params,
                headers=headers
            )

            if response.status_code == 200:
                logger.info("Found hotels")
                return response.json()

            logger.error(f"Sabre hotel search failed: {response.text}")
            return {"data": []}

    # ---------------------------------------------------------
    # CREATE PNR
    # ---------------------------------------------------------
    async def create_pnr(self, given_name: str, surname: str, phone: str, email: str, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a Passenger Name Record"""

        payload = {
            "CreatePassengerNameRecordRQ": {
                "Version": "2.3.0",
                "targetCity": "PSS",
                "AirBook": {
                    "OriginDestinationInformation": segments
                },
                "TravelerInfo": {
                    "AirTraveler": [
                        {
                            "PassengerTypeQuantity": {"Code": "ADT", "Quantity": 1},
                            "PersonName": {
                                "GivenName": given_name,
                                "Surname": surname
                            }
                        }
                    ]
                },
                "ContactInfo": {
                    "Contact": [
                        {"Phone": phone, "Email": email}
                    ]
                }
            }
        }

        logger.info("Creating Sabre PNR")

        return await self._send_request(
            "POST",
            "/v2.3.0/passenger/records?mode=create",
            json=payload
        )

    # ---------------------------------------------------------
    # PRICE ITINERARY
    # ---------------------------------------------------------
    async def price_itinerary(self, pnr: str) -> Dict[str, Any]:
        """Price an itinerary for a given PNR"""

        payload = {
            "OTA_AirPriceRQ": {
                "Version": "3.5.0",
                "PriceRequestInformation": {"Retain": "true"},
                "AirItinerary": {"PNR": pnr}
            }
        }

        logger.info(f"Pricing itinerary for PNR: {pnr}")

        return await self._send_request(
            "POST",
            "/v3.5.0/air/price",
            json=payload
        )

    # ---------------------------------------------------------
    # ISSUE TICKET
    # ---------------------------------------------------------
    async def issue_ticket(self, pnr: str) -> Dict[str, Any]:
        """Issue an e-ticket for a given PNR"""

        payload = {
            "AirTicketRQ": {
                "Version": "1.0.0",
                "Ticketing": [
                    {"PNR": pnr, "Type": "ETICKET"}
                ]
            }
        }

        logger.info(f"Issuing ticket for Sabre PNR: {pnr}")

        return await self._send_request(
            "POST",
            "/v1.0.0/air/ticket",
            json=payload
        )

    # ---------------------------------------------------------
    # RETRIEVE PNR
    # ---------------------------------------------------------
    async def get_pnr_details(self, pnr: str) -> Dict[str, Any]:
        """Retrieve PNR details"""

        logger.info(f"Retrieving PNR details: {pnr}")

        return await self._send_request(
            "GET",
            f"/v2.3.0/passenger/records/{pnr}"
        )


# Singleton instance
sabre_provider = SabreProvider()