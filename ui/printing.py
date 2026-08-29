"""
الطباعة وتصدير PDF عبر محرّك Qt
Printing and PDF export through Qt

لماذا Qt لا ReportLab؟ QTextDocument هو نفسه محرّك النص الذي يرسم الواجهة،
فيتعامل مع تشكيل العربية والاتجاه من اليمين لليسار صحيحاً بلا مكتبات
تشكيل. المسار القديم كان يقع على `text[::-1]` فتخرج العربية مقلوبة.
"""
import re
from typing import Callable, Optional, Tuple

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import (
    QPrintPreviewDialog,
    QPrinter,
    QPrinterInfo,
)

from core.reports import PAPER_A4, PAPER_THERMAL_58, PAPER_THERMAL_80

# ------------------------------------------------- كشف نوع الطابعة

# لا طابعة حرارية أعرض من 80 مم؛ 90 هامش أمان
THERMAL_MAX_MM = 90.0
THERMAL_58_MAX_MM = 62.0

# احتياطي أخير حين لا يبلّغ المُعرِّف أي مقاسات
_THERMAL_NAME_HINTS = re.compile(
    r"\b(pos|tm-t|tm-u|xp-\d|rp-?\d|thermal|receipt|58\s?mm|80\s?mm)\b",
    re.IGNORECASE,
)

PAPER_LABELS = {
    PAPER_A4: "A4",
    PAPER_THERMAL_80: "حراري ٨٠ مم",
    PAPER_THERMAL_58: "حراري ٥٨ مم",
}


def _widest_supported_mm(info: QPrinterInfo) -> Optional[float]:
    """
    أقصى عرض ورق يصرّح المُعرِّف بدعمه فعلاً

    أوثق من maximumPhysicalPageSize(): الطابعات الوهمية تبلّغ أرقاماً
    خيالية (XPS ‏863 مم، Print-to-PDF ‏917 مم)، وطابعات A4 تبلّغ ارتفاعات
    بانر تصل 1200 مم.

    كل استعلام مغلَّف: مُعرِّفات ويندوز قد ترمي أخطاء COM عند سؤالها عن
    مقاساتها (شوهد 0x80040155 على طابعة شبكية فعلية). طابعة واحدة معطوبة
    يجب ألا تمنع الطباعة على البقية.
    """
    try:
        widths = [
            size.size(QPageSize.Unit.Millimeter).width()
            for size in info.supportedPageSizes()
        ]
        widths = [w for w in widths if w and w > 0]
        if widths:
            return max(widths)
    except Exception:
        pass

    try:
        width = info.maximumPhysicalPageSize().size(QPageSize.Unit.Millimeter).width()
        return width if width and width > 0 else None
    except Exception:
        return None


def detect_paper_class(info: QPrinterInfo) -> Tuple[str, str]:
    """
    تحديد نوع ورق الطابعة تلقائياً
    Detect a printer's paper class automatically

    Returns:
        (نوع الورق، سبب القرار) — السبب للعرض في الواجهة
    """
    width = _widest_supported_mm(info)

    if width:
        if width <= THERMAL_58_MAX_MM:
            return PAPER_THERMAL_58, f"أقصى عرض مدعوم {width:.0f} مم"
        if width <= THERMAL_MAX_MM:
            return PAPER_THERMAL_80, f"أقصى عرض مدعوم {width:.0f} مم"
        return PAPER_A4, f"أقصى عرض مدعوم {width:.0f} مم"

    try:
        haystack = f"{info.printerName()} {info.makeAndModel()}"
    except Exception:
        haystack = ""

    if _THERMAL_NAME_HINTS.search(haystack):
        return PAPER_THERMAL_80, "لا بيانات مقاسات — تطابق اسم طابعة حرارية"

    return PAPER_A4, "لا بيانات مقاسات — افتراضي"


def detect_for_printer(printer: QPrinter) -> Tuple[str, str]:
    """كشف نوع الورق لطابعة قيد الاستخدام (أو مخرَج PDF)"""
    if printer.outputFormat() == QPrinter.PdfFormat:
        return PAPER_A4, "إخراج PDF"

    info = QPrinterInfo(printer)
    if info.isNull():
        return PAPER_A4, "طابعة غير معروفة — افتراضي"
    return detect_paper_class(info)


# ------------------------------------------------- تخطيط الصفحة

