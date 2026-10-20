from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum
from datetime import date

class TravelPreference(BaseModel):
    budget_level: Optional[Literal["budget", "mid-range", "luxury"]] = None
    travel_style: Optional[List[str]] = None  # e.g., ["adventure", "relaxation"]
    interests: Optional[List[str]] = None  # e.g., ["beaches", "history"]
    accessibility_needs: Optional[bool] = None

class TravelerInfo(BaseModel):
    adults: int = 1
    children: int = 0
    infants: int = 0
    special_requirements: Optional[str] = None

class DestinationDetails(BaseModel):
    destination: str
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    duration_days: Optional[int] = None
    travelers: Optional[TravelerInfo] = None
    preferences: Optional[TravelPreference] = None

class ConfirmationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"

class ConfirmationRequest(BaseModel):
    field: str  # e.g., "destination"
    value: str  # e.g., "Mumbai, India"
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    alternatives: Optional[List[str]] = None
