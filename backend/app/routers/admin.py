from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Date, DateTime, Numeric, func, or_
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApartmentUnit, BillSplitShare, LeaseAgreement, MaintenanceTicket, SecurityDeposit, Tenant, TicketUpdateLog, UtilityBill
from app.routers.auth import account_role, get_current_tenant, get_password_hash

router = APIRouter(prefix="/admin", tags=["Admin"])

class TenantCreateInput(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=100)
    t_email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    t_dob: date
    t_phone_no: str = Field(min_length=1, max_length=20)

class TenantUpdateInput(BaseModel):
    tenant_name: str | None = Field(default=None, min_length=1, max_length=100)
    t_email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    t_dob: date | None = None
    t_phone_no: str | None = Field(default=None, min_length=1, max_length=20)

RESOURCES = {
    "tenants": Tenant, "apartment_units": ApartmentUnit, "lease_agreements": LeaseAgreement,
    "security_deposits": SecurityDeposit, "utility_bills": UtilityBill,
    "bill_split_shares": BillSplitShare, "maintenance_tickets": MaintenanceTicket,
    "ticket_update_logs": TicketUpdateLog,
}

def require_admin(current_tenant=Depends(get_current_tenant)):
    if account_role(current_tenant) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required")
    return current_tenant

def model_for(resource: str):
    model = RESOURCES.get(resource)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown database table")
    return model

def clean_values(model, payload: dict[str, Any], creating: bool) -> dict[str, Any]:
    columns = {column.name: column for column in inspect(model).columns}
    values = {key: value for key, value in payload.items() if key in columns and (creating or not columns[key].primary_key)}
    if model is Tenant and "password" in payload:
        values["password_hash"] = get_password_hash(payload["password"])
    for name, value in list(values.items()):
        if value in (None, ""):
            continue
        column_type = columns[name].type
        if isinstance(column_type, Date) and not isinstance(value, date):
            values[name] = date.fromisoformat(value)
        elif isinstance(column_type, DateTime) and not isinstance(value, datetime):
            values[name] = datetime.fromisoformat(value)
        elif isinstance(column_type, Numeric) and not isinstance(value, Decimal):
            values[name] = Decimal(str(value))
    return values

def tenant_view(tenant: Tenant) -> dict[str, Any]:
    return {"tenant_id": tenant.tenant_id, "tenant_name": tenant.tenant_name, "t_email": tenant.t_email, "t_dob": tenant.t_dob, "t_phone_no": tenant.t_phone_no}

@router.get("/tables")
def list_tables(_: Tenant = Depends(require_admin)):
    return list(RESOURCES)

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    return {
        "total_users": db.query(func.count(Tenant.tenant_id)).scalar(),
        "pending_tickets": db.query(func.count(MaintenanceTicket.ticket_id)).filter(MaintenanceTicket.status.in_(["Open", "In Progress"])).scalar(),
        "resolved_tickets": db.query(func.count(MaintenanceTicket.ticket_id)).filter(MaintenanceTicket.status.in_(["Resolved", "Closed"])).scalar(),
        "pending_deposits": db.query(func.count(SecurityDeposit.deposit_id)).filter(SecurityDeposit.refund_status.in_(["Held", "Partial Refund"])).scalar(),
        "active_leases": db.query(func.count(LeaseAgreement.lease_id)).scalar(),
    }

@router.get("/users")
def list_users(search: str = "", db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    query = db.query(Tenant)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Tenant.tenant_name.ilike(term), Tenant.t_email.ilike(term)))
    return [tenant_view(tenant) for tenant in query.order_by(Tenant.tenant_name).all()]

@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: TenantCreateInput, db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    if db.query(Tenant).filter(Tenant.t_email == payload.t_email).first():
        raise HTTPException(status_code=400, detail="Email already belongs to a tenant")
    tenant = Tenant(tenant_name=payload.tenant_name, t_email=payload.t_email, password_hash=get_password_hash(payload.password), t_dob=payload.t_dob, t_phone_no=payload.t_phone_no)
    db.add(tenant); db.commit(); db.refresh(tenant)
    return tenant_view(tenant)

@router.patch("/users/{tenant_id}")
def update_user(tenant_id: int, payload: TenantUpdateInput, db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    updates = payload.model_dump(exclude_none=True)
    if "password" in updates:
        tenant.password_hash = get_password_hash(updates.pop("password"))
    for field, value in updates.items():
        setattr(tenant, field, value)
    try:
        db.commit(); db.refresh(tenant)
    except Exception as error:
        db.rollback(); raise HTTPException(status_code=400, detail=f"User update failed: {str(error).splitlines()[0]}")
    return tenant_view(tenant)

@router.delete("/users/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(tenant_id: int, db: Session = Depends(get_db), current_admin: Tenant = Depends(require_admin)):
    if tenant_id == current_admin.tenant_id:
        raise HTTPException(status_code=400, detail="You cannot delete the account currently signed in as admin")
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(tenant)
    try:
        db.commit()
    except Exception as error:
        db.rollback(); raise HTTPException(status_code=400, detail=f"User deletion failed: {str(error).splitlines()[0]}")

@router.get("/{resource}")
def list_records(resource: str, db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    model = model_for(resource)
    return db.query(model).limit(500).all()

@router.post("/{resource}", status_code=status.HTTP_201_CREATED)
def create_record(resource: str, payload: dict[str, Any], db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    model = model_for(resource)
    values = clean_values(model, payload, creating=True)
    if model is Tenant and "password_hash" not in values:
        raise HTTPException(status_code=400, detail="A password is required when creating a tenant")
    record = model(**values)
    db.add(record)
    try:
        db.commit(); db.refresh(record)
    except Exception as error:
        db.rollback(); raise HTTPException(status_code=400, detail=f"Database update failed: {str(error).splitlines()[0]}")
    return record

@router.patch("/{resource}/{record_id}")
def update_record(resource: str, record_id: int, payload: dict[str, Any], db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    model = model_for(resource)
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    for key, value in clean_values(model, payload, creating=False).items():
        setattr(record, key, value)
    try:
        db.commit(); db.refresh(record)
    except Exception as error:
        db.rollback(); raise HTTPException(status_code=400, detail=f"Database update failed: {str(error).splitlines()[0]}")
    return record

@router.delete("/{resource}/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(resource: str, record_id: int, db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    model = model_for(resource)
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    try:
        db.commit()
    except Exception as error:
        db.rollback(); raise HTTPException(status_code=400, detail=f"Delete failed: {str(error).splitlines()[0]}")
