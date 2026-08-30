"""
اختبارات لوحة المعلومات
"""
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import make_customer, make_entry, make_supplier


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def dashboard(qt_app, storage):
    from ui.dashboard import DashboardView

    now = datetime.now()
    storage.add_customer(make_customer("c1", "أحمد"))
    storage.add_customer(make_customer("c2", "خليل"))
    storage.add_supplier(make_supplier("s1", "مراد"))

    for days, amount, kind in [(0, "150.00", "purchase"),
                               (0, "80.00", "payment"),
                               (5, "300.00", "purchase"),
                               (40, "220.00", "purchase")]:
        storage.add_entry(make_entry(
            "c1", type=kind, amount=amount,
            date=(now - timedelta(days=days)).isoformat()))

    return DashboardView(storage)


PERIODS = ["today", "month", "year", "all"]


@pytest.mark.parametrize("period", PERIODS)
def test_stat_cards_are_created_for_every_period(dashboard, period):
    """
    كانت حلقة إنشاء البطاقات داخل فرع else، فلا تُنفَّذ إلا للفترة «الكل» —
    والافتراضي «اليوم». النتيجة: صف الإحصاءات فارغ في الاستعمال العادي.
    """
    dashboard.update_stats(period)
    assert dashboard.stats_layout.count() > 0, \
        f"لا بطاقات إحصاء للفترة «{period}»"


@pytest.mark.parametrize("period", PERIODS)
def test_update_stats_does_not_crash(dashboard, period):
    """
    كانت الفترة «الكل» ترمي UnboundLocalError: period_label مُعرَّف في فرع
    if ومُستعمَل في else.
    """
    dashboard.update_stats(period)


@pytest.mark.parametrize("period", PERIODS)
def test_refresh_works_for_every_period(dashboard, period):
    """التحديث الكامل — إحصاءات ورسوم وقوائم — لكل فترة"""
    index = dashboard.period_combo.findData(period)
    dashboard.period_combo.setCurrentIndex(index)
    dashboard.refresh()
    assert dashboard.stats_layout.count() > 0


def test_stat_cards_show_period_in_label(dashboard):
    """عنوان البطاقة يذكر الفترة المعروضة، فلا يلتبس على المستخدم"""
    from PySide6.QtWidgets import QLabel

    dashboard.update_stats("month")
    texts = []
    for i in range(dashboard.stats_layout.count()):
        card = dashboard.stats_layout.itemAt(i).widget()
        if card:
            texts += [w.text() for w in card.findChildren(QLabel)]

    assert any("هذا الشهر" in t for t in texts), texts


def test_stat_cards_are_replaced_not_accumulated(dashboard):
    """تحديثات متتالية لا تكدّس بطاقات"""
    dashboard.update_stats("today")
    first = dashboard.stats_layout.count()

    dashboard.update_stats("month")
    dashboard.update_stats("year")

    assert dashboard.stats_layout.count() == first


def test_dashboard_handles_empty_data(qt_app, storage):
    """تركيب جديد بلا بيانات — لا انهيار ولا صف فارغ"""
    from ui.dashboard import DashboardView

    view = DashboardView(storage)
    for period in PERIODS:
        view.update_stats(period)
        assert view.stats_layout.count() > 0


def test_charts_keep_a_usable_height(dashboard):
    """
    لوحات matplotlib بلا حدّ أدنى للارتفاع تنهار إلى شريط رفيع عندما
    تزدحم اللوحة ببقية البطاقات.
    """
    assert dashboard.sales_chart.canvas.minimumHeight() >= 220
    assert dashboard.payments_chart.canvas.minimumHeight() >= 220
