"""
اختبارات ترحيل صيغة البيانات

الأخطر في المشروع كله: يعمل على بيانات محل حقيقية. كل شرط هنا يحرس
شيئاً يمكن أن يخسر مالاً إن انكسر.
"""
import json
import zipfile
from datetime import datetime
from decimal import Decimal

from core.migrations import SCHEMA_VERSION, run_migrations
from core.summaries import calculate_customer_summary


# ---------- كتابة بيانات بالصيغة القديمة ----------

def write_legacy(storage, customers=None, entries=None,
                 suppliers=None, items=None, payments=None):
    """يكتب ملفات بصيغة ما قبل الترحيل: بلا حقول id وبلا schema_version"""
    storage.customers_file.write_text(
        json.dumps(customers or [], ensure_ascii=False), encoding="utf-8")
    storage.suppliers_file.write_text(
        json.dumps(suppliers or [], ensure_ascii=False), encoding="utf-8")
    for path, records in [
        (storage.entries_file, entries or []),
        (storage.purchase_items_file, items or []),
        (storage.supplier_payments_file, payments or []),
    ]:
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
            encoding="utf-8")


def legacy_entry(customer_id, amount="20.00", desc="أغراض", type_="purchase"):
    """حركة بالصيغة القديمة — بلا حقل id"""
    return {
        "customer_id": customer_id, "type": type_, "amount": amount,
        "date": datetime(2025, 12, 11, 16, 6, 52).isoformat(),
        "desc": desc, "pay_method": "cash", "notes": "",
    }


def legacy_item(supplier_id, order_id="ord_1", total="50.00"):
    """بند شراء بالصيغة القديمة — بلا حقل id"""
    return {
        "order_id": order_id, "supplier_id": supplier_id, "item_name": "بندورة",
        "quantity": "10", "weight": "0", "price": "5.00",
        "packaging": "municipal", "payment_method": "credit",
        "total": total, "notes": "",
    }


CUSTOMER = {"id": "khalil_9518", "name": "خليل"}
SUPPLIER = {"id": "murad_1", "name": "مراد"}


# ---------- إضافة المعرّفات ----------

def test_assigns_ids_to_legacy_entries(storage):
    write_legacy(storage, customers=[CUSTOMER],
                 entries=[legacy_entry("khalil_9518", "20.00"),
                          legacy_entry("khalil_9518", "30.00")])

    report = run_migrations(storage)

    assert report.ran is True
    assert report.entry_ids_added == 2
    ids = [e.id for e in storage.load_entries()]
    assert all(ids) and len(set(ids)) == 2


def test_assigns_ids_to_legacy_purchase_items(storage):
    write_legacy(storage, suppliers=[SUPPLIER],
                 items=[legacy_item("murad_1"), legacy_item("murad_1")])

    report = run_migrations(storage)

    assert report.item_ids_added == 2
    ids = [i.id for i in storage.load_purchase_items()]
    assert all(ids) and len(set(ids)) == 2


def test_preserves_existing_ids(storage):
    record = legacy_entry("khalil_9518")
    record["id"] = "existing_id_abc"
    write_legacy(storage, customers=[CUSTOMER], entries=[record])

    report = run_migrations(storage)

    assert report.entry_ids_added == 0
    assert storage.load_entries()[0].id == "existing_id_abc"


def test_empty_id_treated_as_missing(storage):
    record = legacy_entry("khalil_9518")
    record["id"] = ""
    write_legacy(storage, customers=[CUSTOMER], entries=[record])

    assert run_migrations(storage).entry_ids_added == 1
    assert storage.load_entries()[0].id


# ---------- إزالة السجلات اليتيمة ----------

def test_removes_orphaned_entries(storage):
    """حركة لعميل غير موجود في customers.json"""
    write_legacy(storage, customers=[CUSTOMER],
                 entries=[legacy_entry("khalil_9518"),
                          legacy_entry("deleted_customer_0000")])

    report = run_migrations(storage)

    assert report.orphan_entries_removed == 1
    assert [e.customer_id for e in storage.load_entries()] == ["khalil_9518"]


def test_removes_orphaned_purchase_items(storage):
    write_legacy(storage, suppliers=[SUPPLIER],
                 items=[legacy_item("murad_1"), legacy_item("gone_supplier")])

    report = run_migrations(storage)

    assert report.orphan_items_removed == 1
    assert [i.supplier_id for i in storage.load_purchase_items()] == ["murad_1"]


