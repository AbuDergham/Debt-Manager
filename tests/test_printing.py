"""
اختبارات محرك الطباعة: الكشف التلقائي لنوع الطابعة، وإخراج PDF
"""
import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import make_customer, make_entry
from core.models import Summary
from core.reports import (
    PAPER_A4,
    PAPER_THERMAL_58,
    PAPER_THERMAL_80,
    ReportContext,
    build_customers_report,
    build_ledger_report,
)


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


class FakePageSize:
    """يحاكي QPageSize بعرض ثابت"""
    def __init__(self, width_mm):
        self._w = width_mm

    def size(self, _unit):
        from PySide6.QtCore import QSizeF
        return QSizeF(self._w, 297.0)


class FakePrinterInfo:
    """يحاكي QPrinterInfo — نختبر منطق الكشف بلا طابعات حقيقية"""
    def __init__(self, name, widths, model="", max_physical=None):
        self._name = name
        self._widths = widths
        self._model = model
        self._max = max_physical

    def printerName(self):
        return self._name

    def makeAndModel(self):
        return self._model

    def supportedPageSizes(self):
        return [FakePageSize(w) for w in self._widths]

    def maximumPhysicalPageSize(self):
        if self._max is None:
            raise RuntimeError("لا مقاسات")
        return FakePageSize(self._max)


# ---------- كشف نوع الطابعة ----------

def test_detects_a4_printer(qt_app):
    """إبسون L3250 الحقيقية تبلّغ عروضاً حتى 420 مم"""
    from ui.printing import detect_paper_class

    paper, reason = detect_paper_class(
        FakePrinterInfo("EPSON L3250 Series", [88.9, 210.0, 420.0]))

    assert paper == PAPER_A4
    assert "420" in reason


def test_detects_virtual_printers_as_a4(qt_app):
    """
    الطابعات الوهمية تبلّغ أرقاماً خيالية — يجب ألا تُصنَّف حرارية.
    """
    from ui.printing import detect_paper_class

    for name, widths in [
        ("Microsoft XPS Document Writer", [90.0, 215.9, 914.4]),
        ("Microsoft Print to PDF", [50.8, 215.9, 917.0]),
        ("Fax", [50.8, 216.0]),
        ("AnyDesk Printer", [98.4, 210.0, 297.0]),
    ]:
        assert detect_paper_class(FakePrinterInfo(name, widths))[0] == PAPER_A4


def test_detects_80mm_thermal(qt_app):
    from ui.printing import detect_paper_class
    assert detect_paper_class(FakePrinterInfo("XP-80C", [80.0]))[0] == PAPER_THERMAL_80


def test_detects_58mm_thermal(qt_app):
    from ui.printing import detect_paper_class
    assert detect_paper_class(FakePrinterInfo("POS-58", [58.0]))[0] == PAPER_THERMAL_58


def test_detects_72mm_printable_as_80mm_class(qt_app):
    """بعض طابعات 80 مم تبلّغ عرض الطباعة (72 مم) لا عرض الورق"""
    from ui.printing import detect_paper_class
    assert detect_paper_class(FakePrinterInfo("RP80", [72.0]))[0] == PAPER_THERMAL_80


def test_falls_back_to_physical_size_when_no_page_list(qt_app):
    from ui.printing import detect_paper_class
    info = FakePrinterInfo("Generic", [], max_physical=80.0)
    paper, reason = detect_paper_class(info)
    assert paper == PAPER_THERMAL_80


def test_falls_back_to_name_when_no_sizes_at_all(qt_app):
    from ui.printing import detect_paper_class
    paper, reason = detect_paper_class(
        FakePrinterInfo("Generic POS Printer", [], model="thermal receipt"))
    assert paper == PAPER_THERMAL_80
    assert "اسم" in reason


def test_defaults_to_a4_when_nothing_is_known(qt_app):
    from ui.printing import detect_paper_class
    paper, reason = detect_paper_class(FakePrinterInfo("Unknown Device", []))
    assert paper == PAPER_A4
    assert "افتراضي" in reason


def test_name_hints_do_not_override_real_measurements(qt_app):
    """
    اسم فيه «POS» لكن مقاساته A4 -> يبقى A4. المقاسات أوثق من الاسم.
    """
    from ui.printing import detect_paper_class
    info = FakePrinterInfo("POS Terminal Laser", [210.0, 297.0])
    assert detect_paper_class(info)[0] == PAPER_A4


def test_broken_driver_does_not_break_detection(qt_app):
    """
    مُعرِّفات ويندوز قد ترمي أخطاء COM عند سؤالها عن مقاساتها
    (شوهد 0x80040155 على طابعة شبكية فعلية). لا يجوز أن يمنع ذلك الطباعة.
    """
    from ui.printing import detect_paper_class

    class BrokenInfo(FakePrinterInfo):
        def supportedPageSizes(self):
            raise RuntimeError("0x80040155")

        def maximumPhysicalPageSize(self):
            raise RuntimeError("0x80040155")

    paper, reason = detect_paper_class(BrokenInfo("Broken Network Printer", []))

    assert paper == PAPER_A4
    assert reason


