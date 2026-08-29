"""
اختبارات بناء تقارير HTML — بلا Qt
"""
import re
from datetime import datetime
from decimal import Decimal

import pytest

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

CTX = ReportContext(shop_name="محل الخضار والفواكه", shop_phone="0569337729",
                    generated_at=datetime(2026, 8, 29, 17, 30))


def summary(balance="0.00", today="0.00", month="0.00") -> Summary:
    return Summary(balance=balance, today_sales=today, month_sales=month,
                   last_update=datetime(2026, 8, 29).isoformat())


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


# ---------- تقرير كل العملاء ----------

def test_customers_report_is_rtl():
    html = build_customers_report([], {}, CTX)
    assert 'dir="rtl"' in html


def test_customers_report_shows_shop_info():
    html = build_customers_report([], {}, CTX)
    assert "محل الخضار والفواكه" in html
    assert "0569337729" in html


def test_customers_report_shows_generation_time():
    html = build_customers_report([], {}, CTX)
    assert "2026/08/29" in html


def test_customers_report_lists_every_customer():
    """المطلوب: كل الزبائن، حتى أصحاب الرصيد صفر"""
    customers = [make_customer("c1", "خليل"), make_customer("c2", "أحمد"),
                 make_customer("c3", "آدم")]
    summaries = {"c1": summary("900.00"), "c2": summary("0.00")}

    text = strip_tags(build_customers_report(customers, summaries, CTX))

    assert "خليل" in text and "أحمد" in text and "آدم" in text


def test_customers_report_preserves_given_order():
    """يطبع بترتيب الشاشة، لا بترتيبه الخاص"""
    customers = [make_customer("c1", "خليل"), make_customer("c2", "أحمد")]
    text = strip_tags(build_customers_report(customers, {}, CTX))
    assert text.index("خليل") < text.index("أحمد")


def test_customers_report_totals_only_positive_balances():
    """الأرصدة السالبة (دفع مقدماً) لا تُحتسب ضمن المستحق لنا"""
    customers = [make_customer("c1", "خليل"), make_customer("c2", "أحمد")]
    summaries = {"c1": summary("900.00"), "c2": summary("-100.00")}

    text = strip_tags(build_customers_report(customers, summaries, CTX))

    assert "900.00" in text          # إجمالي المستحق
    assert "100.00" in text          # المدفوع مقدماً
    assert "800.00" in text          # الصافي


def test_customers_report_counts_customers():
    customers = [make_customer(f"c{i}", f"عميل{i}") for i in range(7)]
    text = strip_tags(build_customers_report(customers, {}, CTX))
    assert "عدد العملاء" in text
    assert "7" in text


def test_customers_report_handles_empty_list():
    text = strip_tags(build_customers_report([], {}, CTX))
    assert "لا توجد بيانات" in text


def test_customers_report_escapes_html_in_names():
    """اسم فيه رموز HTML لا يكسر المستند"""
    customers = [make_customer("c1", "<b>خليل</b> & شركاه")]
    html = build_customers_report(customers, {}, CTX)
    assert "&lt;b&gt;" in html
    assert "&amp;" in html


def test_customers_report_thermal_is_narrower():
    """النسخة الحرارية عمودان لا ستة"""
    customers = [make_customer("c1", "خليل")]
    summaries = {"c1": summary("900.00")}

    a4 = build_customers_report(customers, summaries, CTX, paper=PAPER_A4)
    thermal = build_customers_report(customers, summaries, CTX,
                                     paper=PAPER_THERMAL_80)

    assert "مبيعات اليوم" in a4
    assert "مبيعات اليوم" not in thermal
    assert "خليل" in thermal and "900.00" in thermal


# ---------- كشف حساب العميل ----------

