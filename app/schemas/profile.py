from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizerProfileBase(BaseModel):
    business_name: str = Field(..., max_length=255)
    paystack_bank_code: str | None = Field(None, max_length=50)
    paystack_account_number: str | None = Field(None, max_length=50)

class OrganizerProfileCreate(OrganizerProfileBase):
    pass

class OrganizerProfilepdate(BaseModel):
    business_name: str | None = Field(None, max_length=255)
    paystack_bank_code: str | None = Field(None, max_length=50)
    paystack_account_number: str | None = Field(None, max_length=50)

class OrganizerProfileResponse(OrganizerProfileBase):
    id: UUID
    user_id: UUID
    paystack_subaccount_code: str | None = None
    percentage_charge: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)