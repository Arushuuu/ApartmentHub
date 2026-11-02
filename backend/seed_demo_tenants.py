"""Add 30 idempotent demo tenant records for the ApartmentHub presentation.

Run from the backend folder with the virtual-environment Python executable.

Every demo tenant uses the password stored in DEMO_PASSWORD below. Existing
emails are left unchanged, so re-running this file never creates duplicates.
"""

from datetime import date, timedelta
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
    ("Diya Chawla", "diya.chawla@apartmenthub.demo", "9000100021"),
    ("Aarav Patel", "aarav.patel@apartmenthub.demo", "9000100022"),
    ("Sana Mirza", "sana.mirza@apartmenthub.demo", "9000100023"),
    ("Krish Arora", "krish.arora@apartmenthub.demo", "9000100024"),
    ("Naina Saxena", "naina.saxena@apartmenthub.demo", "9000100025"),
    ("Om Prakash", "om.prakash@apartmenthub.demo", "9000100026"),
    ("Tara Mukherjee", "tara.mukherjee@apartmenthub.demo", "9000100027"),
    ("Reyansh Suri", "reyansh.suri@apartmenthub.demo", "9000100028"),
    ("Anjali Desai", "anjali.desai@apartmenthub.demo", "9000100029"),
    ("Mihir Kulkarni", "mihir.kulkarni@apartmenthub.demo", "9000100030"),
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
    new_leases = []
    billing_month = date.today().replace(day=1)
    lease_end = date(billing_month.year + 1, billing_month.month, 1) - timedelta(days=1)
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
                start_date=billing_month,
                end_date=lease_end,
                monthly_rent=rent,
            )
            db.add(lease)
            db.flush()
            new_leases.append(lease)
            db.add(SecurityDeposit(lease_id=lease.lease_id, amount_held=rent * 2, refund_status="Held"))

            # Give half the tenants a visible utility bill and every other
            # tenant a ticket, creating useful records for both dashboards.
            if index % 2 == 0:
                bill = UtilityBill(
                    unit_id=unit.unit_id,
                    total_amount=Decimal("1600") + Decimal(index * 25),
                    bill_date=billing_month,
                    due_date=billing_month.replace(day=20),
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

        # Add rent records only for the tenants created in this run. Existing
        # tenants' payment records must not be changed by a later seed run.
        rent_rows = 0
        for lease in new_leases:
            paid = lease.lease_id % 3 != 0
            db.add(RentPayment(
                lease_id=lease.lease_id,
                billing_month=billing_month,
                amount=lease.monthly_rent,
                payment_status="Paid" if paid else "Pending",
                paid_on=billing_month.replace(day=2) if paid else None,
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
