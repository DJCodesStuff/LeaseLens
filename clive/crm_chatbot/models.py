from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re
from datetime import datetime

class CRERecord(BaseModel):
    unique_id: int
    property_address: str
    floor: str
    suite: str
    size_sf: int
    rent_per_sf_year: float
    broker_email: EmailStr
    annual_rent: float
    monthly_rent: float
    gci_on_3_years: float

    @field_validator("rent_per_sf_year", "annual_rent", "monthly_rent", "gci_on_3_years", mode="before")
    @classmethod
    def strip_dollar_and_commas(cls, v):
        if isinstance(v, str):
            return float(re.sub(r"[^\d.]", "", v))
        return v

class UserRecord(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    role: Optional[str] = "user"

class ChatRecord(BaseModel):
    chat_id: str
    user_id: str
    session_id: str  # allows multiple sessions per user
    timestamp: datetime
    message: str
    response: Optional[str] = None  # AI or agent response 