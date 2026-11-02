import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ApartmentUnit, LeaseAgreement, LeaseSignatory, RentPayment, RentPaymentLog, RentShare, Tenant
from app.routers.rent import (RentMonthCreate, RentReportInput, RentStatusInput,
                              generate_rent_month, my_rent, report_rent_payment, update_rent_status)


class RentLedgerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.admin = Tenant(tenant_name="Admin", t_email="admin@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="1")
        self.first = Tenant(tenant_name="First", t_email="first@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="2")
        self.second = Tenant(tenant_name="Second", t_email="second@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="3")
        self.outsider = Tenant(tenant_name="Outsider", t_email="outsider@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="4")
        unit = ApartmentUnit(building_name="Maple", street="Main", unit_no="1", pincode="123456", base_rent=Decimal("100.01"))
        self.db.add_all([self.admin, self.first, self.second, self.outsider, unit])
        self.db.flush()
        self.lease = LeaseAgreement(unit_id=unit.unit_id, tenant_id=self.first.tenant_id,
                                    start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                                    monthly_rent=Decimal("100.01"))
        self.db.add(self.lease)
        self.db.flush()
        self.db.add_all([LeaseSignatory(lease_id=self.lease.lease_id, tenant_id=self.first.tenant_id),
                         LeaseSignatory(lease_id=self.lease.lease_id, tenant_id=self.second.tenant_id)])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_exact_split_idempotent_generation_and_payment_history(self):
        month = RentMonthCreate(billing_month=date(2026, 11, 1))
        self.assertEqual(generate_rent_month(month, db=self.db, _=self.admin)["created"], 1)
        self.assertEqual(generate_rent_month(month, db=self.db, _=self.admin)["created"], 0)
        payment = self.db.query(RentPayment).one()
        shares = payment.shares
        self.assertEqual([row.owed_amt for row in shares], [Decimal("50.01"), Decimal("50.00")])
        self.assertEqual(self.db.query(RentShare).count(), 2)
        self.assertEqual(my_rent(current_tenant=self.first, db=self.db)[0]["owed_amt"], Decimal("50.01"))
        self.assertEqual(my_rent(current_tenant=self.outsider, db=self.db), [])

        with self.assertRaises(HTTPException) as denied:
            report_rent_payment(shares[0].share_id, RentReportInput(), current_tenant=self.outsider, db=self.db)
        self.assertEqual(denied.exception.status_code, 404)
        report_rent_payment(shares[0].share_id, RentReportInput(reference="UPI-123"), current_tenant=self.first, db=self.db)
        self.assertEqual(shares[0].payment_status, "Pending Verification")
        self.assertIn("UPI-123", shares[0].ledger[-1].note)
        update_rent_status(shares[0].share_id, RentStatusInput(payment_status="Paid"), db=self.db, current_admin=self.admin)
        self.assertEqual(payment.payment_status, "Pending")
        update_rent_status(shares[1].share_id, RentStatusInput(payment_status="Paid"), db=self.db, current_admin=self.admin)
        self.assertEqual(payment.payment_status, "Paid")
        self.assertIsNotNone(payment.paid_on)
        update_rent_status(shares[1].share_id, RentStatusInput(payment_status="Unpaid"), db=self.db, current_admin=self.admin)
        self.assertEqual(payment.payment_status, "Pending")
        self.assertIsNone(payment.paid_on)
        self.assertEqual(self.db.query(RentPaymentLog).count(), 6)

    def test_new_signatory_changes_future_month_only(self):
        generate_rent_month(RentMonthCreate(billing_month=date(2026, 10, 1)), db=self.db, _=self.admin)
        self.db.add(LeaseSignatory(lease_id=self.lease.lease_id, tenant_id=self.outsider.tenant_id))
        self.db.commit()
        generate_rent_month(RentMonthCreate(billing_month=date(2026, 11, 1)), db=self.db, _=self.admin)
        october = self.db.query(RentPayment).filter(RentPayment.billing_month == date(2026, 10, 1)).one()
        november = self.db.query(RentPayment).filter(RentPayment.billing_month == date(2026, 11, 1)).one()
        self.assertEqual(len(october.shares), 2)
        self.assertEqual(len(november.shares), 3)
        self.assertEqual(sum((row.owed_amt for row in november.shares), Decimal("0")), Decimal("100.01"))


if __name__ == "__main__":
    unittest.main()
