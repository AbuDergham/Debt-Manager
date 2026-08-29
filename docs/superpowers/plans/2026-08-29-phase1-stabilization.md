# خطة تنفيذ المرحلة ١ — التثبيت (Stabilization)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** التطبيق يفتح مرة أخرى، وكل إدخال يصير له معرّف فريد، وعمليات الملفات تنتقل من طبقة الواجهة إلى `StorageManager` — بترحيل آمن لبيانات المحل الحقيقية.

**Architecture:** ثلاث حركات. أولاً نجعل الطبقة الأساسية قابلة للاختبار بحقن مجلد بيانات (`data_folder`) بدل المسار العام. ثانياً نضيف `Entry.id` ونبني CRUD كامل في `StorageManager` مع تسجيل تدقيق تلقائي. ثالثاً نكتب ترحيلاً قابلاً للتكرار يعطي المعرّفات للسجلات القديمة ويزيل الأيتام، ونربطه ببدء التشغيل.

**Tech Stack:** Python 3.13 · PySide6 6.10.1 · pytest · JSONL/JSON · Decimal

**Spec:** `docs/superpowers/specs/2026-08-29-stabilization-sorting-printing-design.md`

## Global Constraints

- **بيانات إنتاج حيّة.** التطبيق مستخدم يومياً في محل على بيانات عملاء حقيقية. أي تغيير في صيغة البيانات يحتاج نسخة احتياطية تلقائية قبله، وترحيلاً قابلاً للتكرار (idempotent).
- **كل مبلغ `Decimal`، والتخزين `str`.** ممنوع `float` في أي مسار يمس مبلغاً مالياً. (`float` مسموح فقط في مفاتيح الترتيب وتصدير Excel.)
- **كل كتابة على ملف ذرّية:** `tempfile.mkstemp` → `os.fdopen` → `os.replace`. ممنوع الكتابة المباشرة فوق ملف بيانات.
- **الاختبارات تعمل على `tmp_path` فقط.** ممنوع منعاً باتاً أن يلمس أي اختبار مجلد `data/` الحقيقي.
- **واجهة عربية RTL.** كل نص يراه المستخدم بالعربية. أسماء الدوال والمتغيرات بالإنجليزية، التعليقات والـ docstrings بالعربية+الإنجليزية كما هو النمط القائم.
- **سجل التدقيق لا يوقف عملية تجارية أبداً.** فشل الكتابة فيه يُبتلع بصمت.
- الشغل يبدأ من commit `2db6c2f` على فرع `main`، شجرة نظيفة.

---

## بنية الملفات

| الملف | المسؤولية | الحالة |
|---|---|---|
| `core/utils.py` | أدوات صرفة: مسارات، تنسيق، تجزئة | تعديل — حقن مجلد |
| `core/models.py` | نماذج البيانات | تعديل — `Entry.id` |
| `core/storage.py` | **كل** قراءة/كتابة على القرص + CRUD | تعديل — توسيع كبير |
| `core/backup.py` | ZIP نسخ احتياطي | تعديل — حقن مجلد + بادئة اسم |
| `core/migrations.py` | ترحيل صيغة البيانات | **جديد** |
| `core/audit.py` | سجل التدقيق | بدون تغيير — يُستدعى فقط |
| `main.py` | الإقلاع + تشغيل الترحيل | تعديل |
| `ui/main_window.py` | استيراد كسول للوحة المعلومات | تعديل |
| `ui/customer_ledger.py` | يستهلك CRUD بدل ملفات | تعديل — حذف ~٨٠ سطر |
| `ui/customers_view.py` | يستهلك CRUD بدل ملفات | تعديل |
| `tests/conftest.py` | تركيبات pytest معزولة | **جديد** |
| `tests/test_*.py` | ٥ ملفات اختبار | **جديد** |

---

## Task 1: بنية الاختبارات وحقن مجلد البيانات

الطبقة الأساسية حالياً تنادي `get_data_folder()` العام مباشرة، فأي اختبار يكتب على
`data/` الحقيقي. هذا خطر مع بيانات إنتاج. هذه المهمة تجعل المجلد قابلاً للحقن.

**Files:**
- Modify: `core/utils.py:40` (`ensure_data_folder`)
- Modify: `core/storage.py:129` (`StorageManager.__init__`)
- Modify: `core/backup.py:12` (`create_backup`)
- Create: `tests/conftest.py`
- Create: `tests/test_isolation.py`
- Create: `pytest.ini`
- Modify: `requirements.txt`, create `requirements-dev.txt`

**Interfaces:**
- Produces: `ensure_data_folder(folder: Optional[Path] = None) -> Path`
- Produces: `StorageManager(data_folder: Optional[Path] = None)` مع سمة `.data_folder`
- Produces: `create_backup(backup_folder=None, data_folder=None, prefix="backup") -> Path`
- Produces: تركيبة pytest اسمها `storage` ترجع `StorageManager` على `tmp_path`

- [ ] **Step 1: نصّب المكتبات الناقصة**

```bash
.venv/Scripts/python.exe -m pip install matplotlib openpyxl pytest pyinstaller
```

- [ ] **Step 2: اكتب `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --tb=short
```

- [ ] **Step 3: اكتب `tests/conftest.py`**

```python
"""
تركيبات pytest مشتركة
Shared pytest fixtures — كل اختبار يعمل على مجلد مؤقت معزول
"""
import pytest
from core.storage import StorageManager


@pytest.fixture
def data_folder(tmp_path):
    """مجلد بيانات معزول لكل اختبار"""
    return tmp_path / "data"


@pytest.fixture
def storage(data_folder):
    """مدير تخزين يعمل على المجلد المعزول"""
    return StorageManager(data_folder=data_folder)
```

- [ ] **Step 4: اكتب الاختبار الفاشل — العزل**

`tests/test_isolation.py`:

```python
"""
التحقق من أن الاختبارات لا تلمس بيانات الإنتاج أبداً
"""
from pathlib import Path

from core.utils import get_data_folder


def test_storage_uses_injected_folder(storage, data_folder):
    """مدير التخزين يستخدم المجلد المحقون، لا المسار العام"""
    assert storage.data_folder == data_folder
    assert storage.entries_file == data_folder / "entries.jsonl"


def test_storage_folder_is_not_production(storage):
    """المجلد المستخدم في الاختبار ليس مجلد البيانات الحقيقي"""
    assert storage.data_folder.resolve() != get_data_folder().resolve()


def test_base_files_created(storage, data_folder):
    """الملفات الأساسية تُنشأ داخل المجلد المحقون"""
    assert (data_folder / "customers.json").read_text(encoding="utf-8") == "[]"
    assert (data_folder / "entries.jsonl").read_text(encoding="utf-8") == ""
    assert (data_folder / "summaries.json").read_text(encoding="utf-8") == "{}"
    assert (data_folder / "backups").is_dir()
```

- [ ] **Step 5: شغّل الاختبار وتأكد أنه يفشل**

Run: `.venv/Scripts/python.exe -m pytest tests/test_isolation.py -v`
Expected: FAIL — `TypeError: StorageManager.__init__() got an unexpected keyword argument 'data_folder'`

- [ ] **Step 6: عدّل `ensure_data_folder` في `core/utils.py`**

أعد استيراد `Optional` (أُزيل في التنظيف). السطر ١١ يصير:

```python
from typing import Optional
```

واستبدل الدالة كاملةً:

```python
def ensure_data_folder(folder: Optional[Path] = None) -> Path:
    """
    التأكد من وجود مجلد البيانات وإنشائه إذا لم يكن موجوداً
    Ensure data folder exists, create if it doesn't

    Args:
        folder: مجلد بيانات مخصص (للاختبارات). الافتراضي: مجلد الإنتاج.

    Returns:
        مسار مجلد البيانات
    """
    data_folder = Path(folder) if folder is not None else get_data_folder()
    data_folder.mkdir(parents=True, exist_ok=True)

    # إنشاء مجلد النسخ الاحتياطية
    (data_folder / "backups").mkdir(exist_ok=True)

    # إنشاء الملفات الأساسية إذا لم تكن موجودة
    customers_file = data_folder / "customers.json"
    if not customers_file.exists():
        customers_file.write_text("[]", encoding="utf-8")

    entries_file = data_folder / "entries.jsonl"
    if not entries_file.exists():
        entries_file.write_text("", encoding="utf-8")

    summaries_file = data_folder / "summaries.json"
    if not summaries_file.exists():
        summaries_file.write_text("{}", encoding="utf-8")

    settings_file = data_folder / "settings.json"
    if not settings_file.exists():
        settings_file.write_text(
            '{"theme": "light", "auto_backup_interval": 200}', encoding="utf-8"
        )

    return data_folder
```

- [ ] **Step 7: عدّل `StorageManager.__init__` في `core/storage.py`**

```python
    def __init__(self, data_folder: Optional[Path] = None):
        """
        تهيئة مدير التخزين - Initialize storage manager

        Args:
            data_folder: مجلد بيانات مخصص (للاختبارات). الافتراضي: مجلد الإنتاج.
        """
        self.data_folder = ensure_data_folder(data_folder)
        self.customers_file = self.data_folder / "customers.json"
        self.entries_file = self.data_folder / "entries.jsonl"
        self.summaries_file = self.data_folder / "summaries.json"
        self.settings_file = self.data_folder / "settings.json"
```

