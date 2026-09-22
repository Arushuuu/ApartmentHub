from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MaintenanceTicket, TicketUpdateLog
from app.routers.auth import get_current_tenant
from app.schemas import TicketCreate, TicketResponse, TicketUpdateCreate

router = APIRouter(prefix="/tickets", tags=["Maintenance"])

@router.get("/me", response_model=list[TicketResponse])
def my_tickets(current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    return db.query(MaintenanceTicket).filter(MaintenanceTicket.tenant_id == current_tenant.tenant_id).order_by(MaintenanceTicket.created_at.desc()).all()

@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    ticket = MaintenanceTicket(**payload.model_dump(), tenant_id=current_tenant.tenant_id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

@router.get("/{ticket_id}/updates")
def ticket_updates(ticket_id: int, current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.ticket_id == ticket_id, MaintenanceTicket.tenant_id == current_tenant.tenant_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket.logs

@router.post("/{ticket_id}/updates", status_code=status.HTTP_201_CREATED)
def add_ticket_update(ticket_id: int, payload: TicketUpdateCreate, current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.ticket_id == ticket_id, MaintenanceTicket.tenant_id == current_tenant.tenant_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    log = TicketUpdateLog(ticket_id=ticket.ticket_id, updated_by=current_tenant.tenant_name, update_message=payload.update_message)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
