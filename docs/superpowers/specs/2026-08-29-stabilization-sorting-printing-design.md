# مواصفة التطوير: التثبيت، الترتيب، الطباعة

**التاريخ:** ٢٩ أغسطس ٢٠٢٦
**الإصدار المستهدف:** 2.1.0
**الحالة:** بانتظار المراجعة

---

## ١. السياق والقيود

### القيد الحاكم: بيانات حقيقية شغّالة

التطبيق مستخدَم يومياً في المحل على بيانات عملاء حقيقية. الجهاز الهدف يشغّل
`Debt-Manager.exe` مع مجلد `data/` بجانبه. التحديث يصل بنسخ ملف exe جديد فوق القديم.

**ما يترتب على ذلك:**

- أي تغيير في صيغة البيانات يحتاج ترحيل (migration) آمن، قابل للتكرار، مع نسخة
  احتياطية تُنشأ قبله تلقائياً.
- الكتابة على الملفات لازم تبقى ذرّية (temp file + `os.replace`) — انقطاع كهرباء
  في نص الكتابة ما يجوز يخرّب الدفتر.
- كل حساب مالي يبقى بـ `Decimal`، والتخزين نصّي (`str`) — لا `float` في أي مسار
  يمس مبلغاً.
- الاختبارات لازم تشتغل على مجلد مؤقت، ممنوع تلمس `data/` الحقيقي.

### الحالة الحالية

| البند | الوضع |
|---|---|
| التطبيق يشتغل؟ | **لا** — `ModuleNotFoundError: matplotlib` |
| عدد الأسطر | ٤٧٠٤ (بعد تنظيف ٢٢٩ سطر ميت) |
| تحكم بالإصدارات | git، commitان (`edee4e1`, `8b3bfd0`) |
| نسخة احتياطية كاملة | `D:\Projects\Debt-Manager-backup-20260829_161509.zip` |
| اختبارات | `test_basic.py` — سكربت بـ `assert`، ليس مجموعة اختبارات |

---

## ٢. نطاق العمل

ثلاث مراحل متتابعة. المرحلة ١ شرط لازم للاثنتين بعدها (ما بنقدر نختبر شي والتطبيق
ما بيفتح).

| المرحلة | الهدف | ملفات جديدة |
|---|---|---|
| ١ — التثبيت | التطبيق يشتغل؛ البيانات ما بتنخرب | `core/migrations.py`, `tests/` |
| ٢ — الترتيب | ترتيب صحيح بالضغط على رأس العمود | `ui/table_items.py` |
| ٣ — الطباعة | تقرير كل الزبائن + كشف حساب، A4 وحراري | `core/reports.py`, `ui/printing.py` |

**خارج النطاق صراحةً:** التراجع (Undo) — سجل التدقيق بيصير جاهز يدعمه، بس ما رح
ننفذه هالمرة. كذلك رسائل واتساب، الأقساط، تواريخ الاستحقاق، صلاحيات المستخدمين،
النسخ السحابي، أكواد QR.

---

## ٣. المرحلة ١ — التثبيت

### ٣.١ تشغيل التطبيق

**المشكلة:** `ui/main_window.py:15` فيه `from .dashboard import DashboardView` على
مستوى الوحدة، و`ui/dashboard.py:19` بيستورد matplotlib على مستوى الوحدة. مكتبة
ناقصة = التطبيق كله ما بيفتح، مع إنه ١١ ميزة من ١٢ ما إلها علاقة بالرسوم البيانية.

**الحل — استيراد كسول:**

```python
# ui/main_window.py
self.dashboard_view = None          # يُنشأ عند أول استخدام

def show_dashboard(self):
    if self.dashboard_view is None:
        try:
            from .dashboard import DashboardView
        except ImportError as e:
            QMessageBox.warning(self, "لوحة المعلومات غير متاحة",
                                f"مكتبة الرسوم البيانية غير منصّبة:\n{e}")
            return
        self.dashboard_view = DashboardView(self.storage, self)
        self.dashboard_view.back_requested.connect(self.show_customers_view)
        self.dashboard_view.customer_selected.connect(self.show_customer_ledger)
        self.stack.addWidget(self.dashboard_view)
    self.dashboard_view.refresh()
    self.stack.setCurrentWidget(self.dashboard_view)
```