`get_data_folder` ما عاد يُستعمل في `storage.py` — احذفه من سطر الاستيراد ١١
فيصير:

```python
from .utils import ensure_data_folder
```

- [ ] **Step 8: عدّل `create_backup` في `core/backup.py`**

```python
def create_backup(
    backup_folder: Optional[Path] = None,
    data_folder: Optional[Path] = None,
    prefix: str = "backup",
) -> Path:
    """
    إنشاء نسخة احتياطية من ملفات البيانات
    Create backup of data files

    Args:
        backup_folder: مجلد النسخة الاحتياطية (افتراضياً: <data>/backups/)
        data_folder: مجلد البيانات المصدر (للاختبارات)
        prefix: بادئة اسم الملف (مثلاً "pre-migration-v2")

    Returns:
        مسار ملف ZIP الناتج
    """
    source_folder = Path(data_folder) if data_folder is not None else get_data_folder()

    if backup_folder is None:
        backup_folder = source_folder / "backups"

    backup_folder = Path(backup_folder)
    backup_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_folder / f"{prefix}_{timestamp}.zip"

    files_to_backup = [
        "customers.json",
        "entries.jsonl",
        "summaries.json",
        "settings.json",
    ]

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for filename in files_to_backup:
            file_path = source_folder / filename
            if file_path.exists():
                zipf.write(file_path, arcname=filename)

    return backup_path
```

- [ ] **Step 9: شغّل الاختبارات وتأكد أنها تنجح**

Run: `.venv/Scripts/python.exe -m pytest tests/test_isolation.py -v`
Expected: PASS — ٣ اختبارات

- [ ] **Step 10: تأكد أن التطبيق ما زال يستورد**

Run: `.venv/Scripts/python.exe -c "import core, ui.main_window; print('OK')"`
Expected: `OK` (matplotlib صار منصّباً في الخطوة ١)

- [ ] **Step 11: حدّث المتطلبات**

`requirements.txt`:

```
PySide6>=6.5.0
reportlab>=4.0.0
matplotlib>=3.7.0
openpyxl>=3.1.0
```

(`reportlab` يبقى مؤقتاً — يُزال في المرحلة ٣. `arabic-reshaper` و `python-bidi`
يُزالان الآن لأنهما غير منصّبين أصلاً والمسار الذي يستخدمهما مكسور.)

`requirements-dev.txt` جديد:

```
-r requirements.txt
pytest>=8.0
pyinstaller>=6.0
```

- [ ] **Step 12: Commit**

```bash
git add core/utils.py core/storage.py core/backup.py tests/ pytest.ini requirements.txt requirements-dev.txt
git commit -m "اختبارات: حقن مجلد البيانات لعزل الاختبارات عن الإنتاج"
```

---

## Task 2: معرّف فريد لكل إدخال

**Files:**
- Modify: `core/models.py:45-130` (`Entry`)
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: تركيبة `storage` من Task 1
- Produces: `new_entry_id() -> str` في `core/models.py`
- Produces: `Entry.id: str` — حقل بقيمة مولّدة تلقائياً، آخر حقول الـ dataclass
- Produces: `Entry.to_dict()` يتضمن `"id"`؛ `Entry.from_dict()` يولّد معرّفاً عند غيابه

- [ ] **Step 1: اكتب الاختبار الفاشل**

`tests/test_models.py`:

```python
"""
اختبارات نماذج البيانات
"""
from datetime import datetime
from decimal import Decimal

import pytest

from core.models import Customer, Entry, Summary, new_entry_id


def make_entry(**overrides) -> Entry:
    """إدخال صالح للاختبار، مع إمكانية تجاوز أي حقل"""
    fields = dict(
        customer_id="ahmad_1234",
        type="purchase",
        amount="100.00",
        date=datetime(2026, 1, 15, 10, 30).isoformat(),
        desc="أغراض",
        pay_method="cash",
    )
    fields.update(overrides)
    return Entry(**fields)


def test_new_entry_id_is_unique():
    """كل استدعاء يعطي معرّفاً مختلفاً"""
    ids = {new_entry_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_entry_gets_id_automatically():
    """الإدخال الجديد يحصل على معرّف بدون تدخل"""
    entry = make_entry()
    assert entry.id
    assert len(entry.id) == 32


def test_two_identical_entries_have_different_ids():
    """إدخالان متطابقان تماماً في كل شيء عدا المعرّف — جوهر الإصلاح"""
    a = make_entry()
    b = make_entry()
    assert a.customer_id == b.customer_id
    assert a.date == b.date
    assert a.amount == b.amount
    assert a.desc == b.desc
    assert a.id != b.id


def test_to_dict_includes_id():
    entry = make_entry()
    assert entry.to_dict()["id"] == entry.id


def test_from_dict_preserves_id():
    """المعرّف المخزّن يُقرأ كما هو"""
    entry = make_entry()
    restored = Entry.from_dict(entry.to_dict())
    assert restored.id == entry.id
    assert restored == entry


def test_from_dict_generates_id_when_missing():
    """سجل قديم بلا معرّف يحصل على واحد عند القراءة"""
    old_record = {
        "customer_id": "ahmad_1234",
        "type": "purchase",
        "amount": "100.00",
        "date": datetime(2026, 1, 15).isoformat(),
        "desc": "أغراض",
        "pay_method": "cash",
    }
    entry = Entry.from_dict(old_record)
    assert entry.id
    assert len(entry.id) == 32


def test_from_dict_generates_id_when_empty_string():
    """معرّف فاضي يُعامل كمفقود"""
    record = make_entry().to_dict()
    record["id"] = ""
    assert Entry.from_dict(record).id


def test_signed_amount_purchase_is_positive():
    assert make_entry(type="purchase", amount="100.00").signed_amount == Decimal("100.00")


def test_signed_amount_payment_is_negative():
    assert make_entry(type="payment", amount="40.00").signed_amount == Decimal("-40.00")


def test_validate_rejects_zero_amount():
    with pytest.raises(ValueError, match="positive"):
        make_entry(amount="0.00").validate()


def test_validate_rejects_negative_amount():
    with pytest.raises(ValueError, match="positive"):
        make_entry(amount="-5.00").validate()


def test_validate_rejects_bad_type():
    with pytest.raises(ValueError, match="Invalid entry type"):
        make_entry(type="refund").validate()


def test_validate_rejects_bad_pay_method():
    with pytest.raises(ValueError, match="Invalid payment method"):
        make_entry(pay_method="crypto").validate()


def test_validate_accepts_valid_entry():
    assert make_entry().validate() is True


def test_customer_round_trip():
    customer = Customer(id="ahmad_1234", name="أحمد", phone="0599123456",
                        credit_limit="500.00", notes="زبون قديم")
    assert Customer.from_dict(customer.to_dict()) == customer


def test_customer_from_dict_defaults_missing_fields():
    """عميل قديم بحقول ناقصة يُقرأ بقيم افتراضية"""
    customer = Customer.from_dict({"id": "x_1", "name": "خليل"})
    assert customer.phone == ""
    assert customer.credit_limit == "0"
    assert customer.notes == ""


def test_summary_empty_is_zero():
    summary = Summary.empty()
    assert summary.balance_decimal == Decimal("0.00")
    assert summary.today_sales_decimal == Decimal("0.00")
    assert summary.month_sales_decimal == Decimal("0.00")
```

- [ ] **Step 2: شغّل واتأكد من الفشل**

Run: `.venv/Scripts/python.exe -m pytest tests/test_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'new_entry_id' from 'core.models'`

- [ ] **Step 3: نفّذ التغيير في `core/models.py`**

بدّل سطر الاستيراد ٥ ليصير:

```python
import uuid
from dataclasses import dataclass, asdict, field
```

أضف الدالة قبل `class Customer` مباشرةً:

```python
def new_entry_id() -> str:
    """
    توليد معرّف فريد لإدخال جديد
    Generate a unique entry ID
    """
    return uuid.uuid4().hex
```

في `class Entry`، أضف الحقل بعد `notes` مباشرةً:

```python
    notes: str = ""  # ملاحظات داخلية لا تظهر للعميل
    id: str = field(default_factory=new_entry_id)  # معرّف فريد
```

> **لماذا `id` آخر شيء؟** `notes` قبله له قيمة افتراضية، وقواعد dataclass تمنع
> حقلاً بلا قيمة افتراضية بعد حقل له واحدة. تحقّقنا أن كل استدعاءات `Entry(...)`
> في المشروع تستخدم keyword arguments، فالترتيب لا يكسر شيئاً.

في `to_dict` أضف المفتاح:

```python
    def to_dict(self):
        """تحويل إلى قاموس - Convert to dictionary"""
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'type': self.type,
            'amount': self.amount,
            'date': self.date,
            'desc': self.desc,
            'pay_method': self.pay_method,
            'notes': self.notes
        }
```

في `from_dict` أضف السطر الأخير:

