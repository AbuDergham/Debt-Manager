"""
اختبارات الترتيب: مفتاح الأبجدية العربية وعناصر الجدول
"""
from datetime import datetime
from decimal import Decimal

import pytest

from core.utils import arabic_sort_key, format_currency, format_datetime_arabic


# ---------- الترتيب الأبجدي العربي ----------

def test_hamza_forms_sort_with_plain_alef():
    """
    بدون تطبيع يعطي ترتيب اليونيكود: آدم | أحمد | إياد | ابراهيم — غلط،
    لأن أشكال الهمزة نقاطها أقل من الألف العادية.
    """
    names = ["آدم", "أحمد", "إياد", "ابراهيم"]
    assert sorted(names, key=arabic_sort_key) == ["ابراهيم", "أحمد", "آدم", "إياد"]


def test_full_alphabet_order():
    names = ["يوسف", "خليل", "بلال", "أحمد", "محمود", "تامر", "هاني", "عمر"]
    assert sorted(names, key=arabic_sort_key) == [
        "أحمد", "بلال", "تامر", "خليل", "عمر", "محمود", "هاني", "يوسف"
    ]


def test_taa_marbuta_folds_to_haa():
    """ة تُعامل كـ ه، فـ «عائشة» تقع في موضعها الصحيح لا بين الباء والتاء"""
    assert sorted(["عمر", "عائشة"], key=arabic_sort_key) == ["عائشة", "عمر"]


def test_waw_hamza_folds_to_waw():
    assert sorted(["مؤمن", "محمود"], key=arabic_sort_key) == ["محمود", "مؤمن"]


def test_alef_maqsura_folds_to_yaa():
    assert arabic_sort_key("ليلى") == arabic_sort_key("ليلي")


def test_diacritics_are_ignored():
    assert arabic_sort_key("مُحَمَّد") == arabic_sort_key("محمد")


def test_tatweel_is_ignored():
    assert arabic_sort_key("خــليل") == arabic_sort_key("خليل")


def test_surrounding_whitespace_ignored():
    assert arabic_sort_key("  خليل  ") == arabic_sort_key("خليل")


def test_arabic_sorts_before_latin():
    """تطبيق عربي — الأسماء العربية أولاً"""
    names = ["Ahmad", "خليل", "Zaid", "أحمد"]
    result = sorted(names, key=arabic_sort_key)
    assert result[:2] == ["أحمد", "خليل"]
    assert set(result[2:]) == {"Ahmad", "Zaid"}


def test_latin_sorts_case_insensitively():
    assert sorted(["banana", "Apple"], key=arabic_sort_key) == ["Apple", "banana"]


def test_empty_string_does_not_crash():
    assert sorted(["خليل", "", "أحمد"], key=arabic_sort_key)[0] == ""


def test_compound_names_sort_by_first_word():
    names = ["خليل بركات", "أحمد محمود", "خليل أحمد"]
    assert sorted(names, key=arabic_sort_key) == ["أحمد محمود", "خليل أحمد", "خليل بركات"]


# ---------- عناصر الجدول (تحتاج QApplication) ----------

