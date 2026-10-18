"""
نقطة البداية للتطبيق
Main entry point for the debt management application
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from core.utils import get_base_path
from core.storage import StorageManager
from core.migrations import run_migrations
from core.updater import cleanup_old_exe
from core.version import __version__
from core.integrity import (
    check_data_files, disabled_sections, has_critical_problem, summary_arabic
)
from ui.main_window import MainWindow


def handle_data_problems(problems, storage) -> bool:
    """
    إبلاغ المستخدم بملفات تالفة، وعرض الاستعادة من نسخة احتياطية
    Report unreadable files and offer restoring from a backup

    Returns:
        True إن جاز متابعة التشغيل، False إن وجب الخروج
    """
    from ui.restore_dialog import RestoreBackupDialog

    critical = has_critical_problem(problems)
    body = summary_arabic(problems)

    box = QMessageBox()
    box.setIcon(QMessageBox.Critical if critical else QMessageBox.Warning)
    box.setWindowTitle("مشكلة في ملفات البيانات")
    box.setText(body)
    box.setDetailedText("\n\n".join(f"{p.filename}\n{p.detail}" for p in problems))

    restore_btn = box.addButton("استعادة نسخة احتياطية", QMessageBox.AcceptRole)
    if critical:
        box.addButton("خروج", QMessageBox.RejectRole)
    else:
        box.addButton("متابعة بدون هذه الشاشات", QMessageBox.RejectRole)

    box.exec()

    if box.clickedButton() is restore_btn:
        if RestoreBackupDialog(storage).exec():
            QMessageBox.information(
                None, "تمت الاستعادة",
                "تمت استعادة البيانات.\nأغلق البرنامج وافتحه من جديد.")
        return False      # إعادة التشغيل مطلوبة في الحالتين

    return not critical


def main():
    """
    الدالة الرئيسية
    Main function
    """
    # إنشاء التطبيق
    app = QApplication(sys.argv)

    # تعيين الاسم والنسخة
    app.setApplicationName("إدارة ديون العملاء")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("محل الخضار والفواكه")

    # تعيين الاتجاه من اليمين إلى اليسار (RTL)
    app.setLayoutDirection(Qt.RightToLeft)

    # تعيين الخط الافتراضي
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # تعيين أيقونة التطبيق
    icon_path = get_base_path() / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # حذف نسخة الإصدار السابق المتبقّية من تحديث ناجح.
    # وصولنا إلى هنا دليلٌ على أن الإصدار الجديد أقلع فعلاً.
    if getattr(sys, "frozen", False):
        cleanup_old_exe(Path(sys.executable))

    # تهيئة التخزين (تُنشئ مجلد البيانات وملفاته إن لم تكن موجودة)
    storage = StorageManager()

    # تشغيل أي ترحيل ناقص قبل فتح الواجهة، حتى لا تعمل على ملف نصف مرحَّل
    try:
        report = run_migrations(storage)
    except Exception as e:
        QMessageBox.critical(
            None, "فشل تحديث البيانات",
            f"تعذّر تحديث صيغة البيانات:\n\n{e}\n\n"
            "لم تُعدَّل ملفاتك — الكتابة ذرّية، ففشلها يترك الأصل سليماً.\n"
            "راجع مجلد data/backups/ ثم أعد المحاولة."
        )
        sys.exit(1)

    if report.ran and (report.total_ids_added or report.total_orphans_removed):
        QMessageBox.information(None, "تحديث البيانات", report.summary_arabic())

    # فحص سلامة الملفات قبل بناء الواجهة.
    # بدونه كان ملف واحد تالف يُسقط التطبيق كله برسالة إنجليزية.
    problems = check_data_files(storage)
    if problems and not handle_data_problems(problems, storage):
        sys.exit(1)

    # إنشاء وعرض النافذة الرئيسية
    window = MainWindow(storage, disabled=disabled_sections(problems))
    window.show()

    # فحص التحديثات في الخلفية — بعد ظهور النافذة، فلا يؤخّر الإقلاع
    window.start_update_check()

    # تشغيل التطبيق
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