```python
    @staticmethod
    def from_dict(data: dict) -> 'Entry':
        """إنشاء من قاموس - Create from dictionary"""
        return Entry(
            customer_id=data['customer_id'],
            type=data['type'],
            amount=data['amount'],
            date=data['date'],
            desc=data['desc'],
            pay_method=data['pay_method'],
            notes=data.get('notes', ''),
            id=data.get('id') or new_entry_id()
        )
```

- [ ] **Step 4: شغّل واتأكد من النجاح**

Run: `.venv/Scripts/python.exe -m pytest tests/test_models.py -v`
Expected: PASS — ١٨ اختباراً

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "نماذج: معرّف uuid فريد لكل إدخال"
```

---

## Task 3: كتابة JSONL ذرّية + ربط سجل التدقيق

**Files:**
- Modify: `core/storage.py` — أضف `atomic_write_jsonl` و `_log` و `save_entries`
- Modify: `core/storage.py:191` (`add_entry`) و `:156` (`add_customer`) — أضف تسجيلاً
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: `Entry.id` من Task 2
- Produces: `atomic_write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None`
- Produces: `StorageManager.audit: AuditManager`
- Produces: `StorageManager._log(action, entity_type, entity_id, old_data=None, new_data=None) -> None`
- Produces: `StorageManager.save_entries(entries: List[Entry]) -> None`

- [ ] **Step 1: اكتب الاختبار الفاشل**

`tests/test_storage.py`:

```python
"""
اختبارات طبقة التخزين
"""
import json
from datetime import datetime

import pytest

from core.models import Customer, Entry
from core.storage import atomic_write_jsonl


def make_customer(cid="ahmad_1234", name="أحمد") -> Customer:
    return Customer(id=cid, name=name)


def make_entry(customer_id="ahmad_1234", **overrides) -> Entry:
    fields = dict(
        customer_id=customer_id,
        type="purchase",
        amount="100.00",
        date=datetime(2026, 1, 15, 10, 30).isoformat(),
        desc="أغراض",
        pay_method="cash",
    )
    fields.update(overrides)
    return Entry(**fields)


# ---------- الكتابة الذرّية ----------

def test_atomic_write_jsonl_writes_one_line_per_record(tmp_path):
    path = tmp_path / "out.jsonl"
    atomic_write_jsonl(path, [{"a": 1}, {"a": 2}, {"a": 3}])
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[1]) == {"a": 2}


def test_atomic_write_jsonl_preserves_arabic(tmp_path):
    path = tmp_path / "out.jsonl"
    atomic_write_jsonl(path, [{"name": "خليل بركات"}])
    assert "خليل بركات" in path.read_text(encoding="utf-8")


def test_atomic_write_jsonl_empty_list_truncates(tmp_path):
    path = tmp_path / "out.jsonl"
    path.write_text('{"old": true}\n', encoding="utf-8")
    atomic_write_jsonl(path, [])
    assert path.read_text(encoding="utf-8") == ""


def test_atomic_write_jsonl_leaves_no_temp_files(tmp_path):
    path = tmp_path / "out.jsonl"
    atomic_write_jsonl(path, [{"a": 1}])
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_jsonl_keeps_original_on_failure(tmp_path):
    """سجل غير قابل للتحويل إلى JSON يترك الملف الأصلي سليماً"""
    path = tmp_path / "out.jsonl"
    path.write_text('{"original": true}\n', encoding="utf-8")
    with pytest.raises(TypeError):
        atomic_write_jsonl(path, [{"bad": object()}])
    assert path.read_text(encoding="utf-8") == '{"original": true}\n'
    assert list(tmp_path.glob("*.tmp")) == []


# ---------- save_entries ----------

def test_save_entries_round_trip(storage):
    storage.add_customer(make_customer())
    entries = [make_entry(amount="10.00"), make_entry(amount="20.00")]
    storage.save_entries(entries)
    loaded = storage.load_entries()
    assert [e.amount for e in loaded] == ["10.00", "20.00"]
    assert [e.id for e in loaded] == [e.id for e in entries]


# ---------- سجل التدقيق ----------

def test_add_customer_is_audited(storage):
    storage.add_customer(make_customer())
    history = storage.audit.get_history(entity_type="customer")
    assert len(history) == 1
    assert history[0].action == "create"
    assert history[0].entity_id == "ahmad_1234"
    assert history[0].new_data["name"] == "أحمد"


