"""
اختبارات وظيفية: الترتيب داخل الشاشات الفعلية

تبني بيانات حقيقية، تفتح الشاشة، وتقرأ نص الجدول بعد الترتيب.
"""
import os
from datetime import datetime
from decimal import Decimal

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import make_customer, make_entry, make_supplier
from core.models import Check, PurchaseItem, PurchaseOrder


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def column_texts(table, column=0):
    return [table.item(r, column).text() for r in range(table.rowCount())
            if table.item(r, column)]


# ---------- قائمة العملاء ----------

@pytest.fixture
def customers_view(qt_app, storage):
    from ui.customers_view import CustomersView

    # أسماء تكشف مشكلة ترتيب اليونيكود، وأرصدة تكشف الترتيب النصّي
    data = [("khalil", "خليل", "900.00"),
            ("adam", "آدم", "1234.00"),
            ("ahmad", "أحمد", "50.00"),
            ("ibrahim", "ابراهيم", "300.00")]
    for cid, name, amount in data:
        storage.add_customer(make_customer(cid, name))
        storage.add_entry(make_entry(cid, amount=amount))

    return CustomersView(storage)


def test_customers_default_sort_is_alphabetical(customers_view):
    """
    الافتراضي المطلوب: أبجدي حسب الاسم.
    ترتيب اليونيكود الخام يعطي: آدم | أحمد | ابراهيم | خليل — غلط.
    """
    assert column_texts(customers_view.table, 0) == [
        "ابراهيم", "أحمد", "آدم", "خليل"
    ]


def test_customers_sort_by_balance_is_numeric(customers_view):
    """
    الضغط على عمود الرصيد يرتّب رقمياً.
    نصّياً كان «1,234.00» يسبق «900.00».
    """
    from PySide6.QtCore import Qt

    customers_view.table.sortItems(1, Qt.AscendingOrder)

    assert column_texts(customers_view.table, 0) == [
        "أحمد",      # 50
        "ابراهيم",   # 300
        "خليل",      # 900
        "آدم",       # 1234
    ]


def test_customers_sort_by_balance_descending(customers_view):
    from PySide6.QtCore import Qt

    customers_view.table.sortItems(1, Qt.DescendingOrder)

    assert column_texts(customers_view.table, 0)[0] == "آدم"      # الأكبر ديناً
    assert column_texts(customers_view.table, 0)[-1] == "أحمد"    # الأقل


def test_customers_search_keeps_sorting(customers_view):
    """التصفية لا تُفقد الترتيب"""
    customers_view.search_input.setText("ا")
    names = column_texts(customers_view.table, 0)
    assert names == sorted(names, key=lambda n: __import__(
        "core.utils", fromlist=["arabic_sort_key"]).arabic_sort_key(n))


# ---------- دفتر العميل ----------

@pytest.fixture
def ledger_view(qt_app, storage):
    from ui.customer_ledger import CustomerLedgerView

    storage.add_customer(make_customer("c1", "تجربة"))
    for day, amount in [(15, "100.00"), (3, "900.00"), (20, "1234.00")]:
        storage.add_entry(make_entry(
            "c1", amount=amount, date=datetime(2026, 1, day, 10, 0).isoformat()))

    view = CustomerLedgerView(storage)
    view.set_customer("c1")
    return view


def test_ledger_default_sort_is_newest_first(ledger_view):
    dates = column_texts(ledger_view.table, 0)
    assert dates[0].startswith("2026/01/20")
    assert dates[-1].startswith("2026/01/03")


def test_ledger_amount_column_sorts_numerically(ledger_view):
    from PySide6.QtCore import Qt

    ledger_view.table.sortItems(4, Qt.AscendingOrder)

    amounts = column_texts(ledger_view.table, 4)
    assert amounts[0].startswith("100.00")
    assert amounts[-1].startswith("1,234.00")


def test_ledger_context_menu_finds_entry_by_id_not_row(ledger_view, storage):
    """
    الإصلاح الإلزامي: قبل الترتيب كان الكود يستخدم filtered_entries[row].
    بعد الترتيب لم يعد رقم الصف يوافق موضع الحركة، فكان يفتح الحركة الخطأ.
    """
    from PySide6.QtCore import Qt

    # رتّب بالمبلغ تصاعدياً — يعكس ترتيب التاريخ الافتراضي
    ledger_view.table.sortItems(4, Qt.AscendingOrder)

    for row in range(ledger_view.table.rowCount()):
        entry_id = ledger_view.table.item(row, 0).data(Qt.UserRole)
        entry = storage.get_entry(entry_id)
        assert entry is not None, "المعرّف المخزَّن في الصف لا يقابل حركة"

        # المبلغ المعروض في الصف يخصّ نفس الحركة التي يشير إليها المعرّف
        shown_amount = ledger_view.table.item(row, 4).text()
        assert shown_amount.startswith(f"{entry.amount_decimal:,.2f}")