def _page_size(paper: str, height_mm: float = 297.0) -> QPageSize:
    if paper == PAPER_THERMAL_80:
        return QPageSize(QSizeF(80.0, height_mm), QPageSize.Unit.Millimeter,
                         "Thermal80", QPageSize.ExactMatch)
    if paper == PAPER_THERMAL_58:
        return QPageSize(QSizeF(58.0, height_mm), QPageSize.Unit.Millimeter,
                         "Thermal58", QPageSize.ExactMatch)
    return QPageSize(QPageSize.A4)


def _apply_layout(printer: QPrinter, paper: str, height_mm: float = 297.0) -> None:
    """يضبط حجم الصفحة والهوامش حسب نوع الورق"""
    layout = QPageLayout()
    layout.setPageSize(_page_size(paper, height_mm))
    layout.setOrientation(QPageLayout.Portrait)
    layout.setUnits(QPageLayout.Millimeter)

    if paper in (PAPER_THERMAL_80, PAPER_THERMAL_58):
        layout.setMargins(QMarginsF(3, 3, 3, 3))     # قصاصة ضيقة
    else:
        layout.setMargins(QMarginsF(15, 12, 15, 12))

    printer.setPageLayout(layout)


def render_html(printer: QPrinter, html: str, paper: str) -> None:
    """
    يرسم HTML على طابعة (أو ملف PDF)

    للورق الحراري يقيس ارتفاع المستند أولاً ثم يضبط ارتفاع الصفحة عليه،
    فلا تخرج قصاصة بذيل فارغ طويل.
    """
    _apply_layout(printer, paper)

    document = QTextDocument()
    document.setHtml(html)
    document.setPageSize(QSizeF(printer.pageRect(QPrinter.Point).size()))

    if paper in (PAPER_THERMAL_80, PAPER_THERMAL_58):
        # نقطة = 1/72 بوصة، والبوصة 25.4 مم
        content_mm = document.size().height() * 25.4 / 72.0
        _apply_layout(printer, paper, max(60.0, content_mm + 12.0))
        document.setPageSize(QSizeF(printer.pageRect(QPrinter.Point).size()))

    document.print_(printer)


# ------------------------------------------------- الواجهات العامة

def show_print_preview(
    html_builder: Callable[[str], str],
    parent=None,
    title: str = "معاينة الطباعة",
    forced_paper: Optional[str] = None,
) -> None:
    """
    يعرض معاينة قبل الطباعة، ويعيد بناء التقرير مع كل تبديل طابعة
    Show a print preview that re-renders when the printer changes

    `paintRequested` تنطلق مع كل تغيير في الطابعة أو الإعدادات، فيُعاد
    الكشف ويُبنى القالب المطابق — التقرير يتحوّل من جدول A4 إلى قصاصة
    إيصال أمام المستخدم.

    Args:
        html_builder: دالة تأخذ نوع الورق وترجع HTML
        forced_paper: تجاوز يدوي للكشف (لمُعرِّفات الطابعات التي تبلّغ خطأ)
    """
    printer = QPrinter(QPrinter.HighResolution)

    def on_paint_requested(target: QPrinter) -> None:
        paper = forced_paper or detect_for_printer(target)[0]
        render_html(target, html_builder(paper), paper)

    dialog = QPrintPreviewDialog(printer, parent)
    dialog.setWindowTitle(title)
    dialog.paintRequested.connect(on_paint_requested)
    dialog.resize(1000, 760)
    dialog.exec()


def export_pdf(html: str, path: str, paper: str = PAPER_A4) -> None:
    """
    حفظ التقرير ملفَّ PDF بلا مرور على طابعة
    Save the report straight to a PDF file

    العربية تخرج متصلة وباتجاه صحيح لأن الإخراج يمرّ على نفس
    QTextDocument الذي يرسم الواجهة.
    """
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    render_html(printer, html, paper)


def available_printers() -> list:
    """
    الطابعات المتاحة مع نوع الورق المكتشف لكل منها
    Available printers with their detected paper class

    Returns:
        [(الاسم، نوع الورق، سبب القرار، أهي الافتراضية)]
    """
    rows = []
    for info in QPrinterInfo.availablePrinters():
        try:
            paper, reason = detect_paper_class(info)
            rows.append((info.printerName(), paper, reason, info.isDefault()))
        except Exception as e:
            # مُعرِّف معطوب: أدرج الطابعة بافتراض A4 بدل إسقاطها من القائمة
            rows.append((info.printerName(), PAPER_A4,
                         f"تعذّرت قراءة المقاسات ({e})", False))
    return rows
