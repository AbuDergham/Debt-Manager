"""
اختبارات طبقة التخزين — CRUD وسجل التدقيق والكتابة الذرّية
"""
import json
import zipfile
from datetime import datetime

import pytest

from conftest import make_customer, make_entry, make_supplier
from core.models import Check, PurchaseItem, PurchaseOrder, Summary, SupplierPayment
from core.storage import atomic_write_jsonl


# ---------- بنّاؤون ----------

def make_item(order_id="ord_1", supplier_id="murad_1", **overrides) -> PurchaseItem:
    fields = dict(
        order_id=order_id, supplier_id=supplier_id, item_name="بندورة",
        quantity="10", weight="0", price="5.00",
        packaging="municipal", payment_method="credit", total="50.00",
    )
    fields.update(overrides)
    return PurchaseItem(**fields)


def make_order(oid="ord_1") -> PurchaseOrder:
    return PurchaseOrder(id=oid, date=datetime(2026, 4, 13).isoformat())


def make_payment(pid="pay_1", supplier_id="murad_1", **overrides) -> SupplierPayment:
    fields = dict(
        id=pid, supplier_id=supplier_id, amount="200.00",
        date=datetime(2026, 4, 13).isoformat(), payment_method="cash",
    )
    fields.update(overrides)
    return SupplierPayment(**fields)


def make_check(cid="chk_1", **overrides) -> Check:
    fields = dict(
        id=cid, check_number="12345", bank_name="البنك العربي", amount="500.00",
        issue_date=datetime(2026, 4, 1).isoformat(),
        due_date=datetime(2026, 6, 1).isoformat(),
        status="pending", direction="outgoing",
        party_type="supplier", party_id="murad_1", party_name="مراد",
    )
    fields.update(overrides)
    return Check(**fields)


# ---------- الكتابة الذرّية ----------

def test_atomic_write_jsonl_one_line_per_record(tmp_path):
    path = tmp_path / "out.jsonl"
    atomic_write_jsonl(path, [{"a": 1}, {"a": 2}, {"a": 3}])
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[1]) == {"a": 2}


def test_atomic_write_jsonl_preserves_arabic(tmp_path):
    path = tmp_path / "out.jsonl"
    atomic_write_jsonl(path, [{"name": "خليل بركات"}])
    assert "خليل بركات" in path.read_text(encoding="utf-8")


def test_atomic_write_jsonl_empty_list_truncates(tmp_path):
    path = tmp_path / "out.jsonl"
    path.write_text('{"old": true}\n', encoding="utf-8")
    atomic_write_jsonl(path, [])
    assert path.read_text(encoding="utf-8") == ""


def test_atomic_write_jsonl_leaves_no_temp_files(tmp_path):
    atomic_write_jsonl(tmp_path / "out.jsonl", [{"a": 1}])
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_jsonl_keeps_original_on_failure(tmp_path):
    """فشل في منتصف الكتابة يترك الملف الأصلي سليماً — قيد انقطاع الكهرباء"""
    path = tmp_path / "out.jsonl"
    path.write_text('{"original": true}\n', encoding="utf-8")
    with pytest.raises(TypeError):
        atomic_write_jsonl(path, [{"bad": object()}])
    assert path.read_text(encoding="utf-8") == '{"original": true}\n'
    assert list(tmp_path.glob("*.tmp")) == []


# ---------- سجل التدقيق ----------

def test_add_customer_is_audited(storage):
    storage.add_customer(make_customer())
    history = storage.audit.get_history(entity_type="customer")
    assert len(history) == 1
    assert history[0].action == "create"
    assert history[0].new_data["name"] == "أحمد"