فائدة إضافية: بدء التشغيل بيصير أسرع، لأن استيراد matplotlib لحاله بياخد ثانية أو
اثنتين.

**تنصيب المكتبات الناقصة:** `matplotlib`, `openpyxl`, `pytest`, `pyinstaller`.

`arabic-reshaper` و `python-bidi` **ما رح ننصّبهم** — المرحلة ٣ بتشيل المسار اللي
بيستخدمهم بالكامل.

`requirements.txt` الجديد:

```
PySide6>=6.5.0
matplotlib>=3.7.0
openpyxl>=3.1.0
```

`requirements-dev.txt`:

```
-r requirements.txt
pytest>=8.0
pyinstaller>=6.0
```

`reportlab` بيتشال في المرحلة ٣ لما ينستبدل تصدير PDF.

### ٣.٢ معرّف فريد لكل إدخال

**المشكلة:** `customer_ledger.py:689` و `:769` بيلاقوا الإدخال بمطابقة رباعية:

```python
if (e.customer_id == entry.customer_id and e.date == entry.date
    and e.amount == entry.amount and e.desc == entry.desc):
```

عميل اشترى «أغراض» بـ ٢٠ شيكل مرتين بنفس الدقيقة → أول واحد بس اللي بينحذف أو
بينعدل، والتاني بيضل. ولو عدّل المستخدم واحد فيهم، بيتغير الغلط. هذا خطأ بيانات
حقيقي في دفتر ديون.

**الحل:**

```python
# core/models.py
import uuid
from dataclasses import dataclass, field

def new_entry_id() -> str:
    return uuid.uuid4().hex

@dataclass
class Entry:
    customer_id: str
    type: EntryType
    amount: str
    date: str
    desc: str
    pay_method: PaymentMethod
    notes: str = ""
    id: str = field(default_factory=new_entry_id)
```

`id` بيجي آخر شي لأن `notes` قبله إلها قيمة افتراضية — قيود ترتيب حقول dataclass.
كل استدعاءات `Entry(...)` الحالية بتستخدم keyword arguments، فما في كسر.

`to_dict()` بيضيف `id`. `from_dict()`:

```python
id=data.get('id') or new_entry_id()
```

### ٣.٣ الترحيل (Migration)

ملف جديد `core/migrations.py`. مفتاح `schema_version` جديد في `settings.json`
(القيمة الحالية ضمناً `1`، الهدف `2`).

**ترحيل 1 → 2:**

1. إذا `schema_version >= 2` → لا تعمل شيئاً وارجع (قابل للتكرار بأمان).
2. أنشئ نسخة احتياطية: `data/backups/pre-migration-v2-<timestamp>.zip`.
3. اقرأ `entries.jsonl` كقواميس خام (مش ككائنات `Entry`) — عشان نشوف اللي مكتوب
   حرفياً في الملف.
4. كل سجل بلا `id` (أو `id` فاضي) → أعطه `uuid4().hex`.
5. كل سجل `customer_id` تبعه مش موجود في `customers.json` → احذفه (إدخال يتيم)،
   واحسب العدد.
6. اكتب `entries.jsonl` كتابة ذرّية.
7. `schema_version = 2` في `settings.json`.
8. ارجع تقريراً: كم معرّف أُضيف، كم يتيم انحذف، مسار النسخة الاحتياطية.

**مكان التشغيل:** في `main.py`، بعد `QApplication` وقبل `MainWindow` — عشان نقدر
نعرض رسالة، وما نفتح الواجهة على ملف نص مرحّل.

**عند الفشل:** أظهر خطأً فيه مسار النسخة الاحتياطية وأغلق. لأن الكتابة ذرّية، فشل
في نصّها بيترك الملف الأصلي سليماً.

