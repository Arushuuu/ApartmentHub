from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Enum, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.database import Base

class ApartmentUnit(Base):
    __tablename__ = "apartment_units"
    __table_args__ = (UniqueConstraint("building_name", "street", "unit_no", name="uq_apartment_unit"),)

    unit_id = Column(Integer, primary_key=True, index=True)
    building_name = Column(String(100), nullable=False)
    street = Column(String(150), nullable=False)
    unit_no = Column(String(20), nullable=False)
    pincode = Column(String(10), nullable=False)
    base_rent = Column(Numeric(10, 2), nullable=False)

    leases = relationship("LeaseAgreement", back_populates="unit")
    utility_bills = relationship("UtilityBill", back_populates="unit")
    tickets = relationship("MaintenanceTicket", back_populates="unit")


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id = Column(Integer, primary_key=True, index=True)
    tenant_name = Column(String(100), nullable=False)
    t_email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    t_dob = Column(Date, nullable=False)
    t_phone_no = Column(String(20), nullable=False)

    leases = relationship("LeaseAgreement", back_populates="tenant")
    bill_shares = relationship("BillSplitShare", back_populates="tenant")
    tickets = relationship("MaintenanceTicket", back_populates="tenant")


class LeaseAgreement(Base):
    __tablename__ = "lease_agreements"

    lease_id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("apartment_units.unit_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    monthly_rent = Column(Numeric(10, 2), nullable=False)

    unit = relationship("ApartmentUnit", back_populates="leases")
    tenant = relationship("Tenant", back_populates="leases")
    deposit = relationship("SecurityDeposit", back_populates="lease", uselist=False)


class SecurityDeposit(Base):
    __tablename__ = "security_deposits"

    deposit_id = Column(Integer, primary_key=True, index=True)
    lease_id = Column(Integer, ForeignKey("lease_agreements.lease_id", ondelete="CASCADE"), unique=True, nullable=False)
    amount_held = Column(Numeric(10, 2), nullable=False)
    refund_status = Column(Enum("Held", "Partial Refund", "Fully Refunded"), default="Held")

    lease = relationship("LeaseAgreement", back_populates="deposit")


class UtilityBill(Base):
    __tablename__ = "utility_bills"

    bill_id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("apartment_units.unit_id", ondelete="CASCADE"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    bill_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    unit = relationship("ApartmentUnit", back_populates="utility_bills")
    shares = relationship("BillSplitShare", back_populates="bill")


class BillSplitShare(Base):
    __tablename__ = "bill_split_shares"
    __table_args__ = (UniqueConstraint("bill_id", "tenant_id", name="uq_bill_tenant_share"),)

    share_id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("utility_bills.bill_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    owed_amt = Column(Numeric(10, 2), nullable=False)
    payment_status = Column(Enum("Unpaid", "Pending Verification", "Paid"), default="Unpaid")

    bill = relationship("UtilityBill", back_populates="shares")
    tenant = relationship("Tenant", back_populates="bill_shares")


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"

    ticket_id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("apartment_units.unit_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum("Open", "In Progress", "Resolved", "Closed"), default="Open")
    created_at = Column(DateTime, server_default=func.now())  # <--- Updated to DateTime

    unit = relationship("ApartmentUnit", back_populates="tickets")
    tenant = relationship("Tenant", back_populates="tickets")
    logs = relationship("TicketUpdateLog", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketUpdateLog.updated_timestamp")


class TicketUpdateLog(Base):
    __tablename__ = "ticket_update_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("maintenance_tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    updated_by = Column(String(100), nullable=False)
    update_message = Column(Text, nullable=False)
    updated_timestamp = Column(DateTime, server_default=func.now())  # <--- Updated to DateTime

    ticket = relationship("MaintenanceTicket", back_populates="logs")
