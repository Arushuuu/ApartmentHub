import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ApartmentUnit, BillSplitShare, LeaseAgreement, Tenant, UtilityPaymentLog
from app.routers.admin import UtilityBillCreateInput, UtilityStatusInput, create_utility_bill, update_utility_share_status
from app.routers.utilities import mark_share_paid, my_utility_shares


class UtilityLedgerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.admin = Tenant(tenant_name="Admin", t_email="admin@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="1")
        self.tenants = [
            Tenant(tenant_name=f"Tenant {index}", t_email=f"tenant{index}@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no=str(index))
            for index in range(3)
        ]
        self.unit = ApartmentUnit(building_name="Maple", street="Main Road", unit_no="1", pincode="123456", base_rent=Decimal("1000"))
        self.db.add_all([self.admin, self.unit, *self.tenants])
        self.db.flush()
        for tenant in self.tenants:
            self.db.add(LeaseAgreement(unit_id=self.unit.unit_id, tenant_id=tenant.tenant_id,
                                       start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), monthly_rent=Decimal("1000")))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_three_way_split_and_status_history(self):
        bill = create_utility_bill(
            UtilityBillCreateInput(unit_id=self.unit.unit_id, total_amount=Decimal("100.00"),
                                   bill_date=date(2026, 11, 2), due_date=date(2026, 11, 9)),
            db=self.db, current_admin=self.admin,
        )
        self.assertEqual([share["owed_amt"] for share in bill["shares"]],
                         [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")])
        self.assertEqual(sum(share["owed_amt"] for share in bill["shares"]), Decimal("100.00"))
        self.assertEqual(self.db.query(UtilityPaymentLog).count(), 3)

        share_id = bill["shares"][0]["share_id"]
        mark_share_paid(share_id, current_tenant=self.tenants[0], db=self.db)
        self.assertEqual(my_utility_shares(current_tenant=self.tenants[0], db=self.db)[0]["payment_status"], "Pending Verification")
        self.assertEqual(self.db.query(UtilityPaymentLog).filter_by(share_id=share_id).count(), 2)

        updated = update_utility_share_status(share_id, UtilityStatusInput(payment_status="Paid"), db=self.db, current_admin=self.admin)
        self.assertEqual(updated["payment_status"], "Paid")
        self.assertEqual([entry["new_status"] for entry in updated["ledger"]], ["Unpaid", "Pending Verification", "Paid"])

        with self.assertRaises(HTTPException) as denied:
            mark_share_paid(share_id, current_tenant=self.tenants[1], db=self.db)
        self.assertEqual(denied.exception.status_code, 404)

    def test_bill_requires_tenants_with_active_leases(self):
        with self.assertRaises(HTTPException) as denied:
            create_utility_bill(
                UtilityBillCreateInput(unit_id=self.unit.unit_id, total_amount=Decimal("50.00"),
                                       bill_date=date(2025, 1, 1), due_date=date(2025, 1, 8)),
                db=self.db, current_admin=self.admin,
            )
        self.assertEqual(denied.exception.status_code, 400)
        self.assertEqual(self.db.query(BillSplitShare).count(), 0)


if __name__ == "__main__":
    unittest.main()