def test_add_entry_is_audited(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    history = storage.audit.get_history(entity_type="entry")
    assert [h.entity_id for h in history] == [entry.id]


def test_audit_failure_never_blocks_business_operation(storage, monkeypatch):
    """قرار مقصود: لا نخسر تسجيل بيعة لأن ملف السجل تعذّرت الكتابة فيه"""
    monkeypatch.setattr(
        storage.audit, "log_action",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    storage.add_customer(make_customer())
    assert len(storage.load_customers()) == 1


# ---------- CRUD الحركات ----------

def test_save_entries_round_trip(storage):
    storage.add_customer(make_customer())
    entries = [make_entry(amount="10.00"), make_entry(amount="20.00")]
    storage.save_entries(entries)
    loaded = storage.load_entries()
    assert [e.amount for e in loaded] == ["10.00", "20.00"]
    assert [e.id for e in loaded] == [e.id for e in entries]


def test_get_entry_by_id(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    assert storage.get_entry(entry.id).amount == "100.00"


def test_get_entry_returns_none_when_missing(storage):
    assert storage.get_entry("nope") is None


def test_update_entry_changes_only_target(storage):
    storage.add_customer(make_customer())
    a, b = make_entry(amount="10.00"), make_entry(amount="20.00")
    storage.add_entry(a); storage.add_entry(b)

    a.amount = "15.00"
    storage.update_entry(a)

    assert storage.get_entry(a.id).amount == "15.00"
    assert storage.get_entry(b.id).amount == "20.00"


def test_update_entry_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.update_entry(make_entry())


def test_update_entry_rejects_invalid(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    entry.amount = "-5.00"
    with pytest.raises(ValueError):
        storage.update_entry(entry)


def test_delete_entry_removes_only_target(storage):
    storage.add_customer(make_customer())
    a, b = make_entry(amount="10.00"), make_entry(amount="20.00")
    storage.add_entry(a); storage.add_entry(b)

    removed = storage.delete_entry(a.id)

    assert removed.id == a.id
    assert storage.get_entry(a.id) is None
    assert storage.get_entry(b.id) is not None


def test_delete_correct_one_of_two_identical_entries(storage):
    """
    جوهر الإصلاح: حركتان متطابقتان في العميل والتاريخ والمبلغ والوصف.
    المطابقة الرباعية القديمة كانت تحذف الأولى دائماً.
    """
    storage.add_customer(make_customer())
    first, second = make_entry(), make_entry()
    storage.add_entry(first); storage.add_entry(second)

    storage.delete_entry(second.id)

    remaining = storage.load_entries()
    assert [e.id for e in remaining] == [first.id]


def test_delete_entry_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.delete_entry("nope")


def test_update_entry_is_audited(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    entry.amount = "55.00"
    storage.update_entry(entry)

    update = next(h for h in storage.audit.get_history(entity_id=entry.id)
                  if h.action == "update")
    assert update.old_data["amount"] == "100.00"
    assert update.new_data["amount"] == "55.00"


def test_delete_entry_is_audited(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    storage.delete_entry(entry.id)
    assert any(h.action == "delete" and h.old_data["amount"] == "100.00"
               for h in storage.audit.get_history(entity_id=entry.id))


# ---------- CRUD العملاء ----------

def test_update_customer(storage):
    storage.add_customer(make_customer())
    storage.update_customer(make_customer(name="أحمد محمود", phone="0599123456",
                                          credit_limit="500.00"))
    loaded = storage.get_customer("ahmad_1234")
    assert (loaded.name, loaded.phone, loaded.credit_limit) == ("أحمد محمود", "0599123456", "500.00")


def test_update_customer_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.update_customer(make_customer())


def test_delete_customer_removes_their_entries(storage):
    """المشكلة الأصلية: الحركات كانت تبقى يتيمة بعد حذف العميل"""
    storage.add_customer(make_customer("ahmad_1234", "أحمد"))
    storage.add_customer(make_customer("khalil_5678", "خليل"))
    storage.add_entry(make_entry("ahmad_1234", amount="10.00"))
    storage.add_entry(make_entry("ahmad_1234", amount="20.00"))
    storage.add_entry(make_entry("khalil_5678", amount="30.00"))

    customer, deleted, backup_path = storage.delete_customer("ahmad_1234")

    assert customer.name == "أحمد"
    assert deleted == 2
    assert [e.customer_id for e in storage.load_entries()] == ["khalil_5678"]


def test_delete_customer_creates_backup_of_prior_state(storage):
    storage.add_customer(make_customer())
    storage.add_entry(make_entry())

    _, _, backup_path = storage.delete_customer("ahmad_1234")

    assert backup_path.exists()
    with zipfile.ZipFile(backup_path) as z:
        assert "أحمد" in z.read("customers.json").decode("utf-8")
        assert z.read("entries.jsonl").decode("utf-8").strip()


def test_delete_customer_removes_summary(storage):
    storage.add_customer(make_customer())
    storage.save_summaries({"ahmad_1234": Summary.empty()})
    storage.delete_customer("ahmad_1234")
    assert "ahmad_1234" not in storage.load_summaries()


def test_delete_customer_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.delete_customer("nope")


def test_customer_id_reuse_is_safe_after_delete(storage):
    """الخطر الأصلي: عميل جديد يرث ديون عميل محذوف بنفس المعرّف"""
    storage.add_customer(make_customer("ahmad_1234", "أحمد"))
    storage.add_entry(make_entry("ahmad_1234", amount="500.00"))
    storage.delete_customer("ahmad_1234")

    storage.add_customer(make_customer("ahmad_1234", "أحمد آخر"))

    assert storage.get_customer_entries("ahmad_1234") == []


# ---------- CRUD الموردين (مع الحذف المتتالي) ----------

def test_update_supplier(storage):
    storage.add_supplier(make_supplier())
    storage.update_supplier(make_supplier(name="مراد حسن", phone="0599888"))
    loaded = storage.get_supplier("murad_1")
    assert (loaded.name, loaded.phone) == ("مراد حسن", "0599888")


def test_update_supplier_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.update_supplier(make_supplier())


def test_delete_supplier_cascades_to_items_and_payments(storage):
    """حذف مورد يزيل بنود شرائه ودفعاته وملخصه — لا سجلات يتيمة"""
    storage.add_supplier(make_supplier("murad_1", "مراد"))
    storage.add_supplier(make_supplier("sami_2", "سامي"))
    storage.add_purchase_order(make_order("ord_1"))
    storage.add_purchase_item(make_item(supplier_id="murad_1"))
    storage.add_purchase_item(make_item(supplier_id="murad_1"))
    storage.add_purchase_item(make_item(supplier_id="sami_2"))
    storage.add_supplier_payment(make_payment("pay_1", "murad_1"))
    storage.add_supplier_payment(make_payment("pay_2", "sami_2"))

    supplier, counts, backup_path = storage.delete_supplier("murad_1")

    assert supplier.name == "مراد"
    assert counts == {"items": 2, "payments": 1}
    assert [i.supplier_id for i in storage.load_purchase_items()] == ["sami_2"]
    assert [p.supplier_id for p in storage.load_supplier_payments()] == ["sami_2"]
    assert backup_path.exists()


def test_delete_supplier_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.delete_supplier("nope")


# ---------- CRUD بنود الشراء ----------

def test_get_purchase_item_by_id(storage):
    storage.add_supplier(make_supplier())
    storage.add_purchase_order(make_order())
    item = make_item()
    storage.add_purchase_item(item)
    assert storage.get_purchase_item(item.id).item_name == "بندورة"


def test_update_purchase_item(storage):
    storage.add_supplier(make_supplier())
    storage.add_purchase_order(make_order())
    item = make_item()
    storage.add_purchase_item(item)

    item.total = "75.00"
    storage.update_purchase_item(item)

    assert storage.get_purchase_item(item.id).total == "75.00"


def test_delete_correct_one_of_two_identical_items(storage):
    """بندان متطابقان في نفس الفاتورة — نفس مشكلة الحركات"""
    storage.add_supplier(make_supplier())
    storage.add_purchase_order(make_order())
    first, second = make_item(), make_item()
    storage.add_purchase_item(first); storage.add_purchase_item(second)

    storage.delete_purchase_item(second.id)

    assert [i.id for i in storage.load_purchase_items()] == [first.id]


def test_delete_purchase_item_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.delete_purchase_item("nope")


# ---------- CRUD فواتير الشراء ----------

def test_delete_purchase_order_cascades_to_its_items(storage):
    storage.add_supplier(make_supplier())
    storage.add_purchase_order(make_order("ord_1"))
    storage.add_purchase_order(make_order("ord_2"))
    storage.add_purchase_item(make_item(order_id="ord_1"))
    storage.add_purchase_item(make_item(order_id="ord_1"))
    storage.add_purchase_item(make_item(order_id="ord_2"))

    order, deleted, backup_path = storage.delete_purchase_order("ord_1")

    assert order.id == "ord_1"
    assert deleted == 2
    assert [i.order_id for i in storage.load_purchase_items()] == ["ord_2"]


def test_delete_purchase_order_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.delete_purchase_order("nope")


# ---------- CRUD الدفعات والشيكات ----------

def test_delete_supplier_payment(storage):
    storage.add_supplier(make_supplier())
    storage.add_supplier_payment(make_payment("pay_1"))
    storage.add_supplier_payment(make_payment("pay_2"))

    storage.delete_supplier_payment("pay_1")

    assert [p.id for p in storage.load_supplier_payments()] == ["pay_2"]


def test_delete_check(storage):
    storage.add_check(make_check("chk_1"))
    storage.add_check(make_check("chk_2"))

    storage.delete_check("chk_1")

    assert [c.id for c in storage.load_checks()] == ["chk_2"]


def test_delete_check_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.delete_check("nope")


def test_update_check_status_still_works(storage):
    """الدالة الموجودة مسبقاً لا يجب أن تنكسر"""
    storage.add_check(make_check("chk_1"))
    storage.update_check_status("chk_1", "cashed")
    assert storage.get_check("chk_1").status == "cashed"


def test_supplier_deletion_is_audited(storage):
    storage.add_supplier(make_supplier())
    storage.delete_supplier("murad_1")
    assert any(h.action == "delete" and h.old_data["name"] == "مراد"
               for h in storage.audit.get_history(entity_id="murad_1"))