def test_add_entry_is_audited(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    history = storage.audit.get_history(entity_type="entry")
    assert len(history) == 1
    assert history[0].action == "create"
    assert history[0].entity_id == entry.id


def test_audit_failure_does_not_block_operation(storage, monkeypatch):
    """فشل سجل التدقيق لا يمنع حفظ عملية تجارية — قرار مقصود"""
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(storage.audit, "log_action", boom)
    storage.add_customer(make_customer())
    assert len(storage.load_customers()) == 1
```

- [ ] **Step 2: شغّل واتأكد من الفشل**

Run: `.venv/Scripts/python.exe -m pytest tests/test_storage.py -v`
Expected: FAIL — `ImportError: cannot import name 'atomic_write_jsonl' from 'core.storage'`

- [ ] **Step 3: أضف `atomic_write_jsonl` إلى `core/storage.py`**

ضعها بعد `atomic_append_jsonl` مباشرةً:

```python
def atomic_write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    """
    كتابة ملف JSONL كاملاً بشكل ذري
    Atomic full-file JSONL write

    تُستخدم عند التعديل أو الحذف، لأن JSONL صيغة append-only فلا يمكن
    تعديل سطر واحد في مكانه — يجب إعادة كتابة الملف كله.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix='.tmp', text=True)

    try:
        # os.fdopen يتملّك الواصف ويغلقه — لا نفتح المسار مرة ثانية
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
```

- [ ] **Step 4: اربط سجل التدقيق بـ `StorageManager`**

أضف الاستيراد أعلى `core/storage.py`:

```python
from .audit import AuditManager, ActionType, EntityType
```

في `__init__` أضف بعد `self.settings_file`:

```python
        # سجل التدقيق — يُسجَّل تلقائياً في كل عملية تعديل
        self.audit = AuditManager(self.data_folder)
```

وأضف المساعد الخاص بعد `__init__`:

```python
    def _log(
        self,
        action: ActionType,
        entity_type: EntityType,
        entity_id: str,
        old_data: Optional[dict] = None,
        new_data: Optional[dict] = None,
    ) -> None:
        """
        تسجيل عملية في سجل التدقيق

        فشل التسجيل لا يوقف العملية التجارية أبداً — لا نخسر تسجيل بيعة
        لأن ملف السجل تعذّرت الكتابة فيه.
        """
        try:
            self.audit.log_action(action, entity_type, entity_id, old_data, new_data)
        except Exception:
            pass
```

- [ ] **Step 5: أضف `save_entries` وسجّل في `add_customer` و `add_entry`**

`save_entries` — ضعها بعد `load_entries`:

```python
    def save_entries(self, entries: List[Entry]) -> None:
        """
        حفظ جميع الإدخالات (إعادة كتابة الملف كاملاً)
        Save all entries — full atomic rewrite
        """
        atomic_write_jsonl(self.entries_file, [e.to_dict() for e in entries])
```

في `add_customer`، بعد `self.save_customers(customers)` أضف:

```python
        self._log("create", "customer", customer.id, new_data=customer.to_dict())
```

في `add_entry`، بعد `atomic_append_jsonl(...)` أضف:

```python
        self._log("create", "entry", entry.id, new_data=entry.to_dict())
```

- [ ] **Step 6: شغّل واتأكد من النجاح**

Run: `.venv/Scripts/python.exe -m pytest tests/test_storage.py -v`
Expected: PASS — ٩ اختبارات

- [ ] **Step 7: Commit**

```bash
git add core/storage.py tests/test_storage.py
git commit -m "تخزين: كتابة JSONL ذرّية وتفعيل سجل التدقيق"
```

---

## Task 4: CRUD الإدخالات

هنا ينتقل منطق تعديل وحذف الإدخالات من `ui/customer_ledger.py` إلى مكانه الصحيح،
ويصير البحث بالمعرّف بدل المطابقة الرباعية الهشّة.

**Files:**
- Modify: `core/storage.py` — أضف `get_entry`, `update_entry`, `delete_entry`
- Modify: `tests/test_storage.py` — أضف اختبارات

**Interfaces:**
- Consumes: `save_entries`, `_log` من Task 3
- Produces: `StorageManager.get_entry(entry_id: str) -> Optional[Entry]`
- Produces: `StorageManager.update_entry(entry: Entry) -> None` — يرفع `KeyError` إذا لم يوجد
- Produces: `StorageManager.delete_entry(entry_id: str) -> Entry` — يرجع المحذوف، يرفع `KeyError`

- [ ] **Step 1: اكتب الاختبارات الفاشلة**

أضف إلى نهاية `tests/test_storage.py`:

```python
# ---------- CRUD الإدخالات ----------

def test_get_entry_by_id(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    assert storage.get_entry(entry.id).amount == "100.00"


def test_get_entry_returns_none_when_missing(storage):
    assert storage.get_entry("nonexistent") is None


def test_update_entry_changes_only_target(storage):
    storage.add_customer(make_customer())
    a, b = make_entry(amount="10.00"), make_entry(amount="20.00")
    storage.add_entry(a)
    storage.add_entry(b)

    a.amount = "15.00"
    storage.update_entry(a)

    assert storage.get_entry(a.id).amount == "15.00"
    assert storage.get_entry(b.id).amount == "20.00"


def test_update_entry_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.update_entry(make_entry())


def test_update_entry_rejects_invalid(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    entry.amount = "-5.00"
    with pytest.raises(ValueError):
        storage.update_entry(entry)


def test_delete_entry_removes_only_target(storage):
    storage.add_customer(make_customer())
    a, b = make_entry(amount="10.00"), make_entry(amount="20.00")
    storage.add_entry(a)
    storage.add_entry(b)

    removed = storage.delete_entry(a.id)

    assert removed.id == a.id
    assert storage.get_entry(a.id) is None
    assert storage.get_entry(b.id) is not None
    assert len(storage.load_entries()) == 1


def test_delete_correct_one_of_two_identical_entries(storage):
    """
    جوهر الإصلاح: إدخالان متطابقان في العميل والتاريخ والمبلغ والوصف.
    المطابقة الرباعية القديمة كانت تحذف الأول دائماً.
    """
    storage.add_customer(make_customer())
    first, second = make_entry(), make_entry()
    storage.add_entry(first)
    storage.add_entry(second)

    storage.delete_entry(second.id)

    remaining = storage.load_entries()
    assert len(remaining) == 1
    assert remaining[0].id == first.id


def test_delete_entry_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.delete_entry("nonexistent")


def test_update_entry_is_audited(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    entry.amount = "55.00"
    storage.update_entry(entry)

    history = storage.audit.get_history(entity_type="entry", entity_id=entry.id)
    update = next(h for h in history if h.action == "update")
    assert update.old_data["amount"] == "100.00"
    assert update.new_data["amount"] == "55.00"


def test_delete_entry_is_audited(storage):
    storage.add_customer(make_customer())
    entry = make_entry()
    storage.add_entry(entry)
    storage.delete_entry(entry.id)

    history = storage.audit.get_history(entity_type="entry", entity_id=entry.id)
    assert any(h.action == "delete" and h.old_data["amount"] == "100.00" for h in history)
```

- [ ] **Step 2: شغّل واتأكد من الفشل**

Run: `.venv/Scripts/python.exe -m pytest tests/test_storage.py -k "entry and (get or update or delete)" -v`
Expected: FAIL — `AttributeError: 'StorageManager' object has no attribute 'get_entry'`

- [ ] **Step 3: نفّذ الدوال الثلاث في `core/storage.py`**

ضعها بعد `get_customer_entries`:

```python
    def get_entry(self, entry_id: str) -> Optional[Entry]:
        """
        الحصول على إدخال بواسطة المعرّف
        Get entry by ID
        """
        for entry in self.load_entries():
            if entry.id == entry_id:
                return entry
        return None

    def update_entry(self, entry: Entry) -> None:
        """
        تحديث إدخال موجود (البحث بالمعرّف)
        Update an existing entry, matched by ID

        Raises:
            KeyError: إذا لم يوجد إدخال بهذا المعرّف
            ValueError: إذا كانت بيانات الإدخال غير صالحة
        """
        entry.validate()

        entries = self.load_entries()
        for i, existing in enumerate(entries):
            if existing.id == entry.id:
                old_data = existing.to_dict()
                entries[i] = entry
                self.save_entries(entries)
                self._log("update", "entry", entry.id,
                          old_data=old_data, new_data=entry.to_dict())
                return

        raise KeyError(f"Entry not found: {entry.id}")

    def delete_entry(self, entry_id: str) -> Entry:
        """
        حذف إدخال (البحث بالمعرّف)
        Delete an entry, matched by ID

        Returns:
            الإدخال المحذوف

        Raises:
            KeyError: إذا لم يوجد إدخال بهذا المعرّف
        """
        entries = self.load_entries()
        for i, existing in enumerate(entries):
            if existing.id == entry_id:
                removed = entries.pop(i)
                self.save_entries(entries)
                self._log("delete", "entry", entry_id, old_data=removed.to_dict())
                return removed

        raise KeyError(f"Entry not found: {entry_id}")
```

- [ ] **Step 4: شغّل واتأكد من النجاح**

Run: `.venv/Scripts/python.exe -m pytest tests/test_storage.py -v`
Expected: PASS — ١٩ اختباراً

- [ ] **Step 5: Commit**

```bash
git add core/storage.py tests/test_storage.py
git commit -m "تخزين: CRUD الإدخالات بالبحث عن المعرّف بدل المطابقة الرباعية"
```

---

## Task 5: CRUD العملاء مع الحذف المتتالي

**Files:**
- Modify: `core/storage.py` — أضف `update_customer`, `delete_customer`
- Modify: `tests/test_storage.py`

**Interfaces:**
- Consumes: `save_entries`, `_log` من Task 3؛ `create_backup(data_folder=...)` من Task 1
- Produces: `StorageManager.update_customer(customer: Customer) -> None` — يرفع `KeyError`
- Produces: `StorageManager.delete_customer(customer_id: str) -> tuple[Customer, int, Path]`
  ترجع `(العميل المحذوف، عدد الإدخالات المحذوفة، مسار النسخة الاحتياطية)`

> **انحراف مقصود عن المواصفة:** المواصفة (٣.٥) كتبت `tuple[Customer, int]`.
> أضفنا `Path` لأن الواجهة تحتاج عرض مسار النسخة الاحتياطية للمستخدم، والبديل
> استدعاء ثانٍ للنسخ الاحتياطي أو متغيّر عام — كلاهما أسوأ.

- [ ] **Step 1: اكتب الاختبارات الفاشلة**

أضف إلى نهاية `tests/test_storage.py`:

```python
# ---------- CRUD العملاء ----------

def test_update_customer(storage):
    storage.add_customer(make_customer())
    updated = Customer(id="ahmad_1234", name="أحمد محمود",
                       phone="0599123456", credit_limit="500.00", notes="ملاحظة")
    storage.update_customer(updated)

    loaded = storage.get_customer("ahmad_1234")
    assert loaded.name == "أحمد محمود"
    assert loaded.phone == "0599123456"
    assert loaded.credit_limit == "500.00"


def test_update_customer_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.update_customer(make_customer())


def test_delete_customer_removes_their_entries(storage):
    """المشكلة الأصلية: الإدخالات كانت تبقى يتيمة بعد حذف العميل"""
    storage.add_customer(make_customer("ahmad_1234", "أحمد"))
    storage.add_customer(make_customer("khalil_5678", "خليل"))
    storage.add_entry(make_entry("ahmad_1234", amount="10.00"))
    storage.add_entry(make_entry("ahmad_1234", amount="20.00"))
    storage.add_entry(make_entry("khalil_5678", amount="30.00"))

    customer, deleted_count, backup_path = storage.delete_customer("ahmad_1234")

    assert customer.name == "أحمد"
    assert deleted_count == 2
    remaining = storage.load_entries()
    assert len(remaining) == 1
    assert remaining[0].customer_id == "khalil_5678"


def test_delete_customer_creates_backup_first(storage):
    storage.add_customer(make_customer())
    storage.add_entry(make_entry())

    _, _, backup_path = storage.delete_customer("ahmad_1234")

    assert backup_path.exists()
    assert backup_path.suffix == ".zip"

    import zipfile
    with zipfile.ZipFile(backup_path) as z:
        # النسخة الاحتياطية تحوي البيانات كما كانت قبل الحذف
        assert "أحمد" in z.read("customers.json").decode("utf-8")
        assert len(z.read("entries.jsonl").decode("utf-8").strip().split("\n")) == 1


def test_delete_customer_removes_summary(storage):
    from core.models import Summary
    storage.add_customer(make_customer())
    storage.save_summaries({"ahmad_1234": Summary.empty()})

    storage.delete_customer("ahmad_1234")

    assert "ahmad_1234" not in storage.load_summaries()


def test_delete_customer_raises_when_missing(storage):
    with pytest.raises(KeyError):
        storage.delete_customer("nonexistent")


def test_delete_customer_with_no_entries(storage):
    storage.add_customer(make_customer())
    _, deleted_count, _ = storage.delete_customer("ahmad_1234")
    assert deleted_count == 0


def test_customer_id_reuse_is_safe_after_delete(storage):
    """
    الخطر الأصلي: عميل جديد يرث ديون عميل محذوف بنفس المعرّف.
    """
    storage.add_customer(make_customer("ahmad_1234", "أحمد"))
    storage.add_entry(make_entry("ahmad_1234", amount="500.00"))
    storage.delete_customer("ahmad_1234")

    storage.add_customer(make_customer("ahmad_1234", "أحمد آخر"))

    assert storage.get_customer_entries("ahmad_1234") == []


def test_delete_customer_is_audited(storage):
    storage.add_customer(make_customer())
    storage.delete_customer("ahmad_1234")

    history = storage.audit.get_history(entity_type="customer", entity_id="ahmad_1234")
    assert any(h.action == "delete" and h.old_data["name"] == "أحمد" for h in history)
```

- [ ] **Step 2: شغّل واتأكد من الفشل**

Run: `.venv/Scripts/python.exe -m pytest tests/test_storage.py -k customer -v`
Expected: FAIL — `AttributeError: 'StorageManager' object has no attribute 'update_customer'`

- [ ] **Step 3: نفّذ الدالتين في `core/storage.py`**

أضف الاستيراد أعلى الملف:

```python
from .backup import create_backup
```

> **لا دورة استيراد:** `core/backup.py` يستورد من `core/utils.py` فقط، و
> `core/utils.py` لا يستورد شيئاً من `core`.

ضع الدالتين بعد `get_customer`:

```python
    def update_customer(self, customer: Customer) -> None:
        """
        تحديث بيانات عميل موجود
        Update an existing customer

        Raises:
            KeyError: إذا لم يوجد عميل بهذا المعرّف
        """
        customers = self.load_customers()
        for i, existing in enumerate(customers):
            if existing.id == customer.id:
                old_data = existing.to_dict()
                customers[i] = customer
                self.save_customers(customers)
                self._log("update", "customer", customer.id,
                          old_data=old_data, new_data=customer.to_dict())
                return

        raise KeyError(f"Customer not found: {customer.id}")

    def delete_customer(self, customer_id: str) -> tuple[Customer, int, Path]:
        """
        حذف عميل مع جميع إدخالاته
        Delete a customer and all their entries

        تُنشأ نسخة احتياطية تلقائياً قبل أي حذف.

        Returns:
            (العميل المحذوف، عدد الإدخالات المحذوفة، مسار النسخة الاحتياطية)

        Raises:
            KeyError: إذا لم يوجد عميل بهذا المعرّف
        """
        customers = self.load_customers()
        customer = next((c for c in customers if c.id == customer_id), None)
        if customer is None:
            raise KeyError(f"Customer not found: {customer_id}")

        # نسخة احتياطية قبل أي تعديل — الحذف لا رجعة فيه
        backup_path = create_backup(data_folder=self.data_folder,
                                    prefix="pre-delete")

        self.save_customers([c for c in customers if c.id != customer_id])

        entries = self.load_entries()
        remaining = [e for e in entries if e.customer_id != customer_id]
        deleted_count = len(entries) - len(remaining)
        self.save_entries(remaining)

        summaries = self.load_summaries()
        summaries.pop(customer_id, None)
        self.save_summaries(summaries)

        self._log("delete", "customer", customer_id, old_data=customer.to_dict())

        return customer, deleted_count, backup_path
```

- [ ] **Step 4: شغّل واتأكد من النجاح**

Run: `.venv/Scripts/python.exe -m pytest tests/test_storage.py -v`
Expected: PASS — ٢٨ اختباراً

- [ ] **Step 5: Commit**

```bash
git add core/storage.py tests/test_storage.py
git commit -m "تخزين: حذف العميل يحذف إدخالاته، مع نسخة احتياطية تلقائية"
```

---

## Task 6: وحدة الترحيل

**Files:**
- Create: `core/migrations.py`
- Create: `tests/test_migrations.py`
- Modify: `core/__init__.py` — تصدير `run_migrations`

**Interfaces:**
- Consumes: `atomic_write_jsonl`, `read_jsonl` من `core/storage.py`؛ `new_entry_id` من `core/models.py`؛ `create_backup(prefix=...)` من Task 1
- Produces: `SCHEMA_VERSION: int = 2`
- Produces: `MigrationReport` — dataclass بحقول `ran, from_version, to_version, ids_added, orphans_removed, backup_path`
- Produces: `run_migrations(storage: StorageManager) -> MigrationReport`
- Produces: `MigrationReport.summary_arabic() -> str` — نص جاهز للعرض في رسالة

- [ ] **Step 1: اكتب الاختبارات الفاشلة**

`tests/test_migrations.py`:

```python
"""
اختبارات ترحيل صيغة البيانات

الأخطر في المشروع كله: يعمل على بيانات إنتاج حقيقية.
"""
import json
import zipfile
from datetime import datetime

from core.migrations import SCHEMA_VERSION, run_migrations


def write_legacy_data(storage, customers, entry_records):
    """كتابة بيانات بصيغة ما قبل الترحيل (بلا معرّفات، بلا schema_version)"""
    storage.customers_file.write_text(
        json.dumps(customers, ensure_ascii=False), encoding="utf-8"
    )
    storage.entries_file.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in entry_records),
        encoding="utf-8",
    )


def legacy_entry(customer_id, amount="20.00", desc="أغراض"):
    """سجل إدخال بالصيغة القديمة — بلا حقل id"""
    return {
        "customer_id": customer_id,
        "type": "purchase",
        "amount": amount,
        "date": datetime(2025, 12, 11, 16, 6, 52).isoformat(),
        "desc": desc,
        "pay_method": "cash",
        "notes": "",
    }


def test_migration_assigns_ids_to_legacy_entries(storage):
    write_legacy_data(
        storage,
        [{"id": "khalil_9518", "name": "خليل"}],
        [legacy_entry("khalil_9518", "20.00"), legacy_entry("khalil_9518", "30.00")],
    )

    report = run_migrations(storage)

    assert report.ran is True
    assert report.ids_added == 2
    ids = [e.id for e in storage.load_entries()]
    assert all(ids)
    assert len(set(ids)) == 2


def test_migration_removes_orphaned_entries(storage):
    """الإدخال اليتيم: عميله محذوف من customers.json"""
    write_legacy_data(
        storage,
        [{"id": "khalil_9518", "name": "خليل"}],
        [legacy_entry("khalil_9518"), legacy_entry("deleted_customer_0000")],
    )

    report = run_migrations(storage)

    assert report.orphans_removed == 1
    entries = storage.load_entries()
    assert len(entries) == 1
    assert entries[0].customer_id == "khalil_9518"


def test_migration_creates_backup_before_writing(storage):
    write_legacy_data(storage, [{"id": "k_1", "name": "خليل"}], [legacy_entry("k_1")])

    report = run_migrations(storage)

    assert report.backup_path is not None
    assert report.backup_path.exists()
    assert "pre-migration" in report.backup_path.name
    with zipfile.ZipFile(report.backup_path) as z:
        # النسخة تحوي الصيغة القديمة قبل الترحيل
        assert '"id"' not in z.read("entries.jsonl").decode("utf-8")


def test_migration_is_idempotent(storage):
    """تشغيلها مرتين لا يغيّر شيئاً في المرة الثانية — شرط أساسي"""
    write_legacy_data(storage, [{"id": "k_1", "name": "خليل"}], [legacy_entry("k_1")])

    run_migrations(storage)
    after_first = storage.entries_file.read_text(encoding="utf-8")

    second = run_migrations(storage)

    assert second.ran is False
    assert second.ids_added == 0
    assert second.orphans_removed == 0
    assert storage.entries_file.read_text(encoding="utf-8") == after_first


def test_migration_sets_schema_version(storage):
    write_legacy_data(storage, [{"id": "k_1", "name": "خليل"}], [legacy_entry("k_1")])
    run_migrations(storage)
    assert storage.get_setting("schema_version") == SCHEMA_VERSION


def test_migration_preserves_all_business_data(storage):
    """لا يفقد الترحيل أي حقل: المبلغ، التاريخ، الوصف، طريقة الدفع، الملاحظات"""
    record = legacy_entry("k_1", "123.45", "بندورة وخيار")
    record["notes"] = "ملاحظة داخلية"
    record["pay_method"] = "transfer"
    record["type"] = "payment"
    write_legacy_data(storage, [{"id": "k_1", "name": "خليل"}], [record])

    run_migrations(storage)

    entry = storage.load_entries()[0]
    assert entry.customer_id == "k_1"
    assert entry.amount == "123.45"
    assert entry.desc == "بندورة وخيار"
    assert entry.notes == "ملاحظة داخلية"
    assert entry.pay_method == "transfer"
    assert entry.type == "payment"
    assert entry.date == record["date"]


def test_migration_preserves_existing_ids(storage):
    """سجل له معرّف مسبقاً يحتفظ به"""
    record = legacy_entry("k_1")
    record["id"] = "existing_id_abc"
    write_legacy_data(storage, [{"id": "k_1", "name": "خليل"}], [record])

    report = run_migrations(storage)

    assert report.ids_added == 0
    assert storage.load_entries()[0].id == "existing_id_abc"


def test_migration_treats_empty_id_as_missing(storage):
    record = legacy_entry("k_1")
    record["id"] = ""
    write_legacy_data(storage, [{"id": "k_1", "name": "خليل"}], [record])

    report = run_migrations(storage)

    assert report.ids_added == 1
    assert storage.load_entries()[0].id


def test_migration_on_empty_data(storage):
    """تركيب جديد بلا بيانات — لا ينهار"""
    report = run_migrations(storage)
    assert report.ran is True
    assert report.ids_added == 0
    assert report.orphans_removed == 0


def test_migration_report_arabic_summary(storage):
    write_legacy_data(
        storage,
        [{"id": "k_1", "name": "خليل"}],
        [legacy_entry("k_1"), legacy_entry("gone_0000")],
    )
    report = run_migrations(storage)
    summary = report.summary_arabic()
    assert "1" in summary
    assert isinstance(summary, str) and summary.strip()
```

- [ ] **Step 2: شغّل واتأكد من الفشل**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.migrations'`

- [ ] **Step 3: اكتب `core/migrations.py`**

```python
"""
ترحيل صيغة البيانات
Data schema migrations

كل ترحيل:
  - قابل للتكرار (idempotent) — تشغيله مرتين آمن
  - ينشئ نسخة احتياطية قبل أي كتابة
  - يكتب كتابةً ذرّية، ففشله في المنتصف يترك الملف الأصلي سليماً
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .backup import create_backup
from .models import new_entry_id
from .storage import atomic_write_jsonl, read_jsonl

# النسخة الحالية لصيغة البيانات
SCHEMA_VERSION = 2


@dataclass
class MigrationReport:
    """تقرير عمّا فعله الترحيل - Report of what the migration did"""
    ran: bool
    from_version: int
    to_version: int
    ids_added: int
    orphans_removed: int
    backup_path: Optional[Path]

    def summary_arabic(self) -> str:
        """نص عربي جاهز للعرض في رسالة للمستخدم"""
        if not self.ran:
            return "البيانات محدّثة — لا حاجة لأي ترحيل."

        lines = [f"تم تحديث صيغة البيانات من الإصدار {self.from_version} "
                 f"إلى {self.to_version}."]
        if self.ids_added:
            lines.append(f"• أُضيف معرّف فريد لـ {self.ids_added} إدخال.")
        if self.orphans_removed:
            lines.append(f"• حُذف {self.orphans_removed} إدخال يتيم "
                         f"(لعملاء محذوفين).")
        if self.backup_path:
            lines.append(f"\nنسخة احتياطية قبل التحديث:\n{self.backup_path}")
        return "\n".join(lines)


def run_migrations(storage) -> MigrationReport:
    """
    تشغيل الترحيلات الناقصة
    Run any pending migrations

    Args:
        storage: كائن StorageManager

    Returns:
        تقرير بما تم
    """
    current = int(storage.get_setting("schema_version", 1) or 1)

    if current >= SCHEMA_VERSION:
        return MigrationReport(
            ran=False, from_version=current, to_version=current,
            ids_added=0, orphans_removed=0, backup_path=None,
        )

    backup_path = create_backup(
        data_folder=storage.data_folder, prefix="pre-migration-v2"
    )

    ids_added, orphans_removed = _migrate_1_to_2(storage)

    storage.update_setting("schema_version", SCHEMA_VERSION)

    return MigrationReport(
        ran=True, from_version=current, to_version=SCHEMA_VERSION,
        ids_added=ids_added, orphans_removed=orphans_removed,
        backup_path=backup_path,
    )


def _migrate_1_to_2(storage) -> tuple[int, int]:
    """
    الترحيل 1 → 2: معرّف فريد لكل إدخال، وإزالة الإدخالات اليتيمة

    نقرأ السجلات كقواميس خام لا ككائنات Entry، لأن Entry.from_dict يولّد
    معرّفاً في الذاكرة فلا نعود نميّز السجل الذي كان ينقصه معرّف فعلاً.

    Returns:
        (عدد المعرّفات المضافة، عدد الأيتام المحذوفة)
    """
    records = read_jsonl(storage.entries_file)
    known_customer_ids = {c.id for c in storage.load_customers()}

    kept = []
    ids_added = 0
    orphans_removed = 0

    for record in records:
        if record.get("customer_id") not in known_customer_ids:
            orphans_removed += 1
            continue

        if not record.get("id"):
            record["id"] = new_entry_id()
            ids_added += 1

        kept.append(record)

    atomic_write_jsonl(storage.entries_file, kept)

    return ids_added, orphans_removed
```

- [ ] **Step 4: صدّر من `core/__init__.py`**

أضف بعد سطر استيراد `backup`:

```python
from .migrations import run_migrations, SCHEMA_VERSION, MigrationReport
```

وأضف إلى `__all__`:

```python
    'run_migrations',
    'SCHEMA_VERSION',
    'MigrationReport',
```

- [ ] **Step 5: شغّل واتأكد من النجاح**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrations.py -v`
Expected: PASS — ١٠ اختبارات

- [ ] **Step 6: شغّل كل الاختبارات**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: PASS — ٦٠ اختباراً تقريباً

- [ ] **Step 7: Commit**

```bash
git add core/migrations.py core/__init__.py tests/test_migrations.py
git commit -m "ترحيل: معرّفات للإدخالات القديمة وإزالة الأيتام، مع نسخة احتياطية"
```

---

## Task 7: ربط الترحيل والاستيراد الكسول ببدء التشغيل

المهمتان معاً لأنهما تعدّلان نفس مسار الإقلاع، ولا معنى لمراجعة إحداهما دون الأخرى:
الترحيل يحتاج التطبيق أن يفتح، وفتحه يحتاج الاستيراد الكسول.

**Files:**
- Modify: `main.py:38-43`
- Modify: `ui/main_window.py:15, 26, 88-91, 218-226`

**Interfaces:**
- Consumes: `run_migrations`, `MigrationReport` من Task 6
- Produces: `MainWindow(storage: Optional[StorageManager] = None)`

- [ ] **Step 1: تأكّد من فشل الحالة الحالية**

Run: `.venv/Scripts/python.exe -c "import ui.main_window"` بعد إخفاء matplotlib مؤقتاً:

```bash
.venv/Scripts/python.exe -c "
import sys
sys.modules['matplotlib'] = None
try:
    import ui.main_window
    print('استورد رغم غياب matplotlib — غير متوقع')
except Exception as e:
    print('فشل كما هو متوقع:', type(e).__name__)
"
```
Expected: يطبع فشلاً — الاستيراد الحالي غير كسول

- [ ] **Step 2: اجعل استيراد لوحة المعلومات كسولاً في `ui/main_window.py`**

احذف السطر ١٥:

```python
from .dashboard import DashboardView
```

في `setup_ui`، استبدل الأسطر ٨٧-٩١ (كتلة إنشاء لوحة المعلومات) بـ:

```python
        # لوحة المعلومات تُنشأ عند أول استخدام (استيراد كسول)
        # matplotlib ثقيل، وغيابه يجب ألا يمنع التطبيق كله من العمل
        self.dashboard_view = None
```

واستبدل `show_dashboard` (الأسطر ٢٢٣-٢٢٨) بـ:

```python
    def show_dashboard(self):
        """عرض لوحة المعلومات (تُنشأ عند أول استدعاء)"""
        if self.dashboard_view is None:
            try:
                from .dashboard import DashboardView
            except ImportError as e:
                QMessageBox.warning(
                    self, "لوحة المعلومات غير متاحة",
                    f"مكتبة الرسوم البيانية غير منصّبة.\n\n{e}\n\n"
                    "بقية التطبيق يعمل بشكل طبيعي."
                )
                return

            self.dashboard_view = DashboardView(self.storage, self)
            self.dashboard_view.back_requested.connect(self.show_customers_view)
            self.dashboard_view.customer_selected.connect(self.show_customer_ledger)
            self.stack.addWidget(self.dashboard_view)

        self.dashboard_view.refresh()
        self.stack.setCurrentWidget(self.dashboard_view)
        self.statusBar().showMessage("لوحة المعلومات - Ctrl+H للعودة للعملاء")
```

> `go_back()` في السطر ٢٢٠ يقارن `current == self.dashboard_view`. عندما تكون
> `None` تكون المقارنة `False` ببساطة — لا حاجة لتغييرها.

- [ ] **Step 3: اجعل `MainWindow` يقبل مدير تخزين جاهزاً**

استبدل بداية `MainWindow.__init__` (السطران ٢٦-٢٩):

```python
    def __init__(self, storage: StorageManager = None):
        super().__init__()

        # مدير التخزين (يُمرَّر من main.py بعد تشغيل الترحيل)
        self.storage = storage if storage is not None else StorageManager()
```

وفي `setup_ui` احذف السطر ٨١ (`self.audit_manager = AuditManager(...)`) — صار
`self.storage.audit`. واحذف استيراد `AuditManager` من السطر ١٢.

- [ ] **Step 4: اربط الترحيل في `main.py`**

استبدل الأسطر ٣٨-٤٣:

```python
    # التأكد من وجود مجلد البيانات وتشغيل أي ترحيل ناقص
    ensure_data_folder()
    storage = StorageManager()

    try:
        report = run_migrations(storage)
    except Exception as e:
        QMessageBox.critical(
            None, "فشل تحديث البيانات",
            f"تعذّر تحديث صيغة البيانات:\n\n{e}\n\n"
            "لم يُعدَّل أي ملف — بياناتك كما هي.\n"
            "راجع مجلد data/backups/ ثم أعد المحاولة."
        )
        sys.exit(1)

    if report.ran:
        QMessageBox.information(None, "تحديث البيانات", report.summary_arabic())

    # إنشاء وعرض النافذة الرئيسية
    window = MainWindow(storage)
    window.show()
```

وحدّث الاستيرادات أعلى `main.py`:

```python
from PySide6.QtWidgets import QApplication, QMessageBox
from core.utils import ensure_data_folder, get_base_path
from core.storage import StorageManager
from core.migrations import run_migrations
from ui.main_window import MainWindow
```

وحدّث رقم الإصدار في السطر ٢٣:

```python
    app.setApplicationVersion("2.1.0")
```

- [ ] **Step 5: تحقّق أن التطبيق يستورد بدون matplotlib**

```bash
.venv/Scripts/python.exe -c "
import sys, builtins
real = builtins.__import__
def fake(name, *a, **k):
    if name.startswith('matplotlib'):
        raise ImportError('No module named matplotlib')
    return real(name, *a, **k)
builtins.__import__ = fake
import ui.main_window
print('✓ استورد بنجاح رغم غياب matplotlib')
"
```
Expected: `✓ استورد بنجاح رغم غياب matplotlib`

- [ ] **Step 6: شغّل التطبيق فعلياً**

Run: `.venv/Scripts/python.exe main.py`
Expected: النافذة تفتح على قائمة العملاء. جرّب `Ctrl+D` — لوحة المعلومات تظهر.
أغلق النافذة.

- [ ] **Step 7: شغّل كل الاختبارات**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add main.py ui/main_window.py
git commit -m "إقلاع: استيراد كسول للوحة المعلومات وتشغيل الترحيل عند البدء"
```

---

## Task 8: ربط الواجهة بـ CRUD الجديد

هنا تُحذف ~٨٠ سطراً من التعامل المباشر مع الملفات في طبقة الواجهة.

**Files:**
- Modify: `ui/customer_ledger.py:668-737` (`edit_entry`)، `:739-819` (`delete_entry`)
- Modify: `ui/customers_view.py:354-390` (`edit_customer_info`)، `:392-461` (`delete_customer`)

**Interfaces:**
- Consumes: `storage.update_entry`, `storage.delete_entry`, `storage.update_customer`, `storage.delete_customer` من Tasks 4-5

- [ ] **Step 1: استبدل `edit_entry` في `ui/customer_ledger.py`**

احذف الدالة كاملةً (الأسطر ٦٦٨-٧٣٧) وضع مكانها:

```python
    def edit_entry(self, entry: Entry, row: int):
        """
        تعديل إدخال موجود
        Edit existing entry
        """
        dialog = EditEntryDialog(entry, self.customer.name, self)

        if not dialog.exec():
            return

        try:
            updated = dialog.updated_entry
            updated.id = entry.id          # الحفاظ على هوية الإدخال
            self.storage.update_entry(updated)
            self.load_data()
            QMessageBox.information(self, "نجح", "تم تعديل الإدخال بنجاح")
        except KeyError:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على الإدخال")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في تعديل الإدخال: {str(e)}")
