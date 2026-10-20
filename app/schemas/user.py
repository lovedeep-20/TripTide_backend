from __future__ import annotations

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=128)
    last_name: Optional[str] = Field(None, max_length=128)
    gender: Optional[str] = Field(None, max_length=32)
    country_code: Optional[str] = Field(None, max_length=8)

    phone_number: str = Field(..., min_length=3, max_length=20)
    email: Optional[EmailStr] = None


class UserRead(BaseModel):
    id: int
    user_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[str]
    country_code: Optional[str]
    phone_number: str
    email: Optional[EmailStr]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