**ملاحظة عن الأيتام:** `data/entries.jsonl` بالمشروع كان فيه إدخال يتيم واحد
(`خليل_9518`، ٢٠ شيكل، لعميل محذوف) — انحذف في التنظيف. الأيتام أصلاً غير مرئية
ومستثناة من كل الحسابات، فحذفها ما بيغيّر أي رقم يشوفه المستخدم، ومعنا نسخة
احتياطية.

### ٣.٤ عمليات التخزين

**المشكلة:** `customer_ledger.py` فيه ~٨٠ سطر تعامل مباشر مع الملفات (`tempfile.mkstemp`,
`os.replace`) **مكرّرة مرتين** — مرة في `edit_entry` ومرة في `delete_entry`. منطق
تخزين في طبقة الواجهة، ومكرّر.

**الحل — انقلها إلى `StorageManager`:**

```python
def save_entries(self, entries: List[Entry]) -> None
def get_entry(self, entry_id: str) -> Optional[Entry]
def update_entry(self, entry: Entry) -> None                       # حسب id
def delete_entry(self, entry_id: str) -> Entry                     # يرجع المحذوف
def update_customer(self, customer: Customer) -> None
def delete_customer(self, customer_id: str) -> tuple[Customer, int] # مع إدخالاته
```

ودالة `atomic_write_jsonl(path, records)` في `core/storage.py` بنفس نمط
`atomic_write_json` الموجود — أي `os.fdopen(fd, 'w')` اللي بيتملّك الواصف ويغلقه.
(الكود المكرر بالواجهة كان بيعمل `os.close(fd)` ثم يفتح المسار من جديد — بيشتغل بس
فيه سباق.)

### ٣.٥ حذف العميل يحذف إدخالاته

**المشكلة:** `customers_view.py:418` فيه تعليق بيعترف: «الإدخالات تبقى في
entries.jsonl ولكن يمكن تجاهلها». بينما رسالة التأكيد بتقول للمستخدم «سيتم حذف
جميع إدخالات هذا العميل أيضاً». الرسالة بتكذب.

الخطر الحقيقي: توليد المعرّفات `name_random4digits` ممكن نظرياً يعيد إنتاج معرّف
عميل محذوف، فيرث العميل الجديد ديون القديم.

**الحل:** `delete_customer` بيعمل:

1. نسخة احتياطية تلقائية (`create_backup()`) — قبل أي حذف.
2. شيل العميل من `customers.json`.
3. شيل كل إدخالاته من `entries.jsonl`.
4. شيل ملخصه من `summaries.json`.
5. سجّل في سجل التدقيق.
6. ارجع `(customer, deleted_entries_count)`.

الواجهة بتعرض: «تم حذف العميل 'X' و N إدخال. النسخة الاحتياطية: `<المسار>`».

### ٣.٦ تفعيل سجل التدقيق

**المشكلة:** `AuditManager` مبني كاملاً في `core/audit.py` (١٧٢ سطر)، ومُنشَأ في
`main_window.py:82`، و`log_action` **ما انستدعت ولا مرة**. سجل التدقيق ميّت.

**الحل:** خلّي `StorageManager` يملك `AuditManager` ويسجّل داخل دوال التعديل نفسها
— بهيك يستحيل ننسى استدعاءه من الواجهة:

```python
class StorageManager:
    def __init__(self, data_folder: Optional[Path] = None):
        ...
        self.audit = AuditManager(self.data_folder)
```

و`main_window.py` بيستخدم `self.storage.audit` بدل نسخته المنفصلة.

**قرار مهم:** فشل الكتابة في سجل التدقيق **ما بيوقف العملية**. تُغلَّف بـ
`try/except` مع تحذير في شريط الحالة. ما بنخسر تسجيل بيعة لأن ملف السجل ما انكتب.

**حجم السجل:** محل بـ ~٥٠ إدخال يومياً ينتج ~١٨ ألف سجل تدقيق سنوياً، ~٧ ميجابايت.
مقبول. ما في تدوير (rotation) — YAGNI.

### ٣.٧ قابلية الاختبار

