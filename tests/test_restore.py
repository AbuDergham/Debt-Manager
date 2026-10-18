"""
استعادة النسخ الاحتياطية

كانت `restore_backup` و `list_backups` مكتوبتين في core ومقطوعتين عن
الواجهة تماماً. فلمّا تلف ملف في المحل، لم يكن أمام صاحبه أي زر يضغطه.
"""
import zipfile

import pytest

from conftest import make_customer, make_entry, make_supplier
from core.backup import create_backup, list_backups, restore_backup
from core.utils import DATA_FILES


def test_restore_brings_back_deleted_customer(storage, data_folder):
    """
    السيناريو الفعلي: حُذف عميل ومعه حركاته، والنسخة قبل الحذف موجودة.
    """
    storage.add_customer(make_customer("ahmad", "أحمد"))
    storage.add_entry(make_entry("ahmad", amount="250.00"))
    storage.add_entry(make_entry("ahmad", amount="130.00"))

    customer, deleted, backup_path = storage.delete_customer("ahmad")
    assert deleted == 2 and storage.get_customer("ahmad") is None

    restore_backup(backup_path, data_folder=data_folder)

    assert storage.get_customer("ahmad").name == "أحمد"
    assert len(storage.get_customer_entries("ahmad")) == 2


def test_restore_returns_restored_filenames(storage, data_folder):
    storage.add_customer(make_customer())
    path = create_backup(data_folder=data_folder)

    restored = restore_backup(path, data_folder=data_folder)

    assert "customers.json" in restored
    assert set(restored) <= {f for f, _ in DATA_FILES.values()}


def test_restore_overwrites_current_data(storage, data_folder):
    storage.add_customer(make_customer("c1", "خليل"))
    path = create_backup(data_folder=data_folder)

    storage.add_customer(make_customer("c2", "أحمد"))
    assert len(storage.load_customers()) == 2

    restore_backup(path, data_folder=data_folder)

    assert [c.name for c in storage.load_customers()] == ["خليل"]


def test_restore_rejects_missing_file(data_folder):
    with pytest.raises(FileNotFoundError):
        restore_backup(data_folder / "nope.zip", data_folder=data_folder)


# ---------- تحصين الاستخراج ----------

def test_restore_ignores_paths_outside_data_folder(storage, data_folder, tmp_path):
    """
    `extractall` على أرشيف أياً كان مصدره يسمح بمسارات تخرج من المجلد.
    القائمة البيضاء تمنع كتابة أي شيء خارج مجلد البيانات.
    """
    evil = data_folder / "backups" / "evil.zip"
    evil.parent.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "pwned.txt"

    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../../pwned.txt", "اخترقتك")
        z.writestr("customers.json", '[{"id": "c1", "name": "خليل"}]')

    restored = restore_backup(evil, data_folder=data_folder)

    assert not outside.exists(), "كُتب ملف خارج مجلد البيانات"
    assert restored == ["customers.json"]


def test_restore_ignores_unknown_files(storage, data_folder):
    """ملف غريب داخل الأرشيف لا يُستخرج"""
    path = data_folder / "backups" / "mixed.zip"
    path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("customers.json", "[]")
        z.writestr("malware.exe", "MZ")

    restored = restore_backup(path, data_folder=data_folder)

    assert restored == ["customers.json"]
    assert not (data_folder / "malware.exe").exists()


def test_restore_strips_directory_prefix(storage, data_folder):
    """أرشيف فيه مجلد داخلي: يُستخرج الاسم المجرّد"""
    path = data_folder / "backups" / "nested.zip"
    path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w") as z:
        z.writestr("data/customers.json", '[{"id": "c1", "name": "خليل"}]')

    restore_backup(path, data_folder=data_folder)

    assert storage.load_customers()[0].name == "خليل"


# ---------- سرد النسخ ----------

def test_list_backups_newest_first(storage, data_folder):
    import time
    for prefix in ("backup", "pre-delete", "pre-migration-v2"):
        create_backup(data_folder=data_folder, prefix=prefix)
        time.sleep(0.01)

    found = list_backups(backup_folder=data_folder / "backups")

    assert len(found) == 3
    assert found[0].name.startswith("pre-migration-v2")   # الأحدث


def test_list_backups_empty_when_none(data_folder):
    assert list_backups(backup_folder=data_folder / "backups") == []


def test_backup_info_describes_contents(storage, data_folder):
    from core.backup import get_backup_info

    storage.add_customer(make_customer())
    storage.add_supplier(make_supplier())
    path = create_backup(data_folder=data_folder)

    info = get_backup_info(path)

    assert info["name"] == path.name
    assert "customers.json" in info["files"]
    assert "suppliers.json" in info["files"]
    assert info["size"] > 0


# ---------- الاستعادة تُنشئ شبكة أمان ----------

def test_restore_after_corruption_recovers_the_shop(storage, data_folder):
    """
    إعادة إنتاج الحادثة كاملةً: بيانات سليمة -> نسخة -> تلف -> استعادة.
    """
    storage.add_customer(make_customer("c1", "خليل بركات"))
    storage.add_entry(make_entry("c1", amount="500.00"))
    good = create_backup(data_folder=data_folder)

    # محرّر خارجي يفسد الملف فساداً حقيقياً (لا BOM فقط)
    storage.checks_file.write_bytes(b"{ this is broken")

    from core.integrity import check_data_files
    assert check_data_files(storage), "التلف لم يُكتشف"

    restore_backup(good, data_folder=data_folder)

    assert check_data_files(storage) == []
    assert storage.get_customer("c1").name == "خليل بركات"
    assert len(storage.get_customer_entries("c1")) == 1
