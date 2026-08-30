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
from ui.main_window import MainWindow


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

    # إنشاء وعرض النافذة الرئيسية
    window = MainWindow(storage)
    window.show()

    # فحص التحديثات في الخلفية — بعد ظهور النافذة، فلا يؤخّر الإقلاع
    window.start_update_check()

    # تشغيل التطبيق
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
