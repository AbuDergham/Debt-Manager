"""
بناء تقارير HTML للطباعة والتصدير
HTML report builders for printing and PDF export

هذه الوحدة **لا تستورد Qt** — تبني نصاً فقط، فتُختبر وحدها.
العرض والطباعة في ui/printing.py.

لماذا HTML؟ محرّك النص الغني في Qt (QTextDocument) هو نفسه الذي يرسم
الواجهة، فيتعامل مع تشكيل العربية والاتجاه من اليمين لليسار صحيحاً بلا
مكتبات تشكيل. البديل (ReportLab) كان يخرج عربية مقلوبة.

قيود QTextDocument: يدعم جزءاً من CSS 2.1 فقط — لا flexbox ولا grid.
التخطيط بالجداول والخصائص الأساسية.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Dict, Iterable, List, Optional, Sequence

from .models import Customer, Entry, Summary
from .utils import format_currency, format_datetime_arabic

# أنواع الورق المدعومة
PAPER_A4 = "a4"
PAPER_THERMAL_80 = "thermal80"
PAPER_THERMAL_58 = "thermal58"

THERMAL_PAPERS = (PAPER_THERMAL_80, PAPER_THERMAL_58)


@dataclass
class ReportContext:
    """
    ترويسة التقرير: معلومات المحل ووقت الإصدار
    Report header context
    """
    shop_name: str = "محل الخضار والفواكه"
    shop_phone: str = ""
    generated_at: Optional[datetime] = None

    def stamp(self) -> str:
        return format_datetime_arabic(self.generated_at or datetime.now())


# ---------------------------------------------------------------- الأنماط

_A4_CSS = """
body { font-family: 'Segoe UI', Tahoma, Arial; font-size: 11pt; color: #1e293b; }
h1 { font-size: 17pt; margin: 0 0 2pt 0; }
h2 { font-size: 13pt; margin: 0 0 8pt 0; font-weight: normal; color: #475569; }
.meta { font-size: 9pt; color: #64748b; margin-bottom: 10pt; }
table { width: 100%; border-collapse: collapse; margin-top: 6pt; }
th { background-color: #3b82f6; color: #ffffff; font-size: 10pt; }
td { border-bottom: 1px solid #e2e8f0; font-size: 10pt; }
tr.alt td { background-color: #f8fafc; }
/* QTextDocument يتجاهل padding على خلايا الجدول عبر CSS.
   المسافة بين الأعمدة تأتي من خاصية cellpadding على وسم الجدول،
   وإلا التصقت خانة المبلغ بجارتها فصارت «900.00 شيكلنقداً».
   تنبيه: لا تكتب وسماً بين قوسين زاويين داخل هذا التعليق — محلّل
   HTML في Qt يقرأه وسماً حقيقياً فيبتلع بقية المستند. */
.num { text-align: left; }
.debt { color: #dc2626; }
.paid { color: #16a34a; }
.totals { margin-top: 12pt; border-top: 2px solid #3b82f6; }
.totals td { border: none; font-size: 11pt; }
.totals .label { width: 65%; }
.grand td { font-size: 13pt; font-weight: bold; }
.footer { margin-top: 14pt; font-size: 8pt; color: #94a3b8; }
"""

_THERMAL_CSS = """
body { font-family: 'Segoe UI', Tahoma, Arial; font-size: 9pt; color: #000000; }
h1 { font-size: 12pt; margin: 0; text-align: center; }
h2 { font-size: 10pt; margin: 0 0 3pt 0; text-align: center; font-weight: normal; }
.meta { font-size: 7pt; text-align: center; margin-bottom: 4pt; }
.rule { border-top: 1px dashed #000000; margin: 4pt 0; }
table { width: 100%; border-collapse: collapse; }
th { text-align: right; font-size: 8pt; border-bottom: 1px solid #000000; }
td { font-size: 8pt; }
.num { text-align: left; }
.totals td { font-size: 9pt; }
.grand { font-size: 11pt; font-weight: bold; }
.footer { margin-top: 6pt; font-size: 7pt; text-align: center; }
"""


def _css(paper: str) -> str:
    return _THERMAL_CSS if paper in THERMAL_PAPERS else _A4_CSS


def _document(paper: str, title: str, body: str) -> str:
    """يغلّف جسم التقرير بمستند HTML كامل باتجاه من اليمين لليسار"""
    return (
        '<html><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title>"
        f"<style>{_css(paper)}</style></head>"
        f'<body dir="rtl">{body}</body></html>'
    )


def _header(ctx: ReportContext, subtitle: str, paper: str) -> str:
    phone = f" · {escape(ctx.shop_phone)}" if ctx.shop_phone else ""
    parts = [
        f"<h1>{escape(ctx.shop_name)}{phone if paper in THERMAL_PAPERS else ''}</h1>",
        f"<h2>{escape(subtitle)}</h2>",
    ]
    if paper not in THERMAL_PAPERS and ctx.shop_phone:
        parts.insert(1, f'<div class="meta">هاتف: {escape(ctx.shop_phone)}</div>')
    parts.append(f'<div class="meta">تاريخ الطباعة: {escape(ctx.stamp())}</div>')
    if paper in THERMAL_PAPERS:
        parts.append('<div class="rule"></div>')
    return "".join(parts)


def _footer(paper: str) -> str:
    if paper in THERMAL_PAPERS:
        return '<div class="rule"></div><div class="footer">شكراً لتعاملكم معنا</div>'
    return '<div class="footer">أُنتج بواسطة برنامج إدارة ديون العملاء</div>'


def _amount_cell(value: Decimal, css_class: str = "") -> str:
    classes = f"num {css_class}".strip()
    return f'<td class="{classes}">{escape(format_currency(value))}</td>'


# ------------------------------------------------- تقرير كل العملاء

def build_customers_report(
    customers: Sequence[Customer],
    summaries: Dict[str, Summary],
    ctx: Optional[ReportContext] = None,
    paper: str = PAPER_A4,
) -> str:
    """
    تقرير بكل العملاء وأرصدتهم
    Report of all customers with their balances

    Args:
        customers: العملاء بالترتيب المطلوب طباعته (ترتيب الشاشة عادةً)
        summaries: ملخصات العملاء {customer_id: Summary}
        ctx: معلومات المحل ووقت الإصدار
        paper: a4 أو thermal80 أو thermal58
    """
    ctx = ctx or ReportContext()
    thermal = paper in THERMAL_PAPERS

    total_debt = Decimal("0.00")
    total_credit = Decimal("0.00")
    rows: List[str] = []

    for index, customer in enumerate(customers, 1):
        summary = summaries.get(customer.id) or Summary.empty()
        balance = summary.balance_decimal

        if balance > 0:
            total_debt += balance
            balance_class = "debt"
        elif balance < 0:
            total_credit += -balance
            balance_class = "paid"
        else:
            balance_class = ""

        alt = ' class="alt"' if index % 2 == 0 and not thermal else ""

        if thermal:
            rows.append(
                f"<tr><td>{escape(customer.name)}</td>"
                f"{_amount_cell(balance, balance_class)}</tr>"
            )
        else:
            rows.append(
                f"<tr{alt}><td>{index}</td>"
                f"<td>{escape(customer.name)}</td>"
                f"<td>{escape(customer.phone or '-')}</td>"
                f"{_amount_cell(balance, balance_class)}"
                f"{_amount_cell(summary.today_sales_decimal)}"
                f"{_amount_cell(summary.month_sales_decimal)}</tr>"
            )

    if thermal:
        head = "<tr><th>العميل</th><th class='num'>الرصيد</th></tr>"
    else:
        head = ("<tr><th>#</th><th>اسم العميل</th><th>الهاتف</th>"
                "<th>الرصيد الحالي</th><th>مبيعات اليوم</th>"
                "<th>مبيعات الشهر</th></tr>")

    body = [
        _header(ctx, "كشف أرصدة العملاء", paper),
        f'<table cellpadding="7" cellspacing="0">' f"{head}{''.join(rows) or _empty_row(6 if not thermal else 2)}</table>",
        '<table class="totals" cellpadding="7" cellspacing="0">',
        f"<tr><td class='label'>عدد العملاء</td>"
        f"<td class='num'>{len(customers)}</td></tr>",
        f"<tr><td class='label'>إجمالي المستحق لنا</td>"
        f"{_amount_cell(total_debt, 'debt')}</tr>",
    ]
    if total_credit > 0:
        body.append(f"<tr><td class='label'>إجمالي المدفوع مقدماً</td>"
                    f"{_amount_cell(total_credit, 'paid')}</tr>")
    body.append(f"<tr class='grand'><td class='label'>الصافي</td>"
                f"{_amount_cell(total_debt - total_credit)}</tr>")
    body.append("</table>")
    body.append(_footer(paper))

    return _document(paper, "كشف أرصدة العملاء", "".join(body))


# ------------------------------------------------- كشف حساب عميل

def build_ledger_report(
    customer: Customer,
    entries: Sequence[Entry],
    summary: Summary,
    ctx: Optional[ReportContext] = None,
    paper: str = PAPER_A4,
    period_label: str = "كل الفترات",
) -> str:
    """
    كشف حساب عميل واحد
    Statement of account for a single customer

    Args:
        customer: العميل
        entries: حركاته بالترتيب المطلوب طباعته
        summary: ملخّص حسابه
        ctx: معلومات المحل ووقت الإصدار
        paper: a4 أو thermal80 أو thermal58
        period_label: وصف الفترة المعروضة (الكل / اليوم / هذا الشهر)
    """
    ctx = ctx or ReportContext()
    thermal = paper in THERMAL_PAPERS

    # الرصيد التراكمي يُحسب بترتيب زمني تصاعدي مهما كان ترتيب العرض
    chronological = sorted(entries, key=lambda e: e.datetime)
    running: Dict[str, Decimal] = {}
    balance = Decimal("0.00")
    for entry in chronological:
        balance += entry.signed_amount
        running[entry.id] = balance

    total_debt = sum((e.amount_decimal for e in entries if e.type == "purchase"),
                     Decimal("0.00"))
    total_paid = sum((e.amount_decimal for e in entries if e.type == "payment"),
                     Decimal("0.00"))

    rows: List[str] = []
    for index, entry in enumerate(entries, 1):
        is_debt = entry.type == "purchase"
        type_text = "دين" if is_debt else "دفع"
        css = "debt" if is_debt else "paid"
        alt = ' class="alt"' if index % 2 == 0 and not thermal else ""

        if thermal:
            rows.append(
                f"<tr><td>{escape(entry.datetime.strftime('%m/%d'))}</td>"
                f"<td>{escape(type_text)}</td>"
                f"<td>{escape(entry.desc)}</td>"
                f"{_amount_cell(entry.amount_decimal, css)}</tr>"
            )
        else:
            pay_text = "نقداً" if entry.pay_method == "cash" else "تحويل"
            rows.append(
                f"<tr{alt}><td>{escape(format_datetime_arabic(entry.datetime))}</td>"
                f"<td class='{css}'>{escape(type_text)}</td>"
                f"<td>{escape(entry.desc)}</td>"
                f"<td>{escape(pay_text)}</td>"
                f"{_amount_cell(entry.amount_decimal, css)}"
                f"{_amount_cell(running.get(entry.id, Decimal('0.00')))}</tr>"
            )

    if thermal:
        head = ("<tr><th>التاريخ</th><th>النوع</th><th>الوصف</th>"
                "<th class='num'>المبلغ</th></tr>")
    else:
        head = ("<tr><th>التاريخ والوقت</th><th>النوع</th><th>الوصف</th>"
                "<th>طريقة الدفع</th><th>المبلغ</th>"
                "<th>الرصيد بعد العملية</th></tr>")

    info = [f"<div class='meta'>العميل: {escape(customer.name)}"]
    if customer.phone:
        info.append(f" · هاتف: {escape(customer.phone)}")
    if customer.credit_limit_decimal > 0:
        info.append(f" · حد الائتمان: "
                    f"{escape(format_currency(customer.credit_limit_decimal))}")
    info.append(f" · الفترة: {escape(period_label)}</div>")

    body = [
        _header(ctx, f"كشف حساب: {customer.name}", paper),
        "".join(info),
        f'<table cellpadding="7" cellspacing="0">' f"{head}{''.join(rows) or _empty_row(6 if not thermal else 4)}</table>",
        '<table class="totals" cellpadding="7" cellspacing="0">',
        f"<tr><td class='label'>إجمالي الديون</td>"
        f"{_amount_cell(total_debt, 'debt')}</tr>",
        f"<tr><td class='label'>إجمالي المدفوعات</td>"
        f"{_amount_cell(total_paid, 'paid')}</tr>",
        f"<tr class='grand'><td class='label'>الرصيد المستحق</td>"
        f"{_amount_cell(summary.balance_decimal)}</tr>",
        "</table>",
        _footer(paper),
    ]

    return _document(paper, f"كشف حساب {customer.name}", "".join(body))


def _empty_row(columns: int) -> str:
    return (f'<tr><td colspan="{columns}" style="text-align:center; color:#94a3b8">'
            "لا توجد بيانات</td></tr>")
