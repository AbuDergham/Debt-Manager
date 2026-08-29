"""
ترحيل صيغة البيانات
Data schema migrations

كل ترحيل يلتزم بثلاثة شروط:
  - قابل للتكرار (idempotent): تشغيله مرتين آمن، والثانية لا تفعل شيئاً
  - ينشئ نسخة احتياطية قبل أي كتابة
  - يكتب كتابةً ذرّية، ففشله في المنتصف يترك الملفات الأصلية سليمة

هذا الكود يعمل على بيانات محل حقيقية. لا تخفّف أياً من الشروط الثلاثة.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .backup import create_backup
from .models import new_id
from .storage import atomic_write_jsonl, read_jsonl

# النسخة الحالية لصيغة البيانات
SCHEMA_VERSION = 2


@dataclass
class MigrationReport:
    """تقرير عمّا فعله الترحيل - Report of what the migration did"""
    ran: bool
    from_version: int
    to_version: int
    entry_ids_added: int = 0
    item_ids_added: int = 0
    orphan_entries_removed: int = 0
    orphan_items_removed: int = 0
    orphan_payments_removed: int = 0
    backup_path: Optional[Path] = None

    @property
    def total_ids_added(self) -> int:
        return self.entry_ids_added + self.item_ids_added

    @property
    def total_orphans_removed(self) -> int:
        return (self.orphan_entries_removed
                + self.orphan_items_removed
                + self.orphan_payments_removed)

    def summary_arabic(self) -> str:
        """نص عربي جاهز للعرض في رسالة للمستخدم"""
        if not self.ran:
            return "البيانات محدّثة — لا حاجة لأي ترحيل."

        lines: List[str] = [
            f"تم تحديث صيغة البيانات من الإصدار {self.from_version} "
            f"إلى {self.to_version}."
        ]

        if self.entry_ids_added:
            lines.append(f"• أُضيف معرّف فريد لـ {self.entry_ids_added} حركة عميل.")
        if self.item_ids_added:
            lines.append(f"• أُضيف معرّف فريد لـ {self.item_ids_added} بند شراء.")
        if self.orphan_entries_removed:
            lines.append(f"• حُذفت {self.orphan_entries_removed} حركة يتيمة "
                         "(لعملاء محذوفين).")
        if self.orphan_items_removed:
            lines.append(f"• حُذف {self.orphan_items_removed} بند شراء يتيم "
                         "(لموردين محذوفين).")
        if self.orphan_payments_removed:
            lines.append(f"• حُذفت {self.orphan_payments_removed} دفعة يتيمة "
                         "(لموردين محذوفين).")

        if not self.total_ids_added and not self.total_orphans_removed:
            lines.append("• لم تكن هناك سجلات تحتاج تعديلاً.")

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
        return MigrationReport(ran=False, from_version=current, to_version=current)

    backup_path = create_backup(
        data_folder=storage.data_folder, prefix="pre-migration-v2"
    )

    report = _migrate_1_to_2(storage)
    report.from_version = current
    report.backup_path = backup_path

    storage.update_setting("schema_version", SCHEMA_VERSION)

    return report


def _migrate_1_to_2(storage) -> MigrationReport:
    """
    الترحيل 1 → 2

    1. معرّف فريد لكل حركة عميل ولكل بند شراء
    2. إزالة السجلات اليتيمة (لعملاء أو موردين محذوفين)

    نقرأ السجلات كقواميس خام لا ككائنات، لأن `from_dict` يولّد معرّفاً في
    الذاكرة فلا نعود نميّز السجل الذي كان ينقصه معرّف فعلاً.
    """
    report = MigrationReport(ran=True, from_version=1, to_version=SCHEMA_VERSION)

    known_customers = {c.id for c in storage.load_customers()}
    known_suppliers = {s.id for s in storage.load_suppliers()}

    # --- حركات العملاء ---
    kept = []
    for record in read_jsonl(storage.entries_file):
        if record.get("customer_id") not in known_customers:
            report.orphan_entries_removed += 1
            continue
        if not record.get("id"):
            record["id"] = new_id()
            report.entry_ids_added += 1
        kept.append(record)
    atomic_write_jsonl(storage.entries_file, kept)

    # --- بنود الشراء ---
    kept = []
    for record in read_jsonl(storage.purchase_items_file):
        if record.get("supplier_id") not in known_suppliers:
            report.orphan_items_removed += 1
            continue
        if not record.get("id"):
            record["id"] = new_id()
            report.item_ids_added += 1
        kept.append(record)
    atomic_write_jsonl(storage.purchase_items_file, kept)

    # --- دفعات الموردين (لها معرّف أصلاً، اليتيمة فقط) ---
    kept = []
    for record in read_jsonl(storage.supplier_payments_file):
        if record.get("supplier_id") not in known_suppliers:
            report.orphan_payments_removed += 1
            continue
        kept.append(record)
    atomic_write_jsonl(storage.supplier_payments_file, kept)

    return report