def test_removes_orphaned_supplier_payments(storage):
    payment = {"id": "pay_1", "supplier_id": "gone_supplier", "amount": "100.00",
               "date": datetime(2026, 4, 1).isoformat(),
               "payment_method": "cash", "check_id": "", "notes": ""}
    write_legacy(storage, suppliers=[SUPPLIER], payments=[payment])

    report = run_migrations(storage)

    assert report.orphan_payments_removed == 1
    assert storage.load_supplier_payments() == []


# ---------- الأمان ----------

def test_creates_backup_before_writing(storage):
    write_legacy(storage, customers=[CUSTOMER], entries=[legacy_entry("khalil_9518")])

    report = run_migrations(storage)

    assert report.backup_path is not None and report.backup_path.exists()
    assert "pre-migration-v2" in report.backup_path.name
    with zipfile.ZipFile(report.backup_path) as z:
        # النسخة تحفظ الصيغة القديمة كما كانت — بلا معرّفات
        assert '"id"' not in z.read("entries.jsonl").decode("utf-8")


def test_is_idempotent(storage):
    """تشغيلها مرتين لا يغيّر شيئاً في الثانية — شرط أساسي"""
    write_legacy(storage, customers=[CUSTOMER], entries=[legacy_entry("khalil_9518")])

    run_migrations(storage)
    after_first = storage.entries_file.read_text(encoding="utf-8")

    second = run_migrations(storage)

    assert second.ran is False
    assert second.total_ids_added == 0
    assert second.total_orphans_removed == 0
    assert storage.entries_file.read_text(encoding="utf-8") == after_first


def test_sets_schema_version(storage):
    write_legacy(storage, customers=[CUSTOMER], entries=[legacy_entry("khalil_9518")])
    run_migrations(storage)
    assert storage.get_setting("schema_version") == SCHEMA_VERSION


def test_preserves_every_business_field(storage):
    """لا يفقد الترحيل أي حقل: المبلغ، التاريخ، الوصف، طريقة الدفع، الملاحظات"""
    record = legacy_entry("khalil_9518", "123.45", "بندورة وخيار", type_="payment")
    record["notes"] = "ملاحظة داخلية"
    record["pay_method"] = "transfer"
    write_legacy(storage, customers=[CUSTOMER], entries=[record])

    run_migrations(storage)

    entry = storage.load_entries()[0]
    assert entry.customer_id == "khalil_9518"
    assert entry.amount == "123.45"
    assert entry.desc == "بندورة وخيار"
    assert entry.notes == "ملاحظة داخلية"
    assert entry.pay_method == "transfer"
    assert entry.type == "payment"
    assert entry.date == record["date"]


def test_balances_are_identical_before_and_after(storage):
    """
    الشرط الحاسم قبل النشر: رصيد كل عميل لا يتغيّر بالترحيل.
    """
    entries = [
        legacy_entry("khalil_9518", "100.00"),
        legacy_entry("khalil_9518", "250.50"),
        legacy_entry("khalil_9518", "40.25", type_="payment"),
        legacy_entry("khalil_9518", "0.10"),
    ]
    write_legacy(storage, customers=[CUSTOMER], entries=entries)

    before = calculate_customer_summary("khalil_9518", storage.load_entries())
    run_migrations(storage)
    after = calculate_customer_summary("khalil_9518", storage.load_entries())

    assert before.balance_decimal == after.balance_decimal == Decimal("310.35")


def test_no_records_lost(storage):
    """عدد السجلات غير اليتيمة يبقى كما هو"""
    entries = [legacy_entry("khalil_9518", str(n)) for n in range(1, 26)]
    write_legacy(storage, customers=[CUSTOMER], entries=entries)

    run_migrations(storage)

    assert len(storage.load_entries()) == 25


def test_runs_on_empty_installation(storage):
    """تركيب جديد بلا بيانات — لا ينهار"""
    report = run_migrations(storage)
    assert report.ran is True
    assert report.total_ids_added == 0
    assert report.total_orphans_removed == 0


def test_arabic_summary_is_readable(storage):
    write_legacy(storage, customers=[CUSTOMER],
                 entries=[legacy_entry("khalil_9518"), legacy_entry("gone_0000")])
    summary = run_migrations(storage).summary_arabic()
    assert "1" in summary
    assert "نسخة احتياطية" in summary


def test_arabic_summary_when_nothing_to_do(storage):
    run_migrations(storage)
    assert run_migrations(storage).summary_arabic() == "البيانات محدّثة — لا حاجة لأي ترحيل."