`StorageManager.__init__` بياخد `data_folder: Optional[Path] = None` (الافتراضي
`get_data_folder()`). كذلك `ensure_data_folder(folder=None)` و
`create_backup(backup_folder=None, data_folder=None)`.

بهيك الاختبارات بتمرّر `tmp_path` وما بتلمس بيانات حقيقية أبداً — بدون
monkeypatching هش.

### ٣.٨ تنظيفات صغيرة

- `customers_view.py:119` — `"إجمالي الديون: 0.00 ج.م"` → `format_currency(Decimal("0"))`
- `customer_ledger.py:70,74,78` — ثلاث بطاقات فيها `"0.00 ج.م"` → نفس الشي

### ٣.٩ الاختبارات

مجلد `tests/` بـ pytest. `test_basic.py` بينحذف بعد ما تغطّيه:

| الملف | يغطّي |
|---|---|
| `test_models.py` | توليد `id`، `signed_amount`، `validate`، دورة `to_dict`/`from_dict` |
| `test_storage.py` | الكتابة الذرّية، CRUD، الحذف المتتالي، `get_entry` |
| `test_migrations.py` | قابلية التكرار، إضافة المعرّفات، حذف الأيتام، إنشاء النسخة الاحتياطية، عدم فقدان بيانات |
| `test_summaries.py` | الرصيد، مبيعات اليوم/الشهر، الرصيد التراكمي |
| `test_utils.py` | تنسيق العملة، تجزئة كلمة المرور، التحقق من المعرّف، **مفتاح الترتيب العربي** |

---

## ٤. المرحلة ٢ — الترتيب

### ٤.١ المطلوب

ترتيب بالضغط على رأس أي عمود، في الجداول الثلاثة (قائمة العملاء، دفتر العميل،
نتائج البحث). الافتراضي في قائمة العملاء: **أبجدي حسب الاسم**.

### ٤.٢ المشكلة: Qt بيرتّب نصّياً

`QTableWidgetItem` الافتراضي بيقارن نص `Qt.DisplayRole`. يعني `"1,234.00 شيكل"`
بيجي **قبل** `"900.00 شيكل"` لأن `'1' < '9'` نصّياً. نفس المشكلة مع التواريخ
المنسّقة.

### ٤.٣ الحل: عناصر جدول بمفاتيح ترتيب

ملف جديد `ui/table_items.py`:

```python
class NumericItem(QTableWidgetItem):
    """يعرض نصاً منسّقاً، ويرتّب رقمياً."""
    def __init__(self, text: str, value):
        super().__init__(text)
        self._key = float(value)
    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self._key < other._key
        return super().__lt__(other)


class DateTimeItem(QTableWidgetItem):
    """يعرض تاريخاً عربياً، ويرتّب زمنياً."""


class ArabicTextItem(QTableWidgetItem):
    """يرتّب حسب الترتيب الأبجدي العربي الصحيح."""
    def __init__(self, text: str):
        super().__init__(text)
        self._key = arabic_sort_key(text)
```

### ٤.٤ الترتيب الأبجدي العربي

`arabic_sort_key()` في `core/utils.py` (منطق صرف، قابل للاختبار بدون Qt).

ترتيب بايثون الافتراضي بيقارن نقاط اليونيكود، وترتيب كتلة العربية بيحط أشكال
الهمزة **قبل** الألف العادية، والتاء المربوطة بين الباء والتاء. النتيجة غلط.

**متحقَّق منه فعلياً:**

```
بدون تطبيع:  آدم | أحمد | إياد | ابراهيم | بلال | تامر | ...   ← غلط
مع التطبيع:  ابراهيم | أحمد | آدم | إياد | بلال | تامر | ...   ← صح
```

التطبيع: `أ إ آ ٱ → ا` · `ة → ه` · `ى → ي` · `ؤ → و` · `ئ → ي` · حذف التطويل `ـ` ·
حذف التشكيل (NFKD ثم إسقاط combining) · توحيد المسافات · `casefold` للأسماء
اللاتينية.

