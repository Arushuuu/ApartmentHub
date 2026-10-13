from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Date, DateTime, Numeric, func, or_
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApartmentUnit, BillSplitShare, LeaseAgreement, MaintenanceTicket, RentPayment, SecurityDeposit, Tenant, TicketUpdateLog, UtilityBill
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

class CloseTicketInput(BaseModel):
    update_message: str = Field(default="Closed by administrator", min_length=1, max_length=1000)

RESOURCES = {
    "tenants": Tenant, "apartment_units": ApartmentUnit, "lease_agreements": LeaseAgreement,
    "security_deposits": SecurityDeposit, "rent_payments": RentPayment, "utility_bills": UtilityBill,
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
    leases = db.query(LeaseAgreement).all()
    billing_month = date.today().replace(day=1)
    paid_lease_ids = {
        lease_id for (lease_id,) in db.query(RentPayment.lease_id)
        .filter(RentPayment.billing_month == billing_month, RentPayment.payment_status == "Paid")
        .all()
    }
    unpaid_rent_count = sum(lease.lease_id not in paid_lease_ids for lease in leases)
    billed_tenants = db.query(func.count(func.distinct(BillSplitShare.tenant_id))).scalar() or 0
    unpaid_utility_tenants = (db.query(func.count(func.distinct(BillSplitShare.tenant_id)))
        .filter(BillSplitShare.payment_status == "Unpaid")
        .scalar() or 0)
    total_tickets = db.query(func.count(MaintenanceTicket.ticket_id)).scalar() or 0
    pending_tickets = db.query(func.count(MaintenanceTicket.ticket_id)).filter(MaintenanceTicket.status.in_(["Open", "In Progress"])).scalar() or 0
    return {
        "total_users": db.query(func.count(Tenant.tenant_id)).scalar(),
        "pending_tickets": pending_tickets,
        "resolved_tickets": db.query(func.count(MaintenanceTicket.ticket_id)).filter(MaintenanceTicket.status.in_(["Resolved", "Closed"])).scalar(),
        "pending_deposits": db.query(func.count(SecurityDeposit.deposit_id)).filter(SecurityDeposit.refund_status.in_(["Held", "Partial Refund"])).scalar(),
        "active_leases": len(leases),
        "unpaid_rent_count": unpaid_rent_count,
        "rent_unpaid_percentage": round((unpaid_rent_count / len(leases) * 100) if leases else 0, 1),
        "billed_tenants": billed_tenants,
        "unpaid_utility_tenants": unpaid_utility_tenants,
        "utility_unpaid_percentage": round((unpaid_utility_tenants / billed_tenants * 100) if billed_tenants else 0, 1),
        "total_tickets": total_tickets,
        "unresolved_ticket_percentage": round((pending_tickets / total_tickets * 100) if total_tickets else 0, 1),
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

@router.get("/tickets/active")
def active_tickets(db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    tickets = (db.query(MaintenanceTicket)
        .filter(MaintenanceTicket.status.in_(["Open", "In Progress"]))
        .order_by(MaintenanceTicket.created_at.desc())
        .all())
    return [{
        "ticket_id": ticket.ticket_id,
        "tenant_id": ticket.tenant_id,
        "tenant_name": ticket.tenant.tenant_name,
        "tenant_email": ticket.tenant.t_email,
        "unit_id": ticket.unit_id,
        "category": ticket.category,
        "description": ticket.description,
        "status": ticket.status,
        "created_at": ticket.created_at,
    } for ticket in tickets]

@router.get("/tickets/summary")
def ticket_summary(db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    rows = (db.query(MaintenanceTicket.category, func.count(MaintenanceTicket.ticket_id))
        .group_by(MaintenanceTicket.category)
        .order_by(MaintenanceTicket.category)
        .all())
    total = sum(count for _, count in rows)
    return {
        "total": total,
        "categories": [
            {"category": category, "count": count, "percentage": round((count / total * 100) if total else 0, 1)}
            for category, count in rows
        ],
    }

@router.patch("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: int, payload: CloseTicketInput, db: Session = Depends(get_db), current_admin: Tenant = Depends(require_admin)):
    ticket = db.get(MaintenanceTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Maintenance ticket not found")
    if ticket.status in ("Resolved", "Closed"):
        raise HTTPException(status_code=400, detail="This maintenance ticket is already closed")
    ticket.status = "Closed"
    db.add(TicketUpdateLog(ticket_id=ticket.ticket_id, updated_by=current_admin.tenant_name, update_message=payload.update_message))
    db.commit(); db.refresh(ticket)
    return {"message": "Maintenance ticket closed", "ticket_id": ticket.ticket_id, "status": ticket.status}

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
