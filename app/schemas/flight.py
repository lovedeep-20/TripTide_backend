from pydantic import BaseModel, Field
from typing import List, Optional


class FlightSegment(BaseModel):
    origin: str
    destination: str
    departure: str
    arrival: str

class FlightOffer(BaseModel):
    price: str
    currency: str
    segments: List[FlightSegment]


class FlightSearchParams(BaseModel):
    originLocationCode: str = Field(..., description="IATA code of origin airport")
    destinationLocationCode: str = Field(..., description="IATA code of destination airport")
    departureDate: str = Field(..., description="Departure date in YYYY-MM-DD")
    returnDate: Optional[str] = Field(None, description="Return date in YYYY-MM-DD")
    adults: int = Field(..., gt=0, description="Number of adult passengers")
    children: Optional[int] = None
    infants: Optional[int] = None
    travelClass: Optional[str] = "ECONOMY","BUSINESS","FIRST","PREMIUM_ECONOMY"
    includedAirlineCodes: Optional[str] = None
    excludeAirlineCodes: Optional[str] = None
    nonStop: Optional[bool] = None 
    currencyCode: Optional[str] = None
    maxPrice: Optional[int] = None
    max: Optional[int] = None

    def to_params(self) -> dict:
        """Convert model to dict and remove None/empty values."""
        return {k: v for k, v in self.dict().items() if v not in [None, ""]}