**سؤال مفتوح:** الأسماء اللاتينية حالياً بتيجي قبل العربية (نقاط يونيكود أقل).
مقبول ومتوقَّع، وما رح نغيّره إلا لو طُلب.

### ٤.٥ مصيدة Qt لازم نتجنبها

لما `setSortingEnabled(True)` وتعبّي الجدول بـ `setItem()` في حلقة، Qt بيعيد
الترتيب بعد **كل** إدخال، فبتتبعثر الصفوف في نص التعبئة. القاعدة:

```python
self.table.setSortingEnabled(False)
# ... تعبئة الجدول ...
self.table.setSortingEnabled(True)
self.table.sortItems(0, Qt.AscendingOrder)   # الافتراضي
```

### ٤.٦ إصلاح إلزامي: البحث بالفهرس ينكسر مع الترتيب

`customer_ledger.py` حالياً بيربط صف الجدول بالإدخال **بالفهرس**:

```python
entry = filtered_entries[row]      # في show_entry_context_menu
```

أول ما يشتغل الترتيب، `row` ما بيوافق `filtered_entries[row]`، فكليك يمين على صف
بيفتح إدخالاً غير اللي ضغطت عليه — يعني بتعدّل أو بتحذف الغلط.

**الحل (إلزامي، مش اختياري):** خزّن `entry.id` في `Qt.UserRole` على عنصر العمود
الأول، واقرأه:

```python
entry_id = self.table.item(row, 0).data(Qt.UserRole)
entry = self.storage.get_entry(entry_id)
```

هذا يعتمد مباشرةً على معرّفات الإدخالات من المرحلة ١ — سبب إضافي إن المرحلة ١ لازم
تسبق.

كذلك `edit_entry(entry, row)` بيفقد معنى معامل `row` — بينحذف.

### ٤.٧ التفاصيل لكل جدول

| الجدول | الأعمدة | الافتراضي |
|---|---|---|
| قائمة العملاء | الاسم `ArabicTextItem`؛ الرصيد ومبيعات اليوم/الشهر `NumericItem` | الاسم تصاعدي |
| دفتر العميل | التاريخ `DateTimeItem`؛ المبلغ `NumericItem`؛ النوع/الوصف/طريقة الدفع نص عادي | التاريخ تنازلي |
| نتائج البحث | العميل `ArabicTextItem`؛ المبلغ `NumericItem`؛ التاريخ `DateTimeItem` | التاريخ تنازلي |

**عمود «الرصيد بعد العملية»:** مفتاح ترتيبه هو **طابع وقت الإدخال**، مش قيمة
الرصيد. لأن الرصيد التراكمي ما إله معنى إلا بترتيب زمني — الضغط على العمود بيعطي
ترتيباً زمنياً، وهو بالضبط الحالة الوحيدة اللي بيكون فيها الرقم صحيح.

**الاستمرارية:** الترتيب ما بينحفظ بين الجلسات. كل فتح بيبدأ من الافتراضي.

---

## ٥. المرحلة ٣ — الطباعة

### ٥.١ المطلوب

- زر طباعة في **قائمة العملاء** → تقرير بكل الزبائن وحساباتهم.
- زر طباعة في **دفتر العميل** → كشف حساب لهذا العميل.
- طابعة **A4** و**حرارية** (٥٨ و ٨٠ ملم).

### ٥.٢ قرار المحرّك: Qt بدل ReportLab

تصدير PDF الحالي بيستخدم `reportlab` + `arabic-reshaper` + `python-bidi`. لكن
`arabic-reshaper` و `python-bidi` **مش منصّبين أصلاً**، فالكود بيقع على الاحتياطي:

```python
except ImportError:
    return text[::-1]        # عكس بسيط — عربي مكسور
```

وحتى مع تنصيبهم، عناوين التقرير كلها إنجليزية (`Customer Ledger Report`,
`Date/Time`, `Type`) في تطبيق عربي بالكامل.

**البديل: `QTextDocument` + `QPrinter`.** محرك النص الغني في Qt هو نفسه اللي
بيرسم الواجهة — بيتعامل مع تشكيل العربية والاتجاه من اليمين لليسار صح تلقائياً،
بدون أي مكتبة تشكيل.