```

> **حرج:** `EditEntryDialog.accept()` يبني `Entry` جديداً، فيحصل على معرّف جديد
> تلقائياً. سطر `updated.id = entry.id` يعيد الهوية الأصلية. بدونه يفشل التحديث
> بـ `KeyError`.

- [ ] **Step 2: استبدل `delete_entry` في `ui/customer_ledger.py`**

احذف الدالة كاملةً (من `def delete_entry` إلى نهاية الملف) وضع مكانها:

```python
    def delete_entry(self, entry: Entry):
        """
        حذف إدخال
        Delete entry
        """
        entry_type_ar = "الدين" if entry.type == "purchase" else "الدفعة"

        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من حذف {entry_type_ar}؟\n\n"
            f"المبلغ: {format_currency(entry.amount_decimal)}\n"
            f"الوصف: {entry.desc}\n"
            f"التاريخ: {format_datetime_arabic(entry.datetime)}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            self.storage.delete_entry(entry.id)
            self.load_data()
            QMessageBox.information(self, "نجح", f"تم حذف {entry_type_ar} بنجاح")
        except KeyError:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على الإدخال")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في حذف الإدخال: {str(e)}")
```

- [ ] **Step 3: نظّف استيرادات `ui/customer_ledger.py`**

`json` ما عاد مستعملاً إلا في `export_to_json` — تأكّد بـ:

```bash
grep -n "json\." ui/customer_ledger.py
```

إن ظهر `json.dump` فقط في `export_to_json`، أبقِ الاستيراد. `tempfile` و `os`
كانا يُستوردان داخل الدالتين المحذوفتين، فلا شيء لتنظيفه على مستوى الملف.

- [ ] **Step 4: استبدل `edit_customer_info` في `ui/customers_view.py`**

```python
    def edit_customer_info(self, customer_id: str):
        """
        تعديل معلومات العميل
        Edit customer information
        """
        customer = self.storage.get_customer(customer_id)
        if not customer:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على العميل")
            return

        from .dialogs import EditCustomerDialog
        dialog = EditCustomerDialog(customer, self)

        if not dialog.exec():
            return

        try:
            self.storage.update_customer(dialog.updated_customer)
            self.load_data()
            QMessageBox.information(
                self, "نجح",
                f"تم تحديث معلومات العميل '{dialog.updated_customer.name}' بنجاح"
            )
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في تحديث العميل: {str(e)}")
```

- [ ] **Step 5: استبدل `delete_customer` في `ui/customers_view.py`**

```python
    def delete_customer(self, customer_id: str, customer_name: str):
        """
        حذف العميل وجميع إدخالاته
        Delete customer and all their entries
        """
        entries_count = len(self.storage.get_customer_entries(customer_id))

        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من حذف العميل '{customer_name}'؟\n\n"
            f"سيتم حذف {entries_count} إدخال من إدخالاته أيضاً.\n"
            "سيتم إنشاء نسخة احتياطية تلقائياً قبل الحذف.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            customer, deleted_count, backup_path = self.storage.delete_customer(customer_id)
            self.load_data()
            QMessageBox.information(
                self, "نجح",
                f"تم حذف العميل '{customer.name}' و {deleted_count} إدخال.\n\n"
                f"نسخة احتياطية:\n{backup_path}"
            )
        except KeyError:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على العميل")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في حذف العميل: {str(e)}")
