"""
تعديل الشيكات وحذفها والتحقق من تواريخها

السبب الجذري لحادثة ١٨ أكتوبر: أُدخل شيك بتاريخ استحقاق **قبل** تاريخ
إصداره (إصدار 2027-10-10، استحقاق 2027-02-25)، ولم تكن هناك أي طريقة
لتعديله أو حذفه من داخل البرنامج — فاضطر أحدهم لفتح `checks.json` بمحرّر
نصوص، فأضاف المحرّر علامة BOM، فمات التطبيق.

تحمّل الـBOM يعالج العَرَض. هذه الاختبارات تعالج السبب.
"""
import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import make_supplier
from core.models import Check


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def make_check(cid="chk_1", issue_days=-30, due_days=30, **overrides):
    now = datetime(2026, 10, 18, 12, 0)
    fields = dict(
        id=cid, check_number="445120", bank_name="البنك العربي",
        amount="2500.00",
        issue_date=(now + timedelta(days=issue_days)).isoformat(),
        due_date=(now + timedelta(days=due_days)).isoformat(),
        status="pending", direction="outgoing",
        party_type="supplier", party_id="murad", party_name="مراد",
    )
    fields.update(overrides)
    return Check(**fields)


# ---------- التحقق من التواريخ ----------

def test_check_validate_rejects_due_before_issue():
    """الشيك الذي سبّب الحادثة: استحقاق قبل الإصدار"""
    bad = make_check(issue_days=30, due_days=-30)
    with pytest.raises(ValueError, match="الاستحقاق"):
        bad.validate()


def test_check_validate_accepts_due_equal_issue():
    """شيك يُصرف يوم إصداره — مقبول"""
    make_check(issue_days=0, due_days=0).validate()


def test_check_validate_accepts_normal_dates():
    assert make_check().validate() is True


def test_check_validate_rejects_non_positive_amount():
    with pytest.raises(ValueError, match="المبلغ"):
        make_check(amount="0.00").validate()


def test_check_validate_rejects_empty_number():
    with pytest.raises(ValueError, match="رقم الشيك"):
        make_check(check_number="   ").validate()


def test_check_validate_rejects_bad_status():
    with pytest.raises(ValueError, match="حالة"):
        make_check(status="lost").validate()


def test_check_validate_rejects_bad_direction():
    with pytest.raises(ValueError, match="اتجاه"):
        make_check(direction="sideways").validate()


# ---------- التخزين يرفض غير الصالح ----------

def test_add_check_rejects_invalid(storage):
    storage.add_supplier(make_supplier("murad", "مراد"))
    with pytest.raises(ValueError):
        storage.add_check(make_check(issue_days=30, due_days=-30))
    assert storage.load_checks() == []


def test_update_check_rejects_invalid(storage):
    storage.add_supplier(make_supplier("murad", "مراد"))
    check = make_check()
    storage.add_check(check)

    check.due_date = (datetime(2026, 1, 1)).isoformat()      # قبل الإصدار
    with pytest.raises(ValueError):
        storage.update_check(check)

    assert storage.get_check(check.id).due_date != check.due_date


# ---------- التعديل والحذف من التخزين ----------

def test_update_check_changes_dates(storage):
    storage.add_supplier(make_supplier("murad", "مراد"))
    check = make_check()
    storage.add_check(check)

    check.due_date = datetime(2026, 12, 1).isoformat()
    check.amount = "3000.00"
    storage.update_check(check)

    stored = storage.get_check(check.id)
    assert stored.amount == "3000.00"
    assert stored.due_datetime.month == 12


def test_update_check_is_audited(storage):
    storage.add_supplier(make_supplier("murad", "مراد"))
    check = make_check()
    storage.add_check(check)

    check.amount = "999.00"
    storage.update_check(check)

    history = storage.audit.get_history(entity_type="check", entity_id=check.id)
    update = next(h for h in history if h.action == "update")
    assert update.old_data["amount"] == "2500.00"
    assert update.new_data["amount"] == "999.00"


def test_delete_check_removes_it(storage):
    storage.add_supplier(make_supplier("murad", "مراد"))
    storage.add_check(make_check("chk_1"))
    storage.add_check(make_check("chk_2"))

    storage.delete_check("chk_1")

    assert [c.id for c in storage.load_checks()] == ["chk_2"]


def test_update_check_status_is_now_audited(storage):
    """
    كانت update_check_status تكتب checks.json بلا تسجيل تدقيق، بخلاف كل
    عمليات التعديل الأخرى — فثغرة في التتبّع.
    """
    storage.add_supplier(make_supplier("murad", "مراد"))
    check = make_check()
    storage.add_check(check)

    storage.update_check_status(check.id, "cashed")

    history = storage.audit.get_history(entity_type="check", entity_id=check.id)
    assert any(h.action == "update" and h.new_data["status"] == "cashed"
               for h in history), "تغيير الحالة لم يُسجَّل"


def test_update_check_status_rejects_unknown_status(storage):
    storage.add_supplier(make_supplier("murad", "مراد"))
    check = make_check()
    storage.add_check(check)

    with pytest.raises(ValueError):
        storage.update_check_status(check.id, "ضائع")


# ---------- الواجهة ----------

def test_checks_view_has_edit_and_delete(qt_app, storage):
    """بدونهما يضطر المستخدم لفتح الملف بمحرّر نصوص"""
    from ui.checks_view import ChecksView

    storage.add_supplier(make_supplier("murad", "مراد"))
    storage.add_check(make_check())

    view = ChecksView(storage)

    assert hasattr(view, "edit_check"), "لا توجد دالة تعديل"
    assert hasattr(view, "delete_check"), "لا توجد دالة حذف"


def test_checks_view_edit_finds_check_by_id_not_row(qt_app, storage):
    """الجدول مرتَّب، فرقم الصف لا يوافق موضع الشيك في القائمة"""
    from PySide6.QtCore import Qt
    from ui.checks_view import ChecksView

    storage.add_supplier(make_supplier("murad", "مراد"))
    for n, due in [("chk_a", 40), ("chk_b", 5), ("chk_c", 20)]:
        storage.add_check(make_check(n, due_days=due))

    view = ChecksView(storage)

    for row in range(view.table.rowCount()):
        check_id = view.table.item(row, 0).data(Qt.UserRole)
        shown_number = view.table.item(row, 0).text()
        assert storage.get_check(check_id).check_number == shown_number
