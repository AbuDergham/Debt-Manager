"""
عناصر جدول قابلة للترتيب الصحيح
Table items that sort correctly

المشكلة: `QTableWidgetItem` الافتراضي يقارن نص `Qt.DisplayRole`. يعني
«1,234.00 شيكل» يأتي **قبل** «900.00 شيكل» لأن '1' < '9' نصّياً. ونفس
المشكلة مع التواريخ المنسّقة والأسماء العربية.

الحل: عناصر تعرض نصاً منسّقاً للمستخدم، وتقارن بمفتاح مناسب للنوع.

مصيدة Qt المهمة
---------------
عند `setSortingEnabled(True)` وتعبئة الجدول بـ `setItem()` في حلقة، يعيد
Qt الترتيب بعد **كل** إدخال فتتبعثر الصفوف. استخدم `sorted_table(table)`
كمدير سياق ليتكفّل بالتعطيل والإعادة.
"""
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Union

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from core.utils import arabic_sort_key


class SortKeyItem(QTableWidgetItem):
    """
    عنصر جدول يعرض نصاً ويرتَّب بمفتاح مستقل عنه
    Table item displaying one thing and sorting by another
    """

    def __init__(self, text: str, sort_key):
        super().__init__(text)
        self._sort_key = sort_key

    def __lt__(self, other):
        if isinstance(other, SortKeyItem):
            try:
                return self._sort_key < other._sort_key
            except TypeError:
                # مفتاحان من نوعين مختلفين — ارجع للمقارنة النصية
                return super().__lt__(other)
        return super().__lt__(other)


class NumericItem(SortKeyItem):
    """
    مبلغ أو رقم: يعرض النص المنسّق ويرتَّب رقمياً
    Numeric cell: formatted display, numeric ordering
    """

    def __init__(self, text: str, value: Union[Decimal, float, int]):
        super().__init__(text, float(value))


class DateTimeItem(SortKeyItem):
    """
    تاريخ: يعرض الصيغة العربية ويرتَّب زمنياً
    Date cell: Arabic display, chronological ordering
    """

    def __init__(self, text: str, moment: datetime):
        super().__init__(text, moment.timestamp())


class ArabicTextItem(SortKeyItem):
    """
    اسم عربي: يرتَّب بالترتيب الأبجدي الصحيح بعد تطبيع الهمزات
    Arabic name cell: correct alphabetical ordering
    """

    def __init__(self, text: str):
        super().__init__(text, arabic_sort_key(text))


class HeaderSortController:
    """
    ترتيب على مستوى البيانات لا على مستوى عناصر الجدول
    Data-level sorting, driven by header clicks

    لماذا لا نستخدم ترتيب Qt المدمج هنا؟ الجداول التي تحوي أزراراً داخل
    الخلايا (`setCellWidget`) تنكسر معه: Qt يحرّك العناصر ولا يحرّك
    الودجات، فيصبح الزر في صف ما تابعاً لسجل آخر — والضغط عليه ينفّذ
    الإجراء على السجل الخطأ.

    الحل: نرتّب قائمة البيانات نفسها ثم نعيد بناء الصفوف كاملةً.

    Args:
        table: الجدول
        sort_keys: {رقم العمود: دالة تعطي مفتاح ترتيب السجل}
                   الأعمدة غير المذكورة لا تُرتَّب (كعمود الأزرار)
        redraw: دالة تُستدعى بعد كل تغيير لإعادة بناء الجدول
        default_column / default_desc: الترتيب الابتدائي
    """

    def __init__(self, table: QTableWidget, sort_keys: dict, redraw,
                 default_column: int = 0, default_desc: bool = False):
        self.table = table
        self.sort_keys = sort_keys
        self.redraw = redraw
        self.column = default_column
        self.descending = default_desc

        header = table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)
        self._update_indicator()

    def _on_header_clicked(self, column: int) -> None:
        if column not in self.sort_keys:
            return  # عمود غير قابل للترتيب (الأزرار مثلاً)

        if column == self.column:
            self.descending = not self.descending
        else:
            self.column = column
            self.descending = False

        self._update_indicator()
        self.redraw()

    def _update_indicator(self) -> None:
        self.table.horizontalHeader().setSortIndicator(
            self.column,
            Qt.DescendingOrder if self.descending else Qt.AscendingOrder,
        )

    def apply(self, records: list) -> list:
        """يرجع نسخة مرتَّبة من السجلات حسب العمود الفعّال"""
        key = self.sort_keys.get(self.column)
        if key is None:
            return list(records)
        return sorted(records, key=key, reverse=self.descending)


@contextmanager
def sorted_table(table: QTableWidget, column: int = 0,
                 order: Qt.SortOrder = Qt.AscendingOrder):
    """
    يعبّئ الجدول بأمان ثم يفعّل الترتيب
    Safely populate a table, then enable sorting

    يعطّل الترتيب أثناء التعبئة — وإلا أعاد Qt الترتيب بعد كل `setItem()`
    فتبعثرت الصفوف — ثم يعيده ويطبّق الترتيب الافتراضي.

    استعمال:
        with sorted_table(self.table, column=0):
            self.table.setRowCount(len(rows))
            for row, item in enumerate(rows):
                ...
    """
    table.setSortingEnabled(False)
    try:
        yield table
    finally:
        table.setSortingEnabled(True)
        if column >= 0:
            table.sortItems(column, order)