```

- [ ] **Step 6: تحقّق أن الملفات تُصرَّف وتُستورد**

```bash
.venv/Scripts/python.exe -m py_compile ui/customer_ledger.py ui/customers_view.py
.venv/Scripts/python.exe -c "import ui.customer_ledger, ui.customers_view; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: تحقّق أن التعامل المباشر مع الملفات اختفى من الواجهة**

```bash
grep -n "mkstemp\|os.replace" ui/*.py
```
Expected: لا نتائج

- [ ] **Step 8: فحص يدوي**

Run: `.venv/Scripts/python.exe main.py`

جرّب بالترتيب:
1. أضف عميلاً «تجربة».
2. أضف له دينين بنفس المبلغ ونفس الوصف بنفس الدقيقة.
3. كليك يمين على **الثاني** → حذف. تأكّد أن الأول هو الباقي.
4. كليك يمين على الباقي → تعديل → غيّر المبلغ. تأكّد أنه تغيّر.
5. ارجع لقائمة العملاء → كليك يمين → تعديل المعلومات → أضف هاتفاً واحفظ.
6. كليك يمين → حذف العميل. تأكّد أن الرسالة تذكر عدد الإدخالات ومسار النسخة.
7. تحقّق أن `data/audit.jsonl` أُنشئ وفيه أسطر.

