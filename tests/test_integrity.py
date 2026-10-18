"""
فحص سلامة ملفات البيانات قبل الإقلاع

حادثة ١٨ أكتوبر: ملف ثانوي تالف أسقط التطبيق كله برسالة إنجليزية، فما
عاد صاحب المحل يقدر يسجّل بيعة حتى يتدخّل تقني.

المبدأ: الملفات الحرجة لو تلفت **يجب ألا يعمل التطبيق** — عرض «لا ديون
على أحد» أسوأ ألف مرة من التوقف. والثانوية تُعطَّل شاشتها ويكمل العمل.
"""
import pytest

from conftest import make_customer, make_entry, make_supplier
from core.integrity import (
    CRITICAL_FILES,
    SECONDARY_FILES,
    DataProblem,
    check_data_files,
    has_critical_problem,
    disabled_sections,
)

BOM = b"\xef\xbb\xbf"


def test_healthy_data_has_no_problems(storage):
    storage.add_customer(make_customer())
    storage.add_entry(make_entry())
    assert check_data_files(storage) == []


def test_empty_installation_has_no_problems(storage):
    assert check_data_files(storage) == []


# ---------- اكتشاف التلف ----------

def test_detects_corrupt_critical_file(storage):
    storage.customers_file.write_bytes(b"{ this is not json")

    problems = check_data_files(storage)

    assert len(problems) == 1
    assert problems[0].filename == "customers.json"
    assert problems[0].critical is True


def test_detects_corrupt_secondary_file(storage):
    storage.checks_file.write_bytes(b"{ broken")

    problems = check_data_files(storage)

    assert len(problems) == 1
    assert problems[0].filename == "checks.json"
    assert problems[0].critical is False


def test_detects_corrupt_jsonl(storage):
    storage.entries_file.write_bytes(b'{"ok": 1}\nNOT JSON\n')

    problems = check_data_files(storage)

    assert [p.filename for p in problems] == ["entries.jsonl"]


def test_detects_several_problems_at_once(storage):
    storage.customers_file.write_bytes(b"broken")
    storage.checks_file.write_bytes(b"broken")

    names = {p.filename for p in check_data_files(storage)}

    assert names == {"customers.json", "checks.json"}


def test_bom_alone_is_not_a_problem(storage):
    """بعد إصلاح utf-8-sig، الـBOM لم يعد يُعتبر تلفاً"""
    storage.add_customer(make_customer())
    raw = storage.customers_file.read_bytes()
    storage.customers_file.write_bytes(BOM + raw)

    assert check_data_files(storage) == []


def test_missing_file_is_not_a_problem(storage):
    """ملف غائب يُعامل كفارغ — سلوك قائم ومقصود"""
    storage.checks_file.unlink()
    assert check_data_files(storage) == []


def test_problem_carries_readable_arabic_message(storage):
    storage.checks_file.write_bytes(b"broken")

    problem = check_data_files(storage)[0]

    assert "checks.json" in problem.message
    assert any("؀" <= c <= "ۿ" for c in problem.message), \
        "الرسالة يجب أن تكون بالعربية"


# ---------- التصنيف ----------

def test_every_data_file_is_classified():
    """لا ملف بلا تصنيف — وإلا مرّ تلفه بلا قرار"""
    from core.utils import DATA_FILES

    classified = CRITICAL_FILES | SECONDARY_FILES
    actual = {filename for filename, _ in DATA_FILES.values()}

    assert actual == classified, f"غير مصنّف: {actual ^ classified}"


def test_critical_and_secondary_do_not_overlap():
    assert not (CRITICAL_FILES & SECONDARY_FILES)


@pytest.mark.parametrize("filename", [
    "customers.json", "entries.jsonl", "summaries.json", "settings.json",
])
def test_customer_ledger_files_are_critical(filename):
    """
    دفتر الديون هو جوهر العمل. settings.json حرج أيضاً لأنه يحمل تجزئة
    كلمة المرور — التعامل معه كفارغ يتخطّى قفل التطبيق.
    """
    assert filename in CRITICAL_FILES


@pytest.mark.parametrize("filename", [
    "suppliers.json", "checks.json", "purchase_orders.json",
    "purchase_items.jsonl", "supplier_payments.jsonl", "supplier_summaries.json",
])
def test_supplier_side_files_are_secondary(filename):
    assert filename in SECONDARY_FILES


# ---------- القرار ----------

