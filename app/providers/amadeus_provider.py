import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.core.logger import logger
from app.schemas.flight import FlightSearchParams

class AmadeusProvider:
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self.base_url = settings.AMADEUS_BASE_URL
        
    async def get_access_token(self) -> str:
        """Get OAuth2 access token from Amadeus"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token
        
        logger.info("Requesting new Amadeus access token")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.AMADEUS_API_KEY,
                    "client_secret": settings.AMADEUS_API_SECRET
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                self.token_expiry = datetime.now() + timedelta(seconds=data["expires_in"] - 60)
                logger.info("Successfully obtained access token")
                return self.access_token
            else:
                logger.error(f"Failed to get token: {response.text}")
                raise Exception(f"Failed to authenticate with Amadeus: {response.text}")
    
    async def search_city(self, keyword: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for cities by keyword using Amadeus City Search API"""
        logger.info(f"Searching cities with keyword: {keyword}")
        
        try:
            token = await self.get_access_token()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/reference-data/locations/cities",
                    params={
                        "keyword": keyword,
                        "page[limit]": max_results
                    },
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    cities = data.get("data", [])
                    logger.info(f"Found {len(cities)} cities")
                    return cities
                else:
                    logger.warning(f"City search failed: {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Error searching cities: {e}")
            return []
    
    async def search_location(self, keyword: str, subtype: List[str] = None) -> List[Dict[str, Any]]:
        """Search for locations (airports, cities) by keyword"""
        logger.info(f"Searching locations with keyword: {keyword}")
        
        try:
            token = await self.get_access_token()
            
            params = {
                "keyword": keyword,
                "page[limit]": 10
            }
            
            if subtype:
                params["subType"] = ",".join(subtype)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/reference-data/locations",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    locations = data.get("data", [])
                    logger.info(f"Found {len(locations)} locations")
                    return locations
                else:
                    logger.warning(f"Location search failed: {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Error searching locations: {e}")
            return []
    
    async def search_activities(self, latitude: float, longitude: float, radius: int = 20) -> Dict[str, Any]:
        """Search for activities at destination"""
        logger.info(f"Searching activities at lat={latitude}, lon={longitude}")
        
        try:
            token = await self.get_access_token()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/shopping/activities",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "radius": radius
                    },
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Found {len(data.get('data', []))} activities")
                    return data
                else:
                    logger.warning(f"Activities search failed: {response.text}")
                    return {"data": []}
        except Exception as e:
            logger.error(f"Error searching activities: {e}")
            return {"data": []}
    
    async def search_flights(self, flight_data:FlightSearchParams) -> Dict[str, Any]:
        """Search for flight offers"""
        logger.info(f"Searching flights: {flight_data.originLocationCode} -> {flight_data.destinationLocationCode}")
        
        try:
            token = await self.get_access_token()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v2/shopping/flight-offers",
                    params=flight_data.to_params(),
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Found {len(data.get('data', []))} flights")
                    return data
                else:
                    logger.warning(f"Flight search failed: {response.text}")
                    return {"data": []}
        except Exception as e:
            logger.error(f"Error searching flights: {e}")
            return {"data": []}

    async def confirm_flight_price(self, flight_offer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Confirm price and availability of a selected flight offer.
        This step is REQUIRED before creating an order.
        """
        logger.info("Confirming flight offer price")

        try:
            token = await self.get_access_token()

            payload = {
                "data": {
                    "type": "flight-offers-pricing",
                    "flightOffers": [flight_offer]
                }
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/shopping/flight-offers/pricing",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    logger.info("Flight price confirmed successfully")
                    return response.json()
                else:
                    logger.warning(f"Price confirmation failed: {response.text}")
                    return {"data": None}

        except Exception as e:
            logger.error(f"Error confirming flight price: {e}")
            return {"data": None}

    async def create_flight_order(self, flight_offer: Dict[str, Any], travelers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create flight order (booking)"""
        logger.info("Creating flight order")

        try:
            token = await self.get_access_token()

            payload = {
                "data": {
                    "type": "flight-order",
                    "flightOffers": [flight_offer],
                    "travelers": travelers
                }
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/booking/flight-orders",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code in (200, 201):
                    logger.info("Flight order created successfully")
                    return response.json()
                else:
                    logger.warning(f"Flight order creation failed: {response.text}")
                    return {"data": None}

        except Exception as e:
            logger.error(f"Error creating flight order: {e}")
            return {"data": None}

    async def get_flight_order(self, order_id: str) -> Dict[str, Any]:
        """Retrieve flight order details"""
        logger.info(f"Fetching flight order {order_id}")

        try:
            token = await self.get_access_token()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/booking/flight-orders/{order_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Fetch order failed: {response.text}")
                    return {"data": None}

        except Exception as e:
            logger.error(f"Error fetching flight order: {e}")
            return {"data": None}

    async def cancel_flight_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel flight order"""
        logger.info(f"Cancelling flight order {order_id}")

        try:
            token = await self.get_access_token()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.base_url}/v1/booking/flight-orders/{order_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )

                if response.status_code in (200, 204):
                    logger.info("Flight order cancelled successfully")
                    return {"status": "cancelled"}
                else:
                    logger.warning(f"Cancel failed: {response.text}")
                    return {"status": "failed"}

        except Exception as e:
            logger.error(f"Error cancelling flight order: {e}")
            return {"status": "failed"}

    async def get_seat_map(self, flight_offer: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve seat map for a flight offer"""
        logger.info("Fetching seat map")

        try:
            token = await self.get_access_token()

            payload = {
                "data": [flight_offer]
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/shopping/seatmaps",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Seat map fetch failed: {response.text}")
                    return {"data": []}

        except Exception as e:
            logger.error(f"Error fetching seat map: {e}")
            return {"data": []}

    async def flight_inspiration_search(
        self,
        origin: str,
        departure_date: Optional[str] = None,
        max_price: Optional[int] = None
    ) -> Dict[str, Any]:
        """Find inspirational destinations"""
        logger.info(f"Inspiration search from {origin}")

        try:
            token = await self.get_access_token()

            params = {"origin": origin}
            if departure_date:
                params["departureDate"] = departure_date
            if max_price:
                params["maxPrice"] = max_price

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/shopping/flight-destinations",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Inspiration search failed: {response.text}")
                    return {"data": []}

        except Exception as e:
            logger.error(f"Error in inspiration search: {e}")
            return {"data": []}

    async def flight_cheapest_date_search(
        self,
        origin: str,
        destination: str
    ) -> Dict[str, Any]:
        """Find cheapest dates to fly"""
        logger.info(f"Cheapest date search {origin} -> {destination}")

        try:
            token = await self.get_access_token()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/shopping/flight-dates",
                    params={
                        "origin": origin,
                        "destination": destination
                    },
                    headers={"Authorization": f"Bearer {token}"}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Cheapest date search failed: {response.text}")
                    return {"data": []}

        except Exception as e:
            logger.error(f"Error in cheapest date search: {e}")
            return {"data": []}

    async def search_hotels(self, city_code: str, check_in: str, check_out: str, adults: int) -> Dict[str, Any]:
        """Search for hotel offers"""
        logger.info(f"Searching hotels in {city_code}")
        
        try:
            token = await self.get_access_token()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get hotel IDs by city
                hotel_response = await client.get(
                    f"{self.base_url}/v1/reference-data/locations/hotels/by-city",
                    params={"cityCode": city_code},
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if hotel_response.status_code != 200:
                    logger.warning(f"Hotel IDs search failed: {hotel_response.text}")
                    return {"data": []}
                
                hotels = hotel_response.json().get("data", [])[:5]
                hotel_ids = [hotel["hotelId"] for hotel in hotels]
                
                if not hotel_ids:
                    return {"data": []}
                
                # Get hotel offers
                offers_response = await client.get(
                    f"{self.base_url}/v3/shopping/hotel-offers",
                    params={
                        "hotelIds": ",".join(hotel_ids),
                        "checkInDate": check_in,
                        "checkOutDate": check_out,
                        "adults": adults
                    },
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if offers_response.status_code == 200:
                    data = offers_response.json()
                    logger.info(f"Found {len(data.get('data', []))} hotel offers")
                    return data
                else:
                    logger.warning(f"Hotel offers search failed: {offers_response.text}")
                    return {"data": []}
        except Exception as e:
            logger.error(f"Error searching hotels: {e}")
            return {"data": []}

# Singleton instance
amadeus_provider = AmadeusProvider()
