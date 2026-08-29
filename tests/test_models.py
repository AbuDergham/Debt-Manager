"""
اختبارات نماذج البيانات
"""
from datetime import datetime
from decimal import Decimal

import pytest

from conftest import make_customer, make_entry
from core.models import (
    Check,
    Customer,
    Entry,
    PurchaseItem,
    Summary,
    Supplier,
    new_id,
)


# ---------- توليد المعرّفات ----------

def test_new_id_is_unique():
    assert len({new_id() for _ in range(2000)}) == 2000


def test_new_id_is_hex32():
    value = new_id()
    assert len(value) == 32
    assert all(c in "0123456789abcdef" for c in value)


# ---------- Entry ----------

def test_entry_gets_id_automatically():
    assert len(make_entry().id) == 32


def test_two_identical_entries_have_different_ids():
    """
    جوهر الإصلاح: عميل يشتري «أغراض» بـ 100 مرتين في نفس الدقيقة.
    المطابقة الرباعية القديمة (عميل+تاريخ+مبلغ+وصف) كانت تخلط بينهما.
    """
    a, b = make_entry(), make_entry()
    assert (a.customer_id, a.date, a.amount, a.desc) == (b.customer_id, b.date, b.amount, b.desc)
    assert a.id != b.id


def test_entry_to_dict_includes_id():
    entry = make_entry()
    assert entry.to_dict()["id"] == entry.id


def test_entry_round_trip_preserves_id():
    entry = make_entry()
    assert Entry.from_dict(entry.to_dict()) == entry


def test_entry_from_dict_generates_id_when_missing():
    """سجل بالصيغة القديمة (بلا حقل id) يحصل على واحد عند القراءة"""
    legacy = {
        "customer_id": "ahmad_1234",
        "type": "purchase",
        "amount": "100.00",
        "date": datetime(2026, 1, 15).isoformat(),
        "desc": "أغراض",
        "pay_method": "cash",
    }
    assert len(Entry.from_dict(legacy).id) == 32


def test_entry_from_dict_treats_empty_id_as_missing():
    record = make_entry().to_dict()
    record["id"] = ""
    assert Entry.from_dict(record).id


def test_entry_signed_amount_purchase_positive():
    assert make_entry(type="purchase", amount="100.00").signed_amount == Decimal("100.00")


def test_entry_signed_amount_payment_negative():
    assert make_entry(type="payment", amount="40.00").signed_amount == Decimal("-40.00")


@pytest.mark.parametrize("amount", ["0.00", "-5.00"])
def test_entry_validate_rejects_non_positive_amount(amount):
    with pytest.raises(ValueError, match="positive"):
        make_entry(amount=amount).validate()


def test_entry_validate_rejects_bad_type():
    with pytest.raises(ValueError, match="Invalid entry type"):
        make_entry(type="refund").validate()


def test_entry_validate_rejects_bad_pay_method():
    with pytest.raises(ValueError, match="Invalid payment method"):
        make_entry(pay_method="crypto").validate()


def test_entry_validate_accepts_valid():
    assert make_entry().validate() is True


# ---------- PurchaseItem ----------

def make_item(**overrides) -> PurchaseItem:
    fields = dict(
        order_id="ord_1", supplier_id="murad_1", item_name="بندورة",
        quantity="10", weight="0", price="5.00",
        packaging="municipal", payment_method="credit", total="50.00",
    )
    fields.update(overrides)
    return PurchaseItem(**fields)


def test_purchase_item_gets_id_automatically():
    assert len(make_item().id) == 32


def test_two_identical_purchase_items_have_different_ids():
    """نفس مشكلة Entry: بندان متطابقان في نفس الفاتورة"""
    a, b = make_item(), make_item()
    assert a.id != b.id


def test_purchase_item_round_trip_preserves_id():
    item = make_item()
    assert PurchaseItem.from_dict(item.to_dict()) == item


def test_purchase_item_from_dict_generates_id_when_missing():
    legacy = make_item().to_dict()
    del legacy["id"]
    assert len(PurchaseItem.from_dict(legacy).id) == 32


def test_purchase_item_total_by_quantity_and_price():
    assert PurchaseItem.calculate_total("10", "0", "5.00") == Decimal("50.00")


def test_purchase_item_total_by_weight_and_price():
    assert PurchaseItem.calculate_total("0", "12.5", "4.00") == Decimal("50.00")


def test_purchase_item_total_by_quantity_weight_and_price():
    assert PurchaseItem.calculate_total("2", "10", "3.00") == Decimal("60.00")


def test_purchase_item_total_zero_without_price():
    assert PurchaseItem.calculate_total("10", "5", "0") == Decimal("0")


# ---------- Customer ----------

def test_customer_round_trip():
    customer = make_customer(phone="0599123456", credit_limit="500.00", notes="زبون قديم")
    assert Customer.from_dict(customer.to_dict()) == customer


def test_customer_from_dict_defaults_missing_fields():
    customer = Customer.from_dict({"id": "x_1", "name": "خليل"})
    assert (customer.phone, customer.credit_limit, customer.notes) == ("", "0", "")


def test_customer_credit_limit_decimal():
    assert make_customer(credit_limit="500.00").credit_limit_decimal == Decimal("500.00")


def test_customer_empty_credit_limit_is_zero():
    assert make_customer(credit_limit="").credit_limit_decimal == Decimal("0")


# ---------- Supplier / Check / Summary ----------

def test_supplier_round_trip():
    supplier = Supplier(id="murad_1", name="مراد", phone="0599", notes="ملاحظة")
    assert Supplier.from_dict(supplier.to_dict()) == supplier


def test_check_status_helpers():
    def check(status):
        return Check(
            id="c1", check_number="123", bank_name="البنك العربي", amount="500.00",
            issue_date=datetime(2026, 1, 1).isoformat(),
            due_date=datetime(2026, 3, 1).isoformat(),
            status=status, direction="outgoing",
            party_type="supplier", party_id="murad_1", party_name="مراد",
        )
    assert check("pending").is_pending
    assert check("cashed").is_cashed
    assert check("bounced").is_bounced
    assert not check("cashed").is_pending


def test_summary_empty_is_zero():
    summary = Summary.empty()
    assert summary.balance_decimal == Decimal("0.00")
    assert summary.today_sales_decimal == Decimal("0.00")
    assert summary.month_sales_decimal == Decimal("0.00")