# ---------- الشيكات ----------

@pytest.fixture
def checks_view(qt_app, storage):
    from ui.checks_view import ChecksView

    storage.add_supplier(make_supplier("s1", "مراد"))
    for cid, number, amount, due_day in [
        ("chk_1", "111", "900.00", 20),
        ("chk_2", "222", "1234.00", 5),
        ("chk_3", "333", "50.00", 12),
    ]:
        storage.add_check(Check(
            id=cid, check_number=number, bank_name="البنك العربي", amount=amount,
            issue_date=datetime(2026, 1, 1).isoformat(),
            due_date=datetime(2026, 6, due_day).isoformat(),
            status="pending", direction="outgoing",
            party_type="supplier", party_id="s1", party_name="مراد",
        ))

    return ChecksView(storage)


def test_checks_default_sort_is_due_date_soonest_first(checks_view):
    """الأقرب استحقاقاً أولاً — ما يهمّ صاحب المحل"""
    assert column_texts(checks_view.table, 0) == ["222", "333", "111"]


def test_checks_sort_by_amount_is_numeric(checks_view):
    """
    جدول الشيكات فيه أزرار داخل الخلايا، فيُرتَّب على مستوى البيانات.
    """
    checks_view._sorter._on_header_clicked(2)   # عمود المبلغ

    amounts = column_texts(checks_view.table, 2)
    assert amounts[0].startswith("50.00")
    assert amounts[-1].startswith("1,234.00")


def test_checks_action_column_is_not_sortable(checks_view):
    """عمود الأزرار (8) غير قابل للترتيب — الضغط عليه لا يغيّر شيئاً"""
    before = column_texts(checks_view.table, 0)
    checks_view._sorter._on_header_clicked(8)
    assert column_texts(checks_view.table, 0) == before


def test_checks_buttons_match_their_row_after_sorting(checks_view):
    """
    الخطر: Qt يحرّك العناصر ولا يحرّك الودجات، فيصبح الزر تابعاً لشيك آخر.
    نتحقّق أن كل صف معلّق له ودجة أزرار خاصة به بعد إعادة الترتيب.
    """
    checks_view._sorter._on_header_clicked(2)   # أعد الترتيب بالمبلغ

    table = checks_view.table
    widget_rows = [r for r in range(table.rowCount())
                   if table.cellWidget(r, 8) is not None]
    # كل الشيكات معلّقة، فلكل صف ودجة، ولا ودجات زائدة
    assert len(widget_rows) == table.rowCount() == 3


def test_checks_repeated_click_toggles_direction(checks_view):
    checks_view._sorter._on_header_clicked(2)
    ascending = column_texts(checks_view.table, 2)
    checks_view._sorter._on_header_clicked(2)
    descending = column_texts(checks_view.table, 2)
    assert descending == list(reversed(ascending))


# ---------- الموردون ----------

@pytest.fixture
def suppliers_view(qt_app, storage):
    from ui.suppliers_view import SuppliersView

    for sid, name in [("s1", "خليل"), ("s2", "آدم"), ("s3", "ابراهيم")]:
        storage.add_supplier(make_supplier(sid, name))

    return SuppliersView(storage)


def test_suppliers_default_sort_is_alphabetical(suppliers_view):
    assert column_texts(suppliers_view.table, 0) == ["ابراهيم", "آدم", "خليل"]


# ---------- فواتير الشراء ----------

def test_purchase_orders_sort_by_total_numerically(qt_app, storage):
    from ui.purchase_order_view import PurchaseOrderView
    from PySide6.QtCore import Qt

    storage.add_supplier(make_supplier("s1", "مراد"))
    for oid, day, total in [("o1", 5, "900.00"), ("o2", 10, "1234.00"), ("o3", 1, "50.00")]:
        storage.add_purchase_order(PurchaseOrder(
            id=oid, date=datetime(2026, 4, day).isoformat()))
        storage.add_purchase_item(PurchaseItem(
            order_id=oid, supplier_id="s1", item_name="بندورة",
            quantity="1", weight="0", price=total,
            packaging="municipal", payment_method="credit", total=total))

    view = PurchaseOrderView(storage)
    # فلتر السجلّ الافتراضي «اليوم»؛ الفواتير هنا بتاريخ أبريل
    view.history_filter.setCurrentIndex(
        view.history_filter.findData("all"))
    view.refresh()

    # الافتراضي: الأحدث أولاً
    assert column_texts(view.orders_table, 0)[0].startswith("2026/04/10")

    # المجموع رقمياً
    view.orders_table.sortItems(2, Qt.AscendingOrder)
    totals = column_texts(view.orders_table, 2)
    assert totals[0].startswith("50.00")
    assert totals[-1].startswith("1,234.00")