def test_broken_driver_still_listed(qt_app, monkeypatch):
    """طابعة معطوبة تبقى في القائمة بافتراض A4، لا تُسقَط منها"""
    from ui import printing

    class Exploding:
        def printerName(self):
            return "طابعة معطوبة"

        def isDefault(self):
            return False

    monkeypatch.setattr(printing.QPrinterInfo, "availablePrinters",
                        staticmethod(lambda: [Exploding()]))
    monkeypatch.setattr(printing, "detect_paper_class",
                        lambda info: (_ for _ in ()).throw(RuntimeError("boom")))

    rows = printing.available_printers()

    assert len(rows) == 1
    assert rows[0][0] == "طابعة معطوبة"
    assert rows[0][1] == PAPER_A4


def test_pdf_output_is_always_a4(qt_app):
    from PySide6.QtPrintSupport import QPrinter
    from ui.printing import detect_for_printer

    printer = QPrinter()
    printer.setOutputFormat(QPrinter.PdfFormat)

    paper, reason = detect_for_printer(printer)
    assert paper == PAPER_A4
    assert "PDF" in reason


def test_real_installed_printers_all_classify(qt_app):
    """كل طابعة مركّبة فعلاً على هذا الجهاز تُصنَّف بلا انهيار"""
    from core.reports import THERMAL_PAPERS
    from ui.printing import available_printers

    for name, paper, reason, is_default in available_printers():
        assert paper in (PAPER_A4,) + THERMAL_PAPERS
        assert reason


# ---------- إخراج PDF ----------

@pytest.fixture
def report_html():
    customer = make_customer("c1", "خليل بركات", phone="0599123456")
    entries = [
        make_entry("c1", amount="100.00", desc="بندورة",
                   date=datetime(2026, 1, 3, 9, 0).isoformat()),
        make_entry("c1", type="payment", amount="40.00", desc="دفعة",
                   date=datetime(2026, 1, 5, 9, 0).isoformat()),
    ]
    s = Summary(balance="60.00", today_sales="0.00", month_sales="0.00",
                last_update=datetime(2026, 1, 5).isoformat())
    ctx = ReportContext(shop_name="محل الخضار", shop_phone="0569337729",
                        generated_at=datetime(2026, 8, 29, 17, 0))
    return build_ledger_report(customer, entries, s, ctx)


def test_export_pdf_creates_readable_file(qt_app, report_html, tmp_path):
    from ui.printing import export_pdf

    path = tmp_path / "ledger.pdf"
    export_pdf(report_html, str(path))

    assert path.exists()
    assert path.stat().st_size > 1000
    assert path.read_bytes()[:5] == b"%PDF-"


@pytest.mark.parametrize("paper", [PAPER_A4, PAPER_THERMAL_80, PAPER_THERMAL_58])
def test_export_pdf_for_every_paper_size(qt_app, report_html, tmp_path, paper):
    from ui.printing import export_pdf

    path = tmp_path / f"{paper}.pdf"
    export_pdf(report_html, str(path), paper=paper)

    assert path.exists() and path.read_bytes()[:5] == b"%PDF-"


def test_thermal_pdf_is_narrower_than_a4(qt_app, report_html, tmp_path):
    """القصاصة الحرارية أضيق فعلياً — نتحقق من MediaBox في الـ PDF"""
    import re

    from ui.printing import export_pdf

    widths = {}
    for paper in (PAPER_A4, PAPER_THERMAL_80, PAPER_THERMAL_58):
        path = tmp_path / f"{paper}.pdf"
        export_pdf(report_html, str(path), paper=paper)
        raw = path.read_bytes().decode("latin-1")
        match = re.search(r"/MediaBox\s*\[\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)", raw)
        assert match, f"لم أجد MediaBox في {paper}"
        widths[paper] = float(match.group(1))

    assert widths[PAPER_THERMAL_58] < widths[PAPER_THERMAL_80] < widths[PAPER_A4]


def test_export_pdf_of_customers_report(qt_app, tmp_path):
    from ui.printing import export_pdf

    customers = [make_customer(f"c{i}", name)
                 for i, name in enumerate(["خليل", "أحمد", "آدم"])]
    html = build_customers_report(customers, {}, ReportContext())

    path = tmp_path / "customers.pdf"
    export_pdf(html, str(path))

    assert path.read_bytes()[:5] == b"%PDF-"


def test_render_html_does_not_crash_on_empty_report(qt_app, tmp_path):
    from ui.printing import export_pdf

    html = build_customers_report([], {}, ReportContext())
    path = tmp_path / "empty.pdf"
    export_pdf(html, str(path))

    assert path.exists()