- [ ] **Step 9: شغّل كل الاختبارات**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add ui/customer_ledger.py ui/customers_view.py
git commit -m "واجهة: استهلاك CRUD من StorageManager بدل التعامل المباشر مع الملفات"
```

---

## Task 9: اختبارات الملخصات والأدوات + تنظيفات ختامية

**Files:**
- Create: `tests/test_summaries.py`
- Create: `tests/test_utils.py`
- Modify: `ui/customers_view.py:119`
- Modify: `ui/customer_ledger.py:70,74,78`
- Delete: `test_basic.py`
- Modify: `PROJECT_SUMMARY.md`

**Interfaces:**
- Consumes: كل ما سبق

- [ ] **Step 1: اكتب `tests/test_summaries.py`**

```python
"""
اختبارات محرك حساب الملخصات
"""
from datetime import datetime, timedelta
from decimal import Decimal

from core.models import Customer, Entry
from core.summaries import (
    calculate_customer_summary,
    calculate_running_balances,
    recalculate_all_summaries,
)


def entry(customer_id="k_1", type_="purchase", amount="100.00", when=None) -> Entry:
    return Entry(
        customer_id=customer_id,
        type=type_,
        amount=amount,
        date=(when or datetime.now()).isoformat(),
        desc="أغراض",
        pay_method="cash",
    )


def test_balance_is_purchases_minus_payments():
    entries = [entry(amount="100.00"), entry(type_="payment", amount="40.00")]
    assert calculate_customer_summary("k_1", entries).balance_decimal == Decimal("60.00")