**متحقَّق منه فعلياً على PySide6 6.10.1:**

```
QtPrintSupport import OK
PdfFormat attr: True
custom page size: Thermal80  227 x 842 pt
```

**المكسب:** عربي سليم · معاينة قبل الطباعة مجاناً · إخراج PDF مجاناً ·
**ثلاث مكتبات أقل** · حجم exe أصغر.

### ٥.٣ البنية

**`core/reports.py`** — دوال صرفة تبني HTML. **ما بتستورد Qt**، فبتنختبر لحالها.

```python
@dataclass
class ReportContext:
    shop_name: str
    shop_phone: str
    generated_at: datetime

def build_customers_report(customers, summaries, ctx, paper) -> str
def build_ledger_report(customer, entries, summary, ctx, paper, period_label) -> str
```

`paper` من `{"a4", "thermal80", "thermal58"}`.

**`ui/printing.py`** — آلية Qt.

```python
PAPER_SIZES = {
    "a4":        QPageSize(QPageSize.A4),
    "thermal80": QPageSize(QSizeF(80, H), QPageSize.Millimeter, "Thermal80"),
    "thermal58": QPageSize(QSizeF(58, H), QPageSize.Millimeter, "Thermal58"),
}

def show_print_preview(html, paper, parent, title) -> None
def export_pdf(html, paper, path) -> None
```

### ٥.٤ محتوى التقارير

**تقرير كل الزبائن (A4):**
ترويسة: اسم المحل، الهاتف، عنوان التقرير، التاريخ والوقت.
جدول: `#` · اسم العميل · الهاتف · الرصيد الحالي · مبيعات اليوم · مبيعات الشهر.
تذييل: عدد العملاء · **إجمالي الديون**.
المحتوى: **كل الزبائن** (بما فيهم أصحاب الرصيد صفر)، بنفس ترتيب الجدول المعروض.

**كشف حساب العميل (A4):**
ترويسة: اسم المحل · اسم العميل · هاتفه · حد ائتمانه · تاريخ الكشف.
جدول: التاريخ · النوع · الوصف · طريقة الدفع · المبلغ · الرصيد بعد العملية.
تذييل: إجمالي الديون · إجمالي المدفوعات · **الرصيد المستحق**.
بيحترم الفلتر الفعّال (الكل / اليوم / الشهر).

**الحراري (٥٨ و ٨٠ ملم):**
عمود واحد، بلا حدود جدول، خط أكبر، مسافات أضيق. نفس البيانات بتنسيق قصاصة.

### ٥.٥ حدود `QTextDocument` — نقاط انتباه

`QTextDocument` بيدعم **جزءاً** من CSS 2.1. القيود:

- ممنوع `flexbox` أو `grid`. التخطيط بجداول وخصائص أساسية فقط.
- `dir="rtl"` على عنصر الجسم بيشتغل.
- تكرار رأس الجدول عبر الصفحات: عبر `QTextTableFormat.setHeaderRowCount()`
  برمجياً. هل `<thead>` في HTML بيتحوّل إليه تلقائياً؟ **لازم يُتحقَّق منه أول شي
  في التنفيذ** قبل بناء بقية القالب.
- ارتفاع الورق الحراري: الطابعات الحرارية ورقها متصل، بس Qt بيحتاج ارتفاع صفحة
  ثابت. الحل: رسم أولي لقياس `document.size().height()`، ثم ضبط ارتفاع الصفحة
  عليه — بهيك ما يطلع ذيل فاضي طويل.

### ٥.٦ واجهة الطباعة

`PrintOptionsDialog` جديد في `ui/dialogs.py`:

- الورق: A4 / حراري ٨٠مم / حراري ٥٨مم
- (للدفتر) النطاق: حسب الفلتر الحالي / الكل
- زرّان: «معاينة وطباعة» و «حفظ PDF»

المعاينة عبر `QPrintPreviewDialog`؛ إشارة `paintRequested` بتعطينا `QPrinter`
فنرسم عليه `QTextDocument`.

