from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Date, DateTime, Numeric
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApartmentUnit, BillSplitShare, LeaseAgreement, MaintenanceTicket, SecurityDeposit, Tenant, TicketUpdateLog, UtilityBill
from app.routers.auth import account_role, get_current_tenant, get_password_hash

router = APIRouter(prefix="/admin", tags=["Admin"])

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

@router.get("/tables")
def list_tables(_: Tenant = Depends(require_admin)):
    return list(RESOURCES)

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