def test_balance_ignores_other_customers():
    entries = [entry("k_1", amount="100.00"), entry("k_2", amount="500.00")]
    assert calculate_customer_summary("k_1", entries).balance_decimal == Decimal("100.00")


def test_empty_entries_give_zero_summary():
    summary = calculate_customer_summary("k_1", [])
    assert summary.balance_decimal == Decimal("0.00")


def test_today_sales_counts_only_todays_purchases():
    entries = [
        entry(amount="100.00", when=datetime.now()),
        entry(amount="50.00", when=datetime.now() - timedelta(days=2)),
        entry(type_="payment", amount="30.00", when=datetime.now()),
    ]
    summary = calculate_customer_summary("k_1", entries)
    assert summary.today_sales_decimal == Decimal("100.00")


def test_month_sales_excludes_previous_month():
    now = datetime.now()
    last_month = (now.replace(day=1) - timedelta(days=1))
    entries = [entry(amount="100.00", when=now), entry(amount="70.00", when=last_month)]
    assert calculate_customer_summary("k_1", entries).month_sales_decimal == Decimal("100.00")


def test_running_balances_accumulate_in_order():
    entries = [
        entry(amount="100.00"),
        entry(type_="payment", amount="30.00"),
        entry(amount="50.00"),
    ]
    assert calculate_running_balances(entries) == [
        Decimal("100.00"), Decimal("70.00"), Decimal("120.00")
    ]


def test_negative_balance_when_overpaid():
    """العميل دفع أكثر مما عليه — رصيد سالب (له عندنا)"""
    entries = [entry(amount="50.00"), entry(type_="payment", amount="80.00")]
    assert calculate_customer_summary("k_1", entries).balance_decimal == Decimal("-30.00")


def test_decimal_precision_no_float_drift():
    """0.1 × 3 يجب أن تساوي 0.30 بالضبط — سبب استخدام Decimal"""
    entries = [entry(amount="0.10"), entry(amount="0.10"), entry(amount="0.10")]
    assert calculate_customer_summary("k_1", entries).balance_decimal == Decimal("0.30")


def test_recalculate_all_gives_summary_per_customer():
    customers = [Customer(id="k_1", name="خليل"), Customer(id="k_2", name="أحمد")]
    entries = [entry("k_1", amount="100.00"), entry("k_2", amount="200.00")]
    summaries = recalculate_all_summaries(customers, entries)
    assert set(summaries) == {"k_1", "k_2"}
    assert summaries["k_2"].balance_decimal == Decimal("200.00")


def test_recalculate_all_includes_customers_with_no_entries():
    customers = [Customer(id="k_1", name="خليل")]
    summaries = recalculate_all_summaries(customers, [])
    assert summaries["k_1"].balance_decimal == Decimal("0.00")
```

- [ ] **Step 2: اكتب `tests/test_utils.py`**

```python
"""
اختبارات الأدوات المساعدة
"""
from decimal import Decimal

from core.utils import (
    decimal_to_str,
    format_currency,
    hash_password,
    str_to_decimal,
    validate_customer_id,
    verify_password,
)


def test_format_currency_uses_shekel():
    assert format_currency(Decimal("1234.5")) == "1,234.50 شيكل"


def test_format_currency_zero():
    assert format_currency(Decimal("0")) == "0.00 شيكل"


def test_format_currency_negative():
    assert format_currency(Decimal("-30")) == "-30.00 شيكل"


def test_decimal_to_str_always_two_places():
    assert decimal_to_str(Decimal("5")) == "5.00"
    assert decimal_to_str(Decimal("5.126")) == "5.13"


def test_str_to_decimal_round_trip():
    assert str_to_decimal(decimal_to_str(Decimal("99.99"))) == Decimal("99.99")


def test_password_verifies():
    assert verify_password("سر123", hash_password("سر123"))


def test_password_rejects_wrong():
    assert not verify_password("غلط", hash_password("سر123"))


def test_password_hash_is_not_plaintext():
    assert "سر123" not in hash_password("سر123")


def test_validate_customer_id_accepts_arabic():
    """أسماء العملاء عربية، و str.isalnum() ترجع True للحروف العربية"""
    assert validate_customer_id("خليل_9518")


def test_validate_customer_id_accepts_latin_with_separators():
    assert validate_customer_id("ahmad_mahmoud-1234")


def test_validate_customer_id_rejects_empty():
    assert not validate_customer_id("")


def test_validate_customer_id_rejects_spaces():
    assert not validate_customer_id("خليل بركات")
```

- [ ] **Step 3: شغّل الاختبارين وتأكّد من النجاح**

Run: `.venv/Scripts/python.exe -m pytest tests/test_summaries.py tests/test_utils.py -v`
Expected: PASS — ٢٢ اختباراً

> إن فشل `test_format_currency_negative`، تحقّق من ناتج
> `f"{Decimal('-30'):,.2f}"` وعدّل التوقّع في الاختبار ليطابق السلوك الفعلي —
> لا تغيّر `format_currency` نفسها.

- [ ] **Step 4: أصلح بقايا عملة «ج.م»**

في `ui/customers_view.py` السطر ١١٩:

```python
        self.total_debt_label = QLabel(f"إجمالي الديون: {format_currency(Decimal('0'))}")
```

في `ui/customer_ledger.py` الأسطر ٧٠ و ٧٤ و ٧٨ — استبدل `"0.00 ج.م"` في
الاستدعاءات الثلاثة بـ `format_currency(Decimal("0"))`:

```python
        self.balance_box = self.create_summary_card("الرصيد الحالي", format_currency(Decimal("0")))
        ...
        self.today_sales_box = self.create_summary_card("مبيعات اليوم", format_currency(Decimal("0")))
        ...
        self.month_sales_box = self.create_summary_card("مبيعات الشهر", format_currency(Decimal("0")))
```

- [ ] **Step 5: تحقّق أن «ج.م» اختفت**

```bash
grep -rn "ج\.م" core/ ui/ main.py
```
Expected: لا نتائج

- [ ] **Step 6: احذف `test_basic.py`**

تغطيته صارت كاملةً في `tests/test_models.py` و `tests/test_summaries.py`.

```bash
rm test_basic.py
```

- [ ] **Step 7: حدّث `PROJECT_SUMMARY.md`**

في قسم «نماذج البيانات» أضف `id` إلى `Entry`:

```python
@dataclass
class Entry:
    id: str              # معرّف فريد (uuid) — يُولَّد تلقائياً
    customer_id: str     # معرف العميل
    ...
```

في «المكتبات والاعتماديات» احذف سطري `arabic-reshaper` و `python-bidi`.

في «هيكل المشروع» أضف تحت `core/`:

```
│   ├── migrations.py          # ترحيل صيغة البيانات
```

وأضف `tests/` بعد `data/`:

```
├── tests/                     # اختبارات pytest
```

في «ملفات البيانات» أضف صفاً:

| `data/audit.jsonl` | JSONL | سجل التدقيق — كل إنشاء/تعديل/حذف |

- [ ] **Step 8: شغّل كل الاختبارات**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: PASS — ~٨٠ اختباراً، لا فشل

- [ ] **Step 9: شغّل التطبيق للتأكيد الأخير**

Run: `.venv/Scripts/python.exe main.py`
Expected: يفتح، والبطاقات تعرض «0.00 شيكل» لا «0.00 ج.م»

- [ ] **Step 10: Commit**

```bash
git add tests/ ui/customers_view.py ui/customer_ledger.py PROJECT_SUMMARY.md
git rm test_basic.py
git commit -m "اختبارات: تغطية الملخصات والأدوات، وإزالة بقايا عملة ج.م"
```

---

## معايير القبول للمرحلة ١

قبل الانتقال للمرحلة ٢، كل بند لازم يتحقق:

- [ ] `.venv/Scripts/python.exe -m pytest` — كل الاختبارات تنجح
- [ ] `.venv/Scripts/python.exe main.py` — التطبيق يفتح
- [ ] `Ctrl+D` يفتح لوحة المعلومات
- [ ] `grep -rn "mkstemp\|os.replace" ui/` — لا نتائج (لا ملفات في الواجهة)
- [ ] `grep -rn "ج\.م" core/ ui/ main.py` — لا نتائج
- [ ] إدخالان متطابقان: حذف الثاني يبقي الأول
- [ ] حذف عميل يحذف إدخالاته ويعرض مسار نسخة احتياطية
- [ ] `data/audit.jsonl` موجود وفيه سجلات
- [ ] الترحيل يعمل مرتين متتاليتين دون تغيير في المرة الثانية
- [ ] `git status` نظيف

## قبل النشر على جهاز المحل

**لا تنسخ exe جديداً قبل هذا الاختبار:**

1. انسخ مجلد `data/` الحقيقي من جهاز المحل إلى مجلد تجريبي.
2. شغّل التطبيق عليه وتأكّد أن الترحيل نجح.
3. **قارن الأرصدة قبل وبعد** — لكل عميل، الرصيد يجب أن يكون مطابقاً تماماً.
4. عندها فقط انسخ exe الجديد، بعد نسخة احتياطية يدوية لمجلد `data/`.