@pytest.fixture
def ledger_data():
    customer = make_customer("c1", "خليل بركات", phone="0599123456",
                             credit_limit="1000.00")
    entries = [
        make_entry("c1", amount="100.00", desc="بندورة",
                   date=datetime(2026, 1, 3, 9, 0).isoformat()),
        make_entry("c1", amount="250.00", desc="خيار",
                   date=datetime(2026, 1, 10, 11, 0).isoformat()),
        make_entry("c1", type="payment", amount="150.00", desc="دفعة",
                   date=datetime(2026, 1, 15, 16, 0).isoformat()),
    ]
    return customer, entries, summary("200.00")


def test_ledger_report_shows_customer_details(ledger_data):
    customer, entries, s = ledger_data
    text = strip_tags(build_ledger_report(customer, entries, s, CTX))
    assert "خليل بركات" in text
    assert "0599123456" in text
    assert "1,000.00" in text          # حد الائتمان


def test_ledger_report_lists_all_entries(ledger_data):
    customer, entries, s = ledger_data
    text = strip_tags(build_ledger_report(customer, entries, s, CTX))
    assert "بندورة" in text and "خيار" in text and "دفعة" in text


def test_ledger_report_running_balance_is_chronological(ledger_data):
    """
    الرصيد التراكمي يُحسب زمنياً حتى لو عُرضت الحركات بترتيب معكوس.
    100 ثم 350 ثم 200.
    """
    customer, entries, s = ledger_data
    reversed_entries = list(reversed(entries))

    text = strip_tags(build_ledger_report(customer, reversed_entries, s, CTX))

    assert "100.00" in text and "350.00" in text and "200.00" in text


def test_ledger_report_totals(ledger_data):
    customer, entries, s = ledger_data
    text = strip_tags(build_ledger_report(customer, entries, s, CTX))
    assert "إجمالي الديون" in text
    assert "350.00" in text            # 100 + 250
    assert "إجمالي المدفوعات" in text
    assert "150.00" in text
    assert "الرصيد المستحق" in text


def test_ledger_report_shows_period_label(ledger_data):
    customer, entries, s = ledger_data
    text = strip_tags(build_ledger_report(customer, entries, s, CTX,
                                          period_label="هذا الشهر"))
    assert "هذا الشهر" in text


def test_ledger_report_marks_debt_and_payment(ledger_data):
    customer, entries, s = ledger_data
    text = strip_tags(build_ledger_report(customer, entries, s, CTX))
    assert "دين" in text and "دفع" in text


def test_ledger_report_handles_no_entries():
    customer = make_customer("c1", "خليل")
    text = strip_tags(build_ledger_report(customer, [], summary(), CTX))
    assert "لا توجد بيانات" in text


def test_ledger_report_thermal_omits_wide_columns(ledger_data):
    customer, entries, s = ledger_data
    thermal = build_ledger_report(customer, entries, s, CTX,
                                  paper=PAPER_THERMAL_58)
    assert "الرصيد بعد العملية" not in thermal
    assert "طريقة الدفع" not in thermal
    assert "بندورة" in thermal


def test_ledger_report_escapes_description(ledger_data):
    customer, entries, s = ledger_data
    entries[0].desc = "<script>bad</script>"
    html = build_ledger_report(customer, entries, s, CTX)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# ---------- مشترك ----------

@pytest.mark.parametrize("paper", [PAPER_A4, PAPER_THERMAL_80, PAPER_THERMAL_58])
def test_every_paper_size_produces_valid_document(paper):
    customers = [make_customer("c1", "خليل")]
    html = build_customers_report(customers, {"c1": summary("50.00")}, CTX, paper)
    assert html.startswith("<html>")
    assert html.rstrip().endswith("</html>")
    assert "<style>" in html


def test_default_context_uses_now():
    """بلا سياق: اسم افتراضي ووقت الآن"""
    html = build_customers_report([], {})
    assert "محل الخضار والفواكه" in html


def test_currency_is_shekel():
    customers = [make_customer("c1", "خليل")]
    html = build_customers_report(customers, {"c1": summary("50.00")}, CTX)
    assert "شيكل" in html
    assert "ج.م" not in html
