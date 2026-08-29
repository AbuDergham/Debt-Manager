"""
اختبارات وظيفية للطباعة عبر الشاشات الفعلية
"""
import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import make_customer, make_entry
from core.reports import PAPER_A4, PAPER_THERMAL_58, PAPER_THERMAL_80


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def seeded(storage):
    """محل بثلاثة عملاء وحركات"""
    storage.update_setting("shop_name", "محل أبو درغام للخضار")
    storage.update_setting("shop_phone", "0569337729")

    for cid, name, amount in [("c1", "خليل بركات", "900.00"),
                              ("c2", "أحمد محمود", "1234.00"),
                              ("c3", "آدم سالم", "50.00")]:
        storage.add_customer(make_customer(cid, name, phone="0599000111"))
        storage.add_entry(make_entry(cid, amount=amount, desc="بندورة وخيار",
                                     date=datetime(2026, 1, 10, 9, 0).isoformat()))
    storage.add_entry(make_entry("c1", type="payment", amount="200.00",
                                 desc="دفعة نقدية",
                                 date=datetime(2026, 1, 20, 14, 0).isoformat()))
    return storage


# ---------- تقرير كل العملاء من قائمة العملاء ----------

def test_customers_view_report_matches_screen_order(qt_app, seeded):
    from ui.customers_view import CustomersView

    view = CustomersView(seeded)
    visible = view.visible_customers()

    # نفس ترتيب الشاشة (أبجدي افتراضاً).
    # بعد التطبيع: «احمد» و«ادم» و«خليل» — والحاء تسبق الدال تسبق الخاء.
    assert [c.name for c in visible] == ["أحمد محمود", "آدم سالم", "خليل بركات"]


def test_customers_view_report_respects_search_filter(qt_app, seeded):
    from ui.customers_view import CustomersView

    view = CustomersView(seeded)
    view.search_input.setText("خليل")

    assert [c.name for c in view.visible_customers()] == ["خليل بركات"]


def test_customers_report_carries_shop_info(qt_app, seeded):
    from core.reports import build_customers_report
    from ui.customers_view import CustomersView

    view = CustomersView(seeded)
    html = build_customers_report(
        view.visible_customers(), view.summaries, view.report_context(), PAPER_A4)

    assert "محل أبو درغام للخضار" in html
    assert "0569337729" in html


def test_customers_report_pdf_from_view(qt_app, seeded, tmp_path):
    from core.reports import build_customers_report
    from ui.customers_view import CustomersView
    from ui.printing import export_pdf

    view = CustomersView(seeded)
    html = build_customers_report(
        view.visible_customers(), view.summaries, view.report_context(), PAPER_A4)

    path = tmp_path / "customers.pdf"
    export_pdf(html, str(path))

    assert path.read_bytes()[:5] == b"%PDF-"
    assert path.stat().st_size > 1500


# ---------- كشف حساب العميل من الدفتر ----------

@pytest.fixture
def ledger(qt_app, seeded):
    from ui.customer_ledger import CustomerLedgerView

    view = CustomerLedgerView(seeded)
    view.set_customer("c1")
    return view


def test_ledger_report_uses_visible_entries(ledger):
    """التقرير يطبع ما يظهر على الشاشة"""
    assert len(ledger.visible_entries()) == 2


def test_ledger_report_respects_period_filter(ledger):
    ledger.set_filter("today")
    assert ledger.period_label() == "اليوم"
    assert ledger.visible_entries() == []      # الحركات بتاريخ يناير

    ledger.set_filter("all")
    assert ledger.period_label() == "كل الفترات"
    assert len(ledger.visible_entries()) == 2


def test_ledger_report_html_has_customer_and_totals(ledger):
    html = ledger.build_report_html(PAPER_A4)

    assert "خليل بركات" in html
    assert "بندورة وخيار" in html
    assert "دفعة نقدية" in html
    assert "الرصيد المستحق" in html
    assert "محل أبو درغام للخضار" in html


def test_ledger_report_is_rtl_and_has_no_reversed_text(ledger):
    """
    العربية تخرج طبيعية غير معكوسة — المسار القديم كان يقلبها بـ text[::-1].
    """
    html = ledger.build_report_html(PAPER_A4)

    assert 'dir="rtl"' in html
    assert "خليل بركات" in html
    assert "تاكرب ليلخ" not in html          # الاسم معكوساً


@pytest.mark.parametrize("paper", [PAPER_A4, PAPER_THERMAL_80, PAPER_THERMAL_58])
def test_ledger_pdf_for_every_paper(ledger, tmp_path, paper):
    from ui.printing import export_pdf

    path = tmp_path / f"ledger_{paper}.pdf"
    export_pdf(ledger.build_report_html(paper), str(path), paper=paper)

    assert path.read_bytes()[:5] == b"%PDF-"


def test_export_to_pdf_uses_qt_not_reportlab(ledger, tmp_path):
    """
    export_to_pdf القديم كان reportlab بعربية مقلوبة وعناوين إنجليزية.
    """
    path = tmp_path / "export.pdf"
    ledger.export_to_pdf(str(path))

    assert path.exists()
    raw = path.read_bytes()
    assert raw[:5] == b"%PDF-"
    # ReportLab يضع اسمه في المنتِج؛ Qt لا
    assert b"ReportLab" not in raw


def test_ledger_report_after_sorting_still_complete(ledger):
    """إعادة ترتيب الجدول لا تُسقط حركات من التقرير"""
    from PySide6.QtCore import Qt

    ledger.table.sortItems(4, Qt.AscendingOrder)   # بالمبلغ

    entries = ledger.visible_entries()
    assert len(entries) == 2
    assert {e.desc for e in entries} == {"بندورة وخيار", "دفعة نقدية"}


# ---------- معلومات المحل ----------

def test_shop_info_defaults_when_unset(qt_app, storage):
    from ui.customers_view import CustomersView

    view = CustomersView(storage)
    ctx = view.report_context()

    assert ctx.shop_name == "محل الخضار والفواكه"
    assert ctx.shop_phone == ""


def test_shop_info_read_from_settings(qt_app, storage):
    from ui.customers_view import CustomersView

    storage.update_setting("shop_name", "بسطة الأمانة")
    storage.update_setting("shop_phone", "0591234567")

    ctx = CustomersView(storage).report_context()

    assert ctx.shop_name == "بسطة الأمانة"
    assert ctx.shop_phone == "0591234567"
