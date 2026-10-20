from typing import Dict, Any, List, Optional
from app.schemas.flight import FlightSearchParams
from app.providers.amadeus_provider import amadeus_provider
from app.providers.sabre_provider import sabre_provider


class FlightService:
    async def search_flights(self, flight_data: FlightSearchParams) -> Dict[str, Any]:
        """Query Amadeus first, then fall back to Sabre if not enough results.
        Normalizes/merges provider responses into a top-level 'data' list.
        """
        # Query Amadeus (expects FlightSearchParams)
        amadeus_res = await amadeus_provider.search_flights(flight_data)
        results = {"data": amadeus_res.get("data", [])}
        # If not enough results, call Sabre (Sabre expects positional args)
        desired = flight_data.max or 1
        if len(results["data"]) < desired:
            sabre_res = await sabre_provider.search_flights(
                flight_data.originLocationCode,
                flight_data.destinationLocationCode,
                flight_data.departureDate,
                flight_data.returnDate or "",
                flight_data.adults or 1
            )
            # Sabre's response shape may differ; try to append any 'data' or responses list
            sabre_data = sabre_res.get("data") if isinstance(sabre_res, dict) else None
            if not sabre_data:
                # fallback keys
                sabre_data = sabre_res.get("Response") if isinstance(sabre_res, dict) else []
            if sabre_data:
                results["data"].extend(sabre_data)

        return results

    async def search_locations(
        self,
        keyword: str,
        limit: int = 10,
        subtype: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Search airport/city locations across providers, normalized.

        - Tries Amadeus reference-data locations first (CITY/AIRPORT),
          then falls back to Sabre geoservices autocomplete.
        - Returns a normalized 'data' list with items: {code, name, type, provider}.
        """
        normalized: List[Dict[str, Any]] = []
        seen: set[tuple] = set()

        # 1) Amadeus locations
        try:
            amadeus_locs = await amadeus_provider.search_location(
                keyword, subtype=subtype or ["CITY", "AIRPORT"]
            )
            for loc in amadeus_locs or []:
                code = loc.get("iataCode") or loc.get("iata_code")
                name = loc.get("name") or loc.get("cityName") or loc.get("detailedName")
                ltype = loc.get("subType") or loc.get("type")
                key = (code or name, ltype or "")
                if (code or name) and key not in seen:
                    normalized.append({
                        "code": code,
                        "name": name,
                        "type": ltype,
                        "provider": "amadeus",
                        "raw": loc,
                    })
                    seen.add(key)
                if len(normalized) >= limit:
                    return {"data": normalized[:limit]}
        except Exception:
            # Soft-fail to Sabre
            pass

        # 2) Sabre locations
        try:
            sabre_res = await sabre_provider.search_locations(keyword, limit=limit)
            items = []
            if isinstance(sabre_res, dict):
                # Common Sabre response key for lists is "Response"
                items = sabre_res.get("Response") or sabre_res.get("data") or []

            for itm in items:
                # Try a range of possible keys for robustness
                code = (
                    itm.get("AirportCode")
                    or itm.get("IATA")
                    or itm.get("IataCode")
                    or itm.get("Code")
                    or itm.get("code")
                )
                name = (
                    itm.get("Name")
                    or itm.get("CityName")
                    or itm.get("label")
                    or itm.get("value")
                    or itm.get("name")
                )
                ltype = (
                    itm.get("Category")
                    or itm.get("Type")
                    or itm.get("type")
                )
                key = (code or name, ltype or "")
                if (code or name) and key not in seen:
                    normalized.append({
                        "code": code,
                        "name": name,
                        "type": ltype,
                        "provider": "sabre",
                        "raw": itm,
                    })
                    seen.add(key)
                if len(normalized) >= limit:
                    break
        except Exception:
            pass

        return {"data": normalized[:limit]}

    async def price_or_confirm(self, provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Unify pricing step across providers.
        - Amadeus: confirm_flight_price with a flight offer (payload is the offer dict)
        - Sabre: price_itinerary with a PNR (payload requires {"pnr": "..."})
        """
        provider_lc = (provider or "").lower()
        if provider_lc == "amadeus":
            offer = payload
            if not isinstance(offer, dict):
                return {"error": "amadeus: flight offer dict required"}
            return await amadeus_provider.confirm_flight_price(offer)
        elif provider_lc == "sabre":
            pnr = payload.get("pnr") if isinstance(payload, dict) else None
            if not pnr:
                return {"error": "sabre: 'pnr' required for pricing"}
            return await sabre_provider.price_itinerary(pnr)
        return {"error": "unknown provider"}

    async def create_order(self, provider: str, **kwargs) -> Dict[str, Any]:
        """Create a booking/order across providers.
        - Amadeus: requires flight_offer (dict) and travelers (list)
        - Sabre: requires given_name, surname, phone, email, segments (list)
        """
        provider_lc = (provider or "").lower()
        if provider_lc == "amadeus":
            flight_offer = kwargs.get("flight_offer")
            travelers = kwargs.get("travelers")
            if not isinstance(flight_offer, dict) or not isinstance(travelers, list):
                return {"error": "amadeus: 'flight_offer' (dict) and 'travelers' (list) required"}
            return await amadeus_provider.create_flight_order(flight_offer, travelers)

        if provider_lc == "sabre":
            given_name = kwargs.get("given_name")
            surname = kwargs.get("surname")
            phone = kwargs.get("phone")
            email = kwargs.get("email")
            segments = kwargs.get("segments")
            missing = [k for k, v in {
                "given_name": given_name,
                "surname": surname,
                "phone": phone,
                "email": email,
                "segments": segments,
            }.items() if not v]
            if missing:
                return {"error": f"sabre: missing required fields: {', '.join(missing)}"}
            return await sabre_provider.create_pnr(given_name, surname, phone, email, segments)

        return {"error": "unknown provider"}

    async def get_order(self, provider: str, order_id: str) -> Dict[str, Any]:
        """Retrieve booking/order by ID (Amadeus) or PNR (Sabre)."""
        provider_lc = (provider or "").lower()
        if provider_lc == "amadeus":
            return await amadeus_provider.get_flight_order(order_id)
        if provider_lc == "sabre":
            return await sabre_provider.get_pnr_details(order_id)
        return {"error": "unknown provider"}

    async def cancel_order(self, provider: str, order_id: str) -> Dict[str, Any]:
        """Cancel order if supported by provider. Amadeus supports cancel; Sabre cancel not available here."""
        provider_lc = (provider or "").lower()
        if provider_lc == "amadeus":
            return await amadeus_provider.cancel_flight_order(order_id)
        if provider_lc == "sabre":
            return {"status": "unsupported", "message": "Sabre cancel via API not implemented"}
        return {"error": "unknown provider"}

    async def issue_ticket(self, provider: str, order_id: str) -> Dict[str, Any]:
        """Issue ticket where supported.
        - Sabre: issue_ticket with PNR
        - Amadeus: not supported via current provider implementation
        """
        provider_lc = (provider or "").lower()
        if provider_lc == "sabre":
            return await sabre_provider.issue_ticket(order_id)
        if provider_lc == "amadeus":
            return {"status": "unsupported", "message": "Amadeus ticket issuance not implemented"}
        return {"error": "unknown provider"}

    async def get_seat_map(self, provider: str, flight_offer: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve seat map when available (Amadeus only in current providers)."""
        provider_lc = (provider or "").lower()
        if provider_lc == "amadeus":
            return await amadeus_provider.get_seat_map(flight_offer)
        if provider_lc == "sabre":
            return {"status": "unsupported", "message": "Sabre seat map not implemented"}
        return {"error": "unknown provider"}