**مواقع الأزرار:** الشريط العلوي في `customers_view.py`، وبجانب «تصدير» في
`customer_ledger.py`.

### ٥.٧ معلومات المحل

كشف حساب بينعطى للزبون وما فيه اسم المحل مش مقبول. مفتاحان جديدان في
`settings.json`:

- `shop_name` (افتراضي: `"محل الخضار والفواكه"`)
- `shop_phone` (افتراضي: `""`)

وعنصر قائمة جديد تحت «الإعدادات» → «معلومات المحل» بحقلين.

### ٥.٨ استبدال تصدير PDF

جسم `customer_ledger.export_to_pdf` بيصير:

```python
export_pdf(build_ledger_report(...), "a4", path)
```

بعدها `reportlab` بينشال من `requirements.txt`.

---

## ٦. المخاطر والتخفيف

| الخطر | التخفيف |
|---|---|
| **الترحيل على بيانات حقيقية** — أخطر بند بالخطة | نسخة احتياطية تلقائية قبله · كتابة ذرّية · قابل للتكرار · اختبارات تشمل عدم فقدان بيانات · تشغيل تجريبي على نسخة من بيانات المحل قبل النشر |
| **الترتيب يكسر البحث بالفهرس** في الدفتر | إصلاح إلزامي في ٤.٦: البحث بـ `entry.id` بدل رقم الصف. مربوط مباشرة بالمرحلة ١ |
| **CSS محدود في QTextDocument** | تحقق من `<thead>` وتقسيم الصفحات في **أول خطوة** من المرحلة ٣، قبل بناء القوالب |
| **سلوك الطابعة الحرارية** يختلف حسب المُعرِّف (driver) | Qt بيطبع عبر مُعرِّف ويندوز — لازم اختبار على الطابعة الفعلية، مش محاكاة |
| **exe جديد على جهاز المحل** | الاحتفاظ بـ `dist/Debt-Manager.exe` القديم كنسخة رجوع؛ نسخ احتياطي يدوي لمجلد `data/` قبل الاستبدال |

---

## ٧. التحقق

كل مرحلة ما بتخلص إلا لما:

1. `pytest` كله يمر.
2. التطبيق يفتح فعلياً (`python main.py`).
3. فحص يدوي للمسار المتأثر.

**فحص المرحلة ١:** التطبيق يفتح · إضافة دين · تعديله · حذفه · حذف عميل (والتأكد
إن إدخالاته راحت) · التأكد إن `audit.jsonl` انكتب.

**فحص المرحلة ٢:** الضغط على كل رأس عمود في الجداول الثلاثة · التأكد إن ترتيب
المبالغ رقمي مش نصّي · كليك يمين بعد الترتيب يفتح **الإدخال الصحيح**.

**فحص المرحلة ٣:** معاينة التقريرين · التأكد إن العربي متصل ومش مقلوب · حفظ PDF
وفتحه · طباعة على الطابعة الحرارية الفعلية.

---

## ٨. النشر

1. `pytest` يمر بالكامل.
2. `python -m PyInstaller --clean Debt-Manager.spec`.
3. **نسخ احتياطي يدوي لمجلد `data/` على جهاز المحل** — قبل استبدال ملف exe.
4. نسخ `Debt-Manager.exe` الجديد فوق القديم.
5. أول تشغيل بيشغّل الترحيل ويعرض تقريره.
6. تحقق: الأرصدة زي ما كانت، الترتيب شغّال، الطباعة شغّالة.

في حال مشكلة: أرجع `Debt-Manager.exe` القديم واستعد مجلد `data/` من نسخة ما قبل
الترحيل.

---

## ٩. أسئلة مفتوحة

1. **الطابعة الحرارية:** هل مُعرِّفها (driver) منصّب على جهاز المحل وظاهرة في
   طابعات ويندوز؟ Qt بيطبع عبر مُعرِّف النظام، فبدونه ما رح تظهر بقائمة الطابعات.
2. **الأسماء اللاتينية:** حالياً بتيجي قبل العربية في الترتيب. مقبول؟
