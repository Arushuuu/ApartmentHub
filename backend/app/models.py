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
    signed_leases = relationship("LeaseSignatory", back_populates="tenant")
    rent_shares = relationship("RentShare", back_populates="tenant")
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
    signatories = relationship("LeaseSignatory", back_populates="lease", cascade="all, delete-orphan")
    deposit = relationship("SecurityDeposit", back_populates="lease", uselist=False)
    rent_payments = relationship("RentPayment", back_populates="lease", cascade="all, delete-orphan")


class LeaseSignatory(Base):
    __tablename__ = "lease_signatories"

    lease_id = Column(Integer, ForeignKey("lease_agreements.lease_id", ondelete="CASCADE"), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), primary_key=True)

    lease = relationship("LeaseAgreement", back_populates="signatories")
    tenant = relationship("Tenant", back_populates="signed_leases")


class SecurityDeposit(Base):
    __tablename__ = "security_deposits"

    deposit_id = Column(Integer, primary_key=True, index=True)
    lease_id = Column(Integer, ForeignKey("lease_agreements.lease_id", ondelete="CASCADE"), unique=True, nullable=False)
    amount_held = Column(Numeric(10, 2), nullable=False)
    refund_status = Column(Enum("Held", "Partial Refund", "Fully Refunded"), default="Held")

    lease = relationship("LeaseAgreement", back_populates="deposit")
    contributions = relationship("DepositContribution", back_populates="deposit", cascade="all, delete-orphan")
    ledger = relationship("DepositLedgerEntry", back_populates="deposit", cascade="all, delete-orphan", order_by="DepositLedgerEntry.entry_id")


class DepositContribution(Base):
    __tablename__ = "deposit_contributions"

    deposit_id = Column(Integer, ForeignKey("security_deposits.deposit_id", ondelete="CASCADE"), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    contributed_amt = Column(Numeric(10, 2), nullable=False)
    # NULL means a legacy partial refund has no recorded amount yet.
    refunded_amt = Column(Numeric(10, 2), nullable=True, default=0)

    deposit = relationship("SecurityDeposit", back_populates="contributions")
    tenant = relationship("Tenant")


class DepositLedgerEntry(Base):
    __tablename__ = "deposit_ledger_entries"

    entry_id = Column(Integer, primary_key=True, index=True)
    deposit_id = Column(Integer, ForeignKey("security_deposits.deposit_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    action = Column(String(30), nullable=False)
    amount = Column(Numeric(10, 2), nullable=True)
    recorded_by = Column(String(100), nullable=False)
    note = Column(String(500), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    deposit = relationship("SecurityDeposit", back_populates="ledger")
    tenant = relationship("Tenant")


class RentPayment(Base):
    __tablename__ = "rent_payments"
    __table_args__ = (UniqueConstraint("lease_id", "billing_month", name="uq_lease_rent_month"),)

    payment_id = Column(Integer, primary_key=True, index=True)
    lease_id = Column(Integer, ForeignKey("lease_agreements.lease_id", ondelete="CASCADE"), nullable=False)
    billing_month = Column(Date, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    payment_status = Column(Enum("Pending", "Paid"), default="Pending", nullable=False)
    paid_on = Column(Date, nullable=True)

    lease = relationship("LeaseAgreement", back_populates="rent_payments")
    shares = relationship("RentShare", back_populates="payment", cascade="all, delete-orphan", order_by="RentShare.tenant_id")


class RentShare(Base):
    __tablename__ = "rent_shares"
    __table_args__ = (UniqueConstraint("payment_id", "tenant_id", name="uq_rent_payment_tenant"),)

    share_id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("rent_payments.payment_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    owed_amt = Column(Numeric(10, 2), nullable=False)
    payment_status = Column(Enum("Unpaid", "Pending Verification", "Paid"), default="Unpaid", nullable=False)
    paid_on = Column(Date, nullable=True)

    payment = relationship("RentPayment", back_populates="shares")
    tenant = relationship("Tenant", back_populates="rent_shares")
    ledger = relationship("RentPaymentLog", back_populates="share", cascade="all, delete-orphan", order_by="RentPaymentLog.log_id")


class RentPaymentLog(Base):
    __tablename__ = "rent_payment_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    share_id = Column(Integer, ForeignKey("rent_shares.share_id", ondelete="CASCADE"), nullable=False)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    recorded_by = Column(String(100), nullable=False)
    note = Column(String(500), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    share = relationship("RentShare", back_populates="ledger")


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
    ledger = relationship("UtilityPaymentLog", back_populates="share", cascade="all, delete-orphan", order_by="UtilityPaymentLog.log_id")


class UtilityPaymentLog(Base):
    __tablename__ = "utility_payment_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    share_id = Column(Integer, ForeignKey("bill_split_shares.share_id", ondelete="CASCADE"), nullable=False)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    recorded_by = Column(String(100), nullable=False)
    note = Column(String(500), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    share = relationship("BillSplitShare", back_populates="ledger")


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
    logs = relationship("TicketUpdateLog", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketUpdateLog.log_id")


class TicketUpdateLog(Base):
    __tablename__ = "ticket_update_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("maintenance_tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    updated_by = Column(String(100), nullable=False)
    update_message = Column(Text, nullable=False)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=True)
    updated_timestamp = Column(DateTime, server_default=func.now())  # <--- Updated to DateTime

    ticket = relationship("MaintenanceTicket", back_populates="logs")
