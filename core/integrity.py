"""
فحص سلامة ملفات البيانات قبل بناء الواجهة
Data file integrity check, run before building the UI

لماذا
-----
حادثة ١٨ أكتوبر ٢٠٢٦: ملف `checks.json` تلف بعلامة BOM من محرّر خارجي،
فطلع الاستثناء من `setup_ui` إلى خارج `main()` ومات التطبيق برسالة
إنجليزية. صاحب المحل ما عاد يقدر يسجّل بيعة حتى تدخّل تقني.

المبدأ
------
الملفات **الحرجة** (دفتر العملاء والإعدادات) لو تلفت يجب ألا يعمل التطبيق:
معاملة `entries.jsonl` كفارغ تعني عرض «لا ديون على أحد»، وهذا أسوأ ألف
مرة من التوقف الواضح. و`settings.json` حرج لأنه يحمل تجزئة كلمة المرور،
فالتعامل معه كفارغ يتخطّى قفل التطبيق.

الملفات **الثانوية** (الموردون والشيكات والمشتريات) تُعطَّل شاشاتها ويكمل
العمل على العملاء — مع تحذير ظاهر دائماً، لا تعطيل صامت.
"""
from dataclasses import dataclass
from typing import List, Set

from .storage import read_json, read_jsonl
from .utils import DATA_FILES

# دفتر الديون هو جوهر العمل — تلفه يوقف التطبيق
CRITICAL_FILES = {
    "customers.json",
    "entries.jsonl",
    "summaries.json",
    "settings.json",
}

# الجانب الثانوي — تلفه يُعطّل شاشاته فقط
SECONDARY_FILES = {
    "suppliers.json",
    "purchase_orders.json",
    "purchase_items.jsonl",
    "supplier_payments.jsonl",
    "supplier_summaries.json",
    "checks.json",
}

# الملفات التي يعتمد عليها قسم الموردين.
# تلف أيٍّ منها يُعطّل القسم كله: أرصدة الموردين تُحسب من الشيكات ومن
# بنود الشراء، فتعطيل ملف واحد يعرض أرصدة غلط بصمت.
_SUPPLIER_SECTION_FILES = SECONDARY_FILES


@dataclass(frozen=True)
class DataProblem:
    """ملف بيانات تعذّرت قراءته - An unreadable data file"""
    filename: str
    critical: bool
    message: str
    detail: str


def _probe(path) -> str:
    """
    محاولة قراءة ملف. يرجع نص الخطأ، أو سلسلة فارغة إن كان سليماً.

    الملف الغائب ليس تلفاً — التطبيق يعامله كفارغ، وهذا سلوك قائم ومقصود.
    """
    if not path.exists():
        return ""

    try:
        if path.suffix == ".jsonl":
            read_jsonl(path)
        else:
            read_json(path)
        return ""
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def check_data_files(storage) -> List[DataProblem]:
    """
    فحص كل ملفات البيانات
    Check every data file

    **لا يرمي استثناءً أبداً** — الفحص نفسه يجب ألا يكون مصدر انهيار جديد.

    Returns:
        قائمة بالملفات التي تعذّرت قراءتها (فارغة إن كان كل شيء سليماً)
    """
    problems: List[DataProblem] = []

    for filename, _ in DATA_FILES.values():
        detail = _probe(storage.data_folder / filename)
        if not detail:
            continue

        critical = filename in CRITICAL_FILES
        problems.append(DataProblem(
            filename=filename,
            critical=critical,
            message=f"تعذّرت قراءة الملف «{filename}» — محتواه غير سليم.",
            detail=detail,
        ))

    return problems


def has_critical_problem(problems: List[DataProblem]) -> bool:
    """هل بين المشاكل ما يمنع تشغيل التطبيق؟"""
    return any(p.critical for p in problems)


def disabled_sections(problems: List[DataProblem]) -> Set[str]:
    """
    الأقسام التي يجب تعطيلها بسبب ملفات تالفة
    Sections to disable because of unreadable files

    Returns:
        مجموعة من أسماء الأقسام، حالياً {"suppliers"} أو مجموعة فارغة
    """
    sections = set()
    for problem in problems:
        if problem.filename in _SUPPLIER_SECTION_FILES:
            sections.add("suppliers")
    return sections


def summary_arabic(problems: List[DataProblem]) -> str:
    """نص عربي جاهز للعرض في رسالة للمستخدم"""
    if not problems:
        return ""

    lines = []
    for p in problems:
        mark = "⛔" if p.critical else "⚠️"
        lines.append(f"{mark} {p.message}")

    if has_critical_problem(problems):
        lines.append("")
        lines.append("هذا ملف أساسي، فلا يمكن تشغيل البرنامج قبل إصلاحه —")
        lines.append("تشغيله قد يعرض أرصدة خاطئة أو ينسى ديوناً مسجّلة.")
    else:
        lines.append("")
        lines.append("شاشات الموردين والشيكات وفواتير الشراء ستكون معطّلة،")
        lines.append("وبقية البرنامج يعمل بشكل طبيعي.")

    return "\n".join(lines)