@pytest.fixture(scope="module")
def qt_app():
    """تطبيق Qt بلا نافذة — لازم لإنشاء QTableWidgetItem"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_numeric_item_sorts_by_value_not_text(qt_app):
    """
    جوهر المشكلة: «1,234.00 شيكل» يأتي قبل «900.00 شيكل» نصّياً.
    """
    from ui.table_items import NumericItem

    big = NumericItem(format_currency(Decimal("1234.00")), Decimal("1234.00"))
    small = NumericItem(format_currency(Decimal("900.00")), Decimal("900.00"))

    assert big.text() < small.text()      # الترتيب النصّي غلط
    assert small < big                     # ترتيبنا صحيح
    assert not (big < small)


def test_numeric_item_handles_negatives(qt_app):
    from ui.table_items import NumericItem
    negative = NumericItem("-30.00", Decimal("-30.00"))
    zero = NumericItem("0.00", Decimal("0"))
    assert negative < zero


def test_numeric_item_sorted_list(qt_app):
    from ui.table_items import NumericItem
    values = [Decimal("1234.00"), Decimal("900.00"), Decimal("0"), Decimal("-50.00")]
    items = [NumericItem(format_currency(v), v) for v in values]
    assert [i.text() for i in sorted(items)] == [
        format_currency(Decimal("-50.00")),
        format_currency(Decimal("0")),
        format_currency(Decimal("900.00")),
        format_currency(Decimal("1234.00")),
    ]


def test_datetime_item_sorts_chronologically(qt_app):
    """«2026/01/15» و«2025/12/11» — الترتيب النصّي يعكسهما"""
    from ui.table_items import DateTimeItem

    later = datetime(2026, 1, 15, 9, 0)
    earlier = datetime(2025, 12, 11, 16, 0)
    a = DateTimeItem(format_datetime_arabic(later), later)
    b = DateTimeItem(format_datetime_arabic(earlier), earlier)

    assert b < a


def test_datetime_item_distinguishes_same_day_times(qt_app):
    from ui.table_items import DateTimeItem
    morning = datetime(2026, 1, 15, 9, 0)
    evening = datetime(2026, 1, 15, 21, 0)
    assert (DateTimeItem(format_datetime_arabic(morning), morning)
            < DateTimeItem(format_datetime_arabic(evening), evening))


def test_arabic_text_item_uses_alphabet_order(qt_app):
    from ui.table_items import ArabicTextItem
    items = [ArabicTextItem(n) for n in ["آدم", "أحمد", "ابراهيم"]]
    assert [i.text() for i in sorted(items)] == ["ابراهيم", "أحمد", "آدم"]


def test_sorted_table_context_manager(qt_app):
    """
    يعطّل الترتيب أثناء التعبئة ثم يعيده — وإلا بعثر Qt الصفوف.
    """
    from PySide6.QtWidgets import QTableWidget
    from ui.table_items import ArabicTextItem, NumericItem, sorted_table

    table = QTableWidget()
    table.setColumnCount(2)
    rows = [("خليل", Decimal("900")), ("أحمد", Decimal("1234")), ("بلال", Decimal("50"))]

    with sorted_table(table, column=0):
        assert table.isSortingEnabled() is False   # معطّل أثناء التعبئة
        table.setRowCount(len(rows))
        for r, (name, amount) in enumerate(rows):
            table.setItem(r, 0, ArabicTextItem(name))
            table.setItem(r, 1, NumericItem(format_currency(amount), amount))

    assert table.isSortingEnabled() is True
    assert [table.item(r, 0).text() for r in range(3)] == ["أحمد", "بلال", "خليل"]


def test_sorted_table_sorts_numeric_column(qt_app):
    from PySide6.QtWidgets import QTableWidget
    from ui.table_items import ArabicTextItem, NumericItem, sorted_table

    table = QTableWidget()
    table.setColumnCount(2)
    rows = [("خليل", Decimal("900")), ("أحمد", Decimal("1234")), ("بلال", Decimal("50"))]

    with sorted_table(table, column=1):
        table.setRowCount(len(rows))
        for r, (name, amount) in enumerate(rows):
            table.setItem(r, 0, ArabicTextItem(name))
            table.setItem(r, 1, NumericItem(format_currency(amount), amount))

    # مرتَّب رقمياً تصاعدياً: 50 ثم 900 ثم 1234
    assert [table.item(r, 0).text() for r in range(3)] == ["بلال", "خليل", "أحمد"]


def test_sorted_table_restores_sorting_on_exception(qt_app):
    """حتى لو رمت التعبئة استثناءً، يُعاد تفعيل الترتيب"""
    from PySide6.QtWidgets import QTableWidget
    from ui.table_items import sorted_table

    table = QTableWidget()
    with pytest.raises(RuntimeError):
        with sorted_table(table, column=-1):
            raise RuntimeError("فشل أثناء التعبئة")
    assert table.isSortingEnabled() is True


# ---------- تفرّد المعرّفات المؤرَّخة ----------

def test_timestamped_ids_are_unique_within_the_same_second():
    """
    كانت بدقة الثانية فقط: فاتورتان في نفس الثانية = نفس المعرّف.
    """
    from core.utils import generate_check_id, generate_order_id, generate_payment_id

    for generator in (generate_order_id, generate_check_id, generate_payment_id):
        assert len({generator() for _ in range(500)}) == 500


def test_timestamped_ids_keep_readable_prefix():
    from core.utils import generate_order_id
    assert generate_order_id().startswith("PO_")
