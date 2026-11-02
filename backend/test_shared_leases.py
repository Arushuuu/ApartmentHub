import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ApartmentUnit, DepositContribution, DepositLedgerEntry, LeaseSignatory, SecurityDeposit, Tenant
from app.routers.account import complete_setup
from app.routers.leases import my_leases
from app.routers.shared_leases import (ContributionAdd, RefundAdd, RefundReconcile,
    SharedLeaseCreate, SignatoryAdd, add_contribution, add_signatory,
    create_shared_lease, record_refund, reconcile_refund)
from app.routers.admin import UtilityBillCreateInput, create_utility_bill, delete_user
from app.schemas import AccountSetup


class SharedLeaseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.admin = Tenant(tenant_name="Admin", t_email="admin@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="1")
        self.first = Tenant(tenant_name="First", t_email="first@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="2")
        self.second = Tenant(tenant_name="Second", t_email="second@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="3")
        self.unit = ApartmentUnit(building_name="Maple", street="Main Road", unit_no="1", pincode="123456", base_rent=Decimal("12000"))
        self.db.add_all([self.admin, self.first, self.second, self.unit])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_shared_lease_deposit_and_bill_split(self):
        lease = create_shared_lease(SharedLeaseCreate(
            unit_id=self.unit.unit_id, primary_tenant_id=self.first.tenant_id,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), monthly_rent=Decimal("12000")),
            db=self.db, _=self.admin)
        lease_id = lease["lease_id"]
        lease = add_signatory(lease_id, SignatoryAdd(tenant_id=self.second.tenant_id), db=self.db, _=self.admin)
        self.assertEqual(len(lease["signatories"]), 2)
        self.assertEqual(my_leases(current_tenant=self.second, db=self.db)[0]["lease_id"], lease_id)
        with self.assertRaises(HTTPException) as denied:
            delete_user(self.second.tenant_id, db=self.db, current_admin=self.admin)
        self.assertEqual(denied.exception.status_code, 409)

        lease = add_contribution(lease_id, ContributionAdd(tenant_id=self.first.tenant_id, amount=Decimal("6000")), db=self.db, current_admin=self.admin)
        lease = add_contribution(lease_id, ContributionAdd(tenant_id=self.second.tenant_id, amount=Decimal("4000")), db=self.db, current_admin=self.admin)
        self.assertEqual(lease["deposit"]["amount_held"], Decimal("10000"))
        self.assertEqual(lease["deposit"]["remaining_balance"], Decimal("10000"))

        bill = create_utility_bill(UtilityBillCreateInput(
            unit_id=self.unit.unit_id, total_amount=Decimal("100.01"),
            bill_date=date(2026, 11, 2), due_date=date(2026, 11, 9)),
            db=self.db, current_admin=self.admin)
        self.assertEqual(sorted(share["owed_amt"] for share in bill["shares"]),
                         [Decimal("50.00"), Decimal("50.01")])

        lease = record_refund(lease_id, RefundAdd(tenant_id=self.second.tenant_id, amount=Decimal("1000")), db=self.db, current_admin=self.admin)
        self.assertEqual(lease["deposit"]["refund_status"], "Partial Refund")
        self.assertEqual(lease["deposit"]["remaining_balance"], Decimal("9000"))
        with self.assertRaises(HTTPException) as denied:
            record_refund(lease_id, RefundAdd(tenant_id=self.second.tenant_id, amount=Decimal("3001")), db=self.db, current_admin=self.admin)
        self.assertEqual(denied.exception.status_code, 400)

        lease = record_refund(lease_id, RefundAdd(tenant_id=self.second.tenant_id, amount=Decimal("3000")), db=self.db, current_admin=self.admin)
        lease = record_refund(lease_id, RefundAdd(tenant_id=self.first.tenant_id, amount=Decimal("6000")), db=self.db, current_admin=self.admin)
        self.assertEqual(lease["deposit"]["remaining_balance"], Decimal("0"))
        self.assertEqual(lease["deposit"]["refund_status"], "Fully Refunded")

    def test_legacy_partial_refund_requires_reconciliation(self):
        lease = create_shared_lease(SharedLeaseCreate(
            unit_id=self.unit.unit_id, primary_tenant_id=self.first.tenant_id,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), monthly_rent=Decimal("12000")),
            db=self.db, _=self.admin)
        lease_id = lease["lease_id"]
        lease = add_contribution(lease_id, ContributionAdd(tenant_id=self.first.tenant_id, amount=Decimal("5000")), db=self.db, current_admin=self.admin)
        contribution = self.db.get(DepositContribution, (lease["deposit"]["deposit_id"], self.first.tenant_id))
        contribution.refunded_amt = None
        contribution.deposit.refund_status = "Partial Refund"
        self.db.commit()

        with self.assertRaises(HTTPException) as denied:
            record_refund(lease_id, RefundAdd(tenant_id=self.first.tenant_id, amount=Decimal("100")), db=self.db, current_admin=self.admin)
        self.assertEqual(denied.exception.status_code, 409)
        lease = reconcile_refund(lease_id, RefundReconcile(tenant_id=self.first.tenant_id, refunded_amount=Decimal("1200")), db=self.db, current_admin=self.admin)
        self.assertFalse(lease["deposit"]["needs_reconciliation"])
        self.assertEqual(lease["deposit"]["remaining_balance"], Decimal("3800"))

    def test_unattributed_legacy_amount_is_allocated_without_double_counting(self):
        lease = create_shared_lease(SharedLeaseCreate(
            unit_id=self.unit.unit_id, primary_tenant_id=self.first.tenant_id,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), monthly_rent=Decimal("12000")),
            db=self.db, _=self.admin)
        lease_id = lease["lease_id"]
        add_signatory(lease_id, SignatoryAdd(tenant_id=self.second.tenant_id), db=self.db, _=self.admin)
        lease = add_contribution(lease_id, ContributionAdd(tenant_id=self.first.tenant_id, amount=Decimal("5000")), db=self.db, current_admin=self.admin)
        deposit = self.db.get(DepositContribution, (lease["deposit"]["deposit_id"], self.first.tenant_id)).deposit
        deposit.amount_held = Decimal("10000")
        self.db.commit()

        with self.assertRaises(HTTPException) as denied:
            record_refund(lease_id, RefundAdd(tenant_id=self.first.tenant_id, amount=Decimal("100")), db=self.db, current_admin=self.admin)
        self.assertEqual(denied.exception.status_code, 409)
        lease = add_contribution(lease_id, ContributionAdd(tenant_id=self.second.tenant_id, amount=Decimal("5000")), db=self.db, current_admin=self.admin)
        self.assertEqual(lease["deposit"]["amount_held"], Decimal("10000"))
        self.assertEqual(lease["deposit"]["unattributed_amt"], Decimal("0"))
        self.assertEqual(lease["deposit"]["ledger"][-1]["action"], "Allocation")

    def test_tenant_setup_creates_signatory_and_deposit_contribution(self):
        result = complete_setup(AccountSetup(
            existing_unit_id=self.unit.unit_id, start_date=date(2026, 11, 1),
            end_date=date(2027, 10, 31), monthly_rent=Decimal("12000"),
            deposit_amount=Decimal("24000")), current_tenant=self.first, db=self.db)
        self.assertTrue(result["created"])
        self.assertEqual(self.db.query(LeaseSignatory).filter_by(tenant_id=self.first.tenant_id).count(), 1)
        deposit = self.db.query(SecurityDeposit).one()
        contribution = self.db.get(DepositContribution, (deposit.deposit_id, self.first.tenant_id))
        self.assertEqual(contribution.contributed_amt, Decimal("24000"))
        self.assertEqual(self.db.query(DepositLedgerEntry).count(), 1)


if __name__ == "__main__":
    unittest.main()
