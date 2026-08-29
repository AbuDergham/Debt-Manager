"""
نقطة البداية للتطبيق
Main entry point for the debt management application
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from core.utils import ensure_data_folder, get_base_path
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
    app.setApplicationVersion("2.0.0")
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
    
    # التأكد من وجود مجلد البيانات
    ensure_data_folder()
    
    # إنشاء وعرض النافذة الرئيسية
    window = MainWindow()
    window.show()
    
    # تشغيل التطبيق
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