def test_has_critical_problem_true_for_critical(storage):
    storage.entries_file.write_bytes(b"broken")
    assert has_critical_problem(check_data_files(storage))


def test_has_critical_problem_false_for_secondary(storage):
    storage.checks_file.write_bytes(b"broken")
    assert not has_critical_problem(check_data_files(storage))


def test_no_problems_means_no_critical(storage):
    assert not has_critical_problem([])


# ---------- تعطيل الأقسام ----------

def test_broken_checks_disables_whole_supplier_side(storage):
    """
    أرصدة الموردين تُحسب من الشيكات، فتعطيل الشيكات وحدها يعرض أرصدة
    موردين غلط بصمت — وهذا أسوأ من تعطيل القسم كله بوضوح.
    """
    storage.checks_file.write_bytes(b"broken")

    sections = disabled_sections(check_data_files(storage))

    assert sections == {"suppliers"}


def test_broken_purchase_file_disables_supplier_side(storage):
    storage.purchase_items_file.write_bytes(b"NOT JSON\n")
    assert disabled_sections(check_data_files(storage)) == {"suppliers"}


def test_healthy_data_disables_nothing(storage):
    assert disabled_sections([]) == set()


def test_critical_problem_disables_nothing_because_app_will_not_start(storage):
    """التعطيل الجزئي لا معنى له مع تلف حرج — التطبيق لن يعمل أصلاً"""
    storage.customers_file.write_bytes(b"broken")
    problems = check_data_files(storage)
    assert has_critical_problem(problems)


# ---------- لا يرمي استثناءً ----------

def test_check_never_raises_on_weird_bytes(storage):
    """الفحص نفسه يجب ألا يكون مصدر انهيار جديد"""
    storage.checks_file.write_bytes(b"\x00\x01\x02\xff\xfe")
    storage.suppliers_file.write_bytes(b"\xff" * 100)

    problems = check_data_files(storage)

    assert {p.filename for p in problems} == {"checks.json", "suppliers.json"}


def test_check_handles_locked_or_unreadable_file(storage, monkeypatch):
    import builtins

    real_open = builtins.open

    def refuse(path, *a, **k):
        if "checks.json" in str(path):
            raise PermissionError("الملف مستخدم")
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", refuse)

    problems = check_data_files(storage)

    assert [p.filename for p in problems] == ["checks.json"]


# ---------- النافذة الرئيسية في الوضع المعطَّل ----------

@pytest.fixture(scope="module")
def qt_app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def test_app_opens_despite_corrupt_secondary_file(qt_app, storage):
    """
    الجوهر: ملف ثانوي تالف يجب ألا يمنع صاحب المحل من تسجيل بيعة.
    حارس التنقّل وحده لا يكفي — setup_ui يبني الشاشات عند الإقلاع.
    """
    from ui.main_window import MainWindow

    storage.add_customer(make_customer("c1", "خليل"))
    storage.add_entry(make_entry("c1", amount="500.00"))
    storage.checks_file.write_bytes(b"{ broken")

    problems = check_data_files(storage)
    window = MainWindow(storage, disabled=disabled_sections(problems))

    assert window.customers_view is not None, "شاشة العملاء يجب أن تعمل"
    assert len(storage.load_customers()) == 1


def test_disabled_sections_menu_items_are_greyed(qt_app, storage):
    from ui.main_window import MainWindow

    storage.checks_file.write_bytes(b"{ broken")
    window = MainWindow(storage, disabled=disabled_sections(check_data_files(storage)))

    assert not window.suppliers_action.isEnabled()
    assert not window.purchases_action.isEnabled()
    assert not window.checks_action.isEnabled()


def test_healthy_data_keeps_every_section_enabled(qt_app, storage):
    from ui.main_window import MainWindow

    window = MainWindow(storage, disabled=disabled_sections(check_data_files(storage)))

    assert window.suppliers_action.isEnabled()
    assert window.checks_action.isEnabled()
    assert window.suppliers_view is not None


def test_navigating_to_disabled_section_is_refused(qt_app, storage, monkeypatch):
    """الاختصار Ctrl+M يجب ألا يفتح قسماً معطّلاً"""
    from PySide6.QtWidgets import QMessageBox
    from ui.main_window import MainWindow

    storage.checks_file.write_bytes(b"{ broken")
    window = MainWindow(storage, disabled=disabled_sections(check_data_files(storage)))

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    before = window.stack.currentWidget()
    window.show_suppliers_view()

    assert window.stack.currentWidget() is before, "فُتح قسم معطّل"
