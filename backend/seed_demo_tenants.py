"""Add 20 idempotent demo tenant records for the ApartmentHub presentation.

Run from the backend folder with the virtual-environment Python executable.

Every demo tenant uses the password stored in DEMO_PASSWORD below. Existing
emails are left unchanged, so re-running this file never creates duplicates.
"""

from datetime import date
from decimal import Decimal

from app.database import SessionLocal
from app.models import ApartmentUnit, BillSplitShare, LeaseAgreement, MaintenanceTicket, RentPayment, SecurityDeposit, Tenant, UtilityBill
from app.routers.auth import get_password_hash


DEMO_PASSWORD = "ApartmentHub123!"
DEMO_TENANTS = [
    ("Aanya Kapoor", "aanya.kapoor@apartmenthub.demo", "9000100001"),
    ("Vihaan Malhotra", "vihaan.malhotra@apartmenthub.demo", "9000100002"),
    ("Ishita Rao", "ishita.rao@apartmenthub.demo", "9000100003"),
    ("Kabir Singh", "kabir.singh@apartmenthub.demo", "9000100004"),
    ("Meera Joshi", "meera.joshi@apartmenthub.demo", "9000100005"),
    ("Riya Nanda", "riya.nanda@apartmenthub.demo", "9000100006"),
    ("Arnav Gupta", "arnav.gupta@apartmenthub.demo", "9000100007"),
    ("Tanya Bhatia", "tanya.bhatia@apartmenthub.demo", "9000100008"),
    ("Dev Shah", "dev.shah@apartmenthub.demo", "9000100009"),
    ("Nisha Menon", "nisha.menon@apartmenthub.demo", "9000100010"),
    ("Yash Khanna", "yash.khanna@apartmenthub.demo", "9000100011"),
    ("Kavya Iyer", "kavya.iyer@apartmenthub.demo", "9000100012"),
    ("Rohan Das", "rohan.das@apartmenthub.demo", "9000100013"),
    ("Simran Kaur", "simran.kaur@apartmenthub.demo", "9000100014"),
    ("Aditya Bose", "aditya.bose@apartmenthub.demo", "9000100015"),
    ("Pooja Reddy", "pooja.reddy@apartmenthub.demo", "9000100016"),
    ("Neil Fernandes", "neil.fernandes@apartmenthub.demo", "9000100017"),
    ("Anika Sethi", "anika.sethi@apartmenthub.demo", "9000100018"),
    ("Siddharth Jain", "siddharth.jain@apartmenthub.demo", "9000100019"),
    ("Zoya Khan", "zoya.khan@apartmenthub.demo", "9000100020"),
]

TICKET_CATEGORIES = ["Plumbing", "Electrical", "Appliance", "Cleaning"]
TICKET_DESCRIPTIONS = [
    "Kitchen sink is draining slowly and needs inspection.",
    "Bedroom ceiling light flickers intermittently.",
    "Air conditioner is not cooling properly.",
    "Common corridor light needs replacement.",
]


def main():
    db = SessionLocal()
    created = 0
    try:
        password_hash = get_password_hash(DEMO_PASSWORD)
        for index, (name, email, phone) in enumerate(DEMO_TENANTS, start=1):
            if db.query(Tenant).filter(Tenant.t_email == email).first():
                continue

            tenant = Tenant(
                tenant_name=name,
                t_email=email,
                password_hash=password_hash,
                t_dob=date(1995 + (index % 7), (index % 12) + 1, (index % 27) + 1),
                t_phone_no=phone,
            )
            db.add(tenant)
            db.flush()

            unit = ApartmentUnit(
                building_name="Maple Residency",
                street="Lake View Road",
                unit_no=f"{200 + index}",
                pincode="560001",
                base_rent=Decimal("18000") + Decimal(index * 500),
            )
            db.add(unit)
            db.flush()

            rent = Decimal("18000") + Decimal(index * 500)
            lease = LeaseAgreement(
                unit_id=unit.unit_id,
                tenant_id=tenant.tenant_id,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                monthly_rent=rent,
            )
            db.add(lease)
            db.flush()
            db.add(SecurityDeposit(lease_id=lease.lease_id, amount_held=rent * 2, refund_status="Held"))

            # Give half the tenants a visible utility bill and every other
            # tenant a ticket, creating useful records for both dashboards.
            if index % 2 == 0:
                bill = UtilityBill(
                    unit_id=unit.unit_id,
                    total_amount=Decimal("1600") + Decimal(index * 25),
                    bill_date=date(2026, 10, 1),
                    due_date=date(2026, 10, 20),
                )
                db.add(bill)
                db.flush()
                db.add(BillSplitShare(bill_id=bill.bill_id, tenant_id=tenant.tenant_id, owed_amt=bill.total_amount, payment_status="Unpaid"))

            if index % 2 == 1:
                category_index = index % len(TICKET_CATEGORIES)
                db.add(MaintenanceTicket(
                    unit_id=unit.unit_id,
                    tenant_id=tenant.tenant_id,
                    category=TICKET_CATEGORIES[category_index],
                    description=TICKET_DESCRIPTIONS[category_index],
                    status="Open" if index % 4 else "In Progress",
                ))
            created += 1

        # A rent-payment row is tracked per active lease for the current demo
        # month. The mix of statuses makes the admin percentage meaningful.
        rent_rows = 0
        billing_month = date(2026, 10, 1)
        for lease in db.query(LeaseAgreement).all():
            exists = db.query(RentPayment).filter(
                RentPayment.lease_id == lease.lease_id,
                RentPayment.billing_month == billing_month,
            ).first()
            if exists:
                continue
            paid = lease.lease_id % 3 != 0
            db.add(RentPayment(
                lease_id=lease.lease_id,
                billing_month=billing_month,
                amount=lease.monthly_rent,
                payment_status="Paid" if paid else "Pending",
                paid_on=date(2026, 10, 5) if paid else None,
            ))
            rent_rows += 1

        db.commit()
        print(f"Created {created} demo tenants and {rent_rows} rent-payment rows. Total tenants: {db.query(Tenant).count()}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
