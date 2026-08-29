"""
عزل الاختبارات عن بيانات الإنتاج، وسلامة طبقة الملفات الأساسية

التطبيق يعمل على بيانات محل حقيقية. هذه الاختبارات تحرس الحدّ الفاصل.
"""
import json
import zipfile

from conftest import make_customer, make_entry, make_supplier

from core.backup import create_backup, export_all_data, list_backups
from core.utils import DATA_FILES, ensure_data_folder, get_data_folder


# ---------- العزل ----------

def test_storage_uses_injected_folder(storage, data_folder):
    """مدير التخزين يستخدم المجلد المحقون، لا المسار العام"""
    assert storage.data_folder == data_folder
    assert storage.entries_file == data_folder / "entries.jsonl"


def test_storage_folder_is_not_production(storage):
    """المجلد المستخدم في الاختبار ليس مجلد البيانات الحقيقي"""
    assert storage.data_folder.resolve() != get_data_folder().resolve()


def test_writing_does_not_touch_production(storage, data_folder):
    """كتابة فعلية تذهب إلى المجلد المؤقت وحده"""
    storage.add_customer(make_customer())
    written = json.loads((data_folder / "customers.json").read_text(encoding="utf-8"))
    assert written[0]["name"] == "أحمد"


# ---------- إنشاء الملفات الأساسية ----------

def test_all_data_files_created(storage, data_folder):
    """كل ملف في DATA_FILES يُنشأ بمحتواه الابتدائي"""
    for filename, initial in DATA_FILES.values():
        path = data_folder / filename
        assert path.exists(), f"لم يُنشأ {filename}"
        assert path.read_text(encoding="utf-8") == initial


def test_backups_folder_created(data_folder, storage):
    assert (data_folder / "backups").is_dir()


def test_ensure_data_folder_is_idempotent(tmp_path):
    """استدعاؤها مرتين لا يمحو بيانات موجودة"""
    folder = ensure_data_folder(tmp_path / "d")
    (folder / "customers.json").write_text('[{"id":"x","name":"خليل"}]', encoding="utf-8")

    ensure_data_folder(folder)

    assert "خليل" in (folder / "customers.json").read_text(encoding="utf-8")


def test_ensure_data_folder_creates_nested_path(tmp_path):
    """ينشئ المجلدات الأب إن لزم"""
    folder = ensure_data_folder(tmp_path / "a" / "b" / "data")
    assert folder.is_dir()


def test_storage_exposes_a_path_for_every_data_file(storage):
    """كل ملف في DATA_FILES له سمة مسار على مدير التخزين"""
    exposed = {
        p.name for name, p in vars(storage).items()
        if name.endswith("_file")
    }
    expected = {filename for filename, _ in DATA_FILES.values()}
    assert expected <= exposed, f"مسارات ناقصة: {expected - exposed}"


# ---------- النسخ الاحتياطي ----------

def test_backup_includes_every_data_file(storage, data_folder):
    """
    النسخة الاحتياطية تشمل ملفات الموردين والشيكات والفواتير، لا العملاء فقط.
    """
    storage.add_customer(make_customer())
    storage.add_supplier(make_supplier())

    backup_path = create_backup(data_folder=data_folder)

    with zipfile.ZipFile(backup_path) as z:
        archived = set(z.namelist())
    expected = {filename for filename, _ in DATA_FILES.values()}
    assert expected <= archived, f"ملفات مفقودة من النسخة: {expected - archived}"


def test_backup_prefix_is_used(storage, data_folder):
    backup_path = create_backup(data_folder=data_folder, prefix="pre-migration-v2")
    assert backup_path.name.startswith("pre-migration-v2_")
    assert backup_path.suffix == ".zip"


def test_backup_captures_current_content(storage, data_folder):
    storage.add_customer(make_customer(name="خليل بركات"))
    backup_path = create_backup(data_folder=data_folder)
    with zipfile.ZipFile(backup_path) as z:
        assert "خليل بركات" in z.read("customers.json").decode("utf-8")


def test_list_backups_finds_non_default_prefixes(storage, data_folder):
    """
    النسخ التلقائية تأخذ بادئات مثل pre-migration-v2 و pre-delete،
    فيجب ألا يقتصر البحث على backup_*.
    """
    create_backup(data_folder=data_folder, prefix="backup")
    create_backup(data_folder=data_folder, prefix="pre-migration-v2")
    create_backup(data_folder=data_folder, prefix="pre-delete")

    found = list_backups(backup_folder=data_folder / "backups")

    assert len(found) == 3
    assert {p.name.split("_")[0] for p in found} == {"backup", "pre-migration-v2", "pre-delete"}


def test_export_all_data_to_folder_includes_supplier_files(storage, data_folder, tmp_path, monkeypatch):
    """
    «تصدير جميع البيانات» كان يصدّر 4 ملفات فقط، فيُسقط الموردين
    وفواتير الشراء والدفعات والشيكات بصمت.
    """
    monkeypatch.setattr("core.backup.get_data_folder", lambda: data_folder)
    storage.add_customer(make_customer())
    storage.add_supplier(make_supplier())

    out = export_all_data(tmp_path / "export")

    exported = {p.name for p in out.iterdir()}
    expected = {filename for filename, _ in DATA_FILES.values()}
    assert expected <= exported, f"ملفات مفقودة من التصدير: {expected - exported}"
