from pydantic import BaseModel, EmailStr, field_validator
from datetime import date, datetime
from decimal import Decimal

# Tenant Auth Schemas
class TenantCreate(BaseModel):
    tenant_name: str
    t_email: EmailStr
    password: str
    t_dob: date
    t_phone_no: str

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes long")
        return value

class TenantResponse(BaseModel):
    tenant_id: int
    tenant_name: str
    t_email: EmailStr
    t_phone_no: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class LeaseResponse(BaseModel):
    lease_id: int
    unit_id: int
    start_date: date
    end_date: date
    monthly_rent: Decimal
    class Config:
        from_attributes = True

class UtilityShareResponse(BaseModel):
    share_id: int
    bill_id: int
    owed_amt: Decimal
    payment_status: str
    bill_date: date
    due_date: date
    class Config:
        from_attributes = True

# Maintenance Ticket Schemas
class TicketCreate(BaseModel):
    unit_id: int
    category: str
    description: str

class TicketResponse(BaseModel):
    ticket_id: int
    category: str
    description: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class TicketUpdateCreate(BaseModel):
    update_message: str
