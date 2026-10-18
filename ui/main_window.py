"""
النافذة الرئيسية للتطبيق
Main application window
"""
from PySide6.QtWidgets import (
    QMainWindow, QStackedWidget, QMessageBox, QInputDialog
)
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from core.storage import StorageManager
from core.backup import create_backup, AutoBackupManager
from core.utils import hash_password, verify_password
from core.version import __version__
from .customers_view import CustomersView
from .customer_ledger import CustomerLedgerView
from .dialogs import AppLockDialog
from .suppliers_view import SuppliersView
from .supplier_ledger import SupplierLedgerView
from .purchase_order_view import PurchaseOrderView
from .checks_view import ChecksView


class MainWindow(QMainWindow):
    """
    النافذة الرئيسية
    Main application window
    """
    
    def __init__(self, storage: StorageManager = None, disabled=None):
        super().__init__()

        # مدير التخزين — يمرَّر من main.py بعد تشغيل الترحيل
        self.storage = storage if storage is not None else StorageManager()

        # أقسام مُعطَّلة بسبب ملفات بيانات تالفة (من core.integrity).
        # تعمل بقية الشاشات بشكل طبيعي، مع تحذير ظاهر لا تعطيل صامت.
        self.disabled_sections = set(disabled or ())
        
        # مدير النسخ الاحتياطي التلقائي
        auto_backup_interval = self.storage.get_setting("auto_backup_interval", 200)
        self.backup_manager = AutoBackupManager(interval=auto_backup_interval)
        
        # التحقق من قفل التطبيق
        if not self.check_app_lock():
            self.close()
            return
        
        # إعداد النافذة
        self.setWindowTitle("إدارة ديون العملاء - نظام محل الخضار والفواكه")
        self.setGeometry(100, 100, 1200, 800)
        
        # إعداد الواجهة
        self.setup_ui()
        self.setup_menu()
        
        # تعطيل أقسام ملفاتها تالفة (يحتاج القوائم مبنيّة)
        self.apply_disabled_sections()

        # تطبيق الTheme
        self.apply_theme()
        
        # عرض صفحة العملاء
        self.show_customers_view()
    
    def check_app_lock(self) -> bool:
        """
        التحقق من قفل التطبيق
        Check app lock
        
        Returns:
            True إذا تم فتح القفل بنجاح أو لا يوجد قفل
        """
        password_hash = self.storage.get_setting("password_hash")
        
        if password_hash:
            # يوجد قفل، طلب كلمة المرور
            dialog = AppLockDialog(mode="verify", parent=self)
            if dialog.exec():
                if verify_password(dialog.password, password_hash):
                    return True
                else:
                    QMessageBox.warning(self, "خطأ", "كلمة مرور خاطئة")
                    return False
            else:
                return False
        
        return True
    
    def setup_ui(self):
        """إعداد الواجهة"""
        # الويدجت المركزي (Stack Widget للتبديل بين الصفحات)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # لوحة المعلومات تُنشأ عند أول استخدام (استيراد كسول).
        # matplotlib ثقيل، وغيابه يجب ألا يمنع التطبيق كله من العمل.
        self.dashboard_view = None
        
        # صفحة قائمة العملاء
        self.customers_view = CustomersView(self.storage, self)
        self.customers_view.customer_selected.connect(self.show_customer_ledger)
        self.stack.addWidget(self.customers_view)
        
        # صفحة دفتر العميل
        self.ledger_view = CustomerLedgerView(self.storage, self)
        self.ledger_view.back_requested.connect(self.show_customers_view)
        self.stack.addWidget(self.ledger_view)
        
        # صفحة حساب المورد (تُنشأ ديناميكياً)
        self.supplier_ledger_view = None

        # شاشات الموردين لا تُبنى أصلاً إن كان ملف من ملفاتها تالفاً:
        # بنّاؤها يقرأ الملف فينهار، فحارس التنقّل وحده لا يكفي.
        if "suppliers" in self.disabled_sections:
            self.suppliers_view = None
            self.purchase_order_view = None
            self.checks_view = None
        else:
            # صفحة قائمة الموردين
            self.suppliers_view = SuppliersView(self.storage, self)
            self.suppliers_view.supplier_selected.connect(self.show_supplier_ledger)
            self.suppliers_view.back_requested.connect(self.show_customers_view)
            self.stack.addWidget(self.suppliers_view)

            # صفحة فواتير الشراء
            self.purchase_order_view = PurchaseOrderView(self.storage, self)
            self.purchase_order_view.back_requested.connect(self.show_customers_view)
            self.stack.addWidget(self.purchase_order_view)

            # صفحة الشيكات
            self.checks_view = ChecksView(self.storage, self)
            self.checks_view.back_requested.connect(self.show_customers_view)
            self.stack.addWidget(self.checks_view)
        
        # شريط الحالة
        self.statusBar().showMessage("جاهز")
        
        # إعداد اختصارات لوحة المفاتيح
        self.setup_shortcuts()
    
    def setup_menu(self):
        """إعداد شريط القوائم"""
        menubar = self.menuBar()
        
        # قائمة ملف
        file_menu = menubar.addMenu("ملف")
        
        # نسخ احتياطي
        backup_action = QAction("إنشاء نسخة احتياطية", self)
        backup_action.triggered.connect(self.create_manual_backup)
        file_menu.addAction(backup_action)

        # استعادة نسخة احتياطية
        restore_action = QAction("♻️ استعادة نسخة احتياطية", self)
        restore_action.triggered.connect(self.restore_backup_dialog)
        file_menu.addAction(restore_action)


        # تصدير جميع البيانات
        export_action = QAction("تصدير جميع البيانات", self)
        export_action.triggered.connect(self.export_all_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # خروج
        exit_action = QAction("خروج", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # قائمة العرض (جديدة)
        view_menu = menubar.addMenu("عرض")
        
        # لوحة المعلومات
        dashboard_action = QAction("📊 لوحة المعلومات", self)
        dashboard_action.setShortcut(QKeySequence("Ctrl+D"))
        dashboard_action.triggered.connect(self.show_dashboard)
        view_menu.addAction(dashboard_action)
        
        # قائمة العملاء
        customers_action = QAction("👥 قائمة العملاء", self)
        customers_action.setShortcut(QKeySequence("Ctrl+H"))
        customers_action.triggered.connect(self.show_customers_view)
        view_menu.addAction(customers_action)
        
        view_menu.addSeparator()
        
        # الموردون
        self.suppliers_action = suppliers_action = QAction("🏭 الموردون", self)
        suppliers_action.setShortcut(QKeySequence("Ctrl+M"))
        suppliers_action.triggered.connect(self.show_suppliers_view)
        view_menu.addAction(suppliers_action)
        
        # فواتير الشراء
        self.purchases_action = purchases_action = QAction("🧾 فواتير الشراء", self)
        purchases_action.setShortcut(QKeySequence("Ctrl+P"))
        purchases_action.triggered.connect(self.show_purchase_orders)
        view_menu.addAction(purchases_action)
        
        # الشيكات
        self.checks_action = checks_action = QAction("💳 الشيكات", self)
        checks_action.setShortcut(QKeySequence("Ctrl+K"))
        checks_action.triggered.connect(self.show_checks)
        view_menu.addAction(checks_action)
        
        # قائمة الإعدادات
        settings_menu = menubar.addMenu("الإعدادات")

        # معلومات المحل — تظهر في ترويسة المطبوعات
        shop_action = QAction("🏪 معلومات المحل", self)
        shop_action.triggered.connect(self.configure_shop_info)
        settings_menu.addAction(shop_action)

        settings_menu.addSeparator()

        # تبديل الTheme
        theme_action = QAction("تبديل الوضع (فاتح/داكن)", self)
        theme_action.triggered.connect(self.toggle_theme)
        settings_menu.addAction(theme_action)
        
        settings_menu.addSeparator()
        
        # تفعيل/إلغاء قفل التطبيق
        lock_action = QAction("تفعيل قفل التطبيق", self)
        lock_action.triggered.connect(self.setup_app_lock)
        settings_menu.addAction(lock_action)
        
        unlock_action = QAction("إلغاء قفل التطبيق", self)
        unlock_action.triggered.connect(self.remove_app_lock)
        settings_menu.addAction(unlock_action)
        
        settings_menu.addSeparator()
        
        # إعدادات النسخ الاحتياطي
        backup_settings_action = QAction("إعدادات النسخ الاحتياطي", self)
        backup_settings_action.triggered.connect(self.configure_backup)
        settings_menu.addAction(backup_settings_action)
        
        # قائمة المساعدة
        help_menu = menubar.addMenu("مساعدة")

        # التحقق من التحديثات — يصير مميّزاً عند توفّر إصدار جديد
        self.update_action = QAction("🔄 التحقق من التحديثات", self)
        self.update_action.triggered.connect(self.check_for_updates_manually)
        help_menu.addAction(self.update_action)

        help_menu.addSeparator()

        # حول
        about_action = QAction("حول التطبيق", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_shortcuts(self):
        """إعداد اختصارات لوحة المفاتيح"""
        # Ctrl+D - لوحة المعلومات
        QShortcut(QKeySequence("Ctrl+D"), self, self.show_dashboard)
        
        # Ctrl+H - قائمة العملاء (Home)
        QShortcut(QKeySequence("Ctrl+H"), self, self.show_customers_view)
        
        # Ctrl+N - إضافة عميل جديد
        QShortcut(QKeySequence("Ctrl+N"), self, self.add_new_customer)
        
        # Ctrl+F - البحث الشامل
        QShortcut(QKeySequence("Ctrl+F"), self, self.show_search_dialog)
        
        # Ctrl+M - الموردون
        QShortcut(QKeySequence("Ctrl+M"), self, self.show_suppliers_view)
        
        # Ctrl+P - فواتير الشراء
        QShortcut(QKeySequence("Ctrl+P"), self, self.show_purchase_orders)
        
        # Ctrl+K - الشيكات
        QShortcut(QKeySequence("Ctrl+K"), self, self.show_checks)
        
        # Escape - رجوع
        QShortcut(QKeySequence("Escape"), self, self.go_back)
    
    def show_search_dialog(self):
        """عرض نافذة البحث الشامل"""
        from .search_dialog import SearchDialog
        dialog = SearchDialog(self.storage, self)
        dialog.entry_selected.connect(self.navigate_to_entry)
        dialog.exec()
    
    def navigate_to_entry(self, customer_id: str, entry_date: str):
        """الانتقال إلى إدخال محدد"""
        self.show_customer_ledger(customer_id)
    
    def add_new_customer(self):
        """إضافة عميل جديد"""
        self.show_customers_view()
        self.customers_view.add_customer()
    
    def go_back(self):
        """رجوع للصفحة السابقة"""
        current = self.stack.currentWidget()
        if current == self.ledger_view:
            self.show_customers_view()
        elif current == self.dashboard_view:
            self.show_customers_view()
        elif current == self.suppliers_view:
            self.show_customers_view()
        elif current == self.supplier_ledger_view:
            self.show_suppliers_view()
        elif current == self.purchase_order_view:
            self.show_customers_view()
        elif current == self.checks_view:
            self.show_customers_view()
    
    def show_dashboard(self):
        """عرض لوحة المعلومات (تُنشأ عند أول استدعاء)"""
        if self.dashboard_view is None:
            try:
                from .dashboard import DashboardView
            except ImportError as e:
                QMessageBox.warning(
                    self, "لوحة المعلومات غير متاحة",
                    "مكتبة الرسوم البيانية غير منصّبة.\n\n"
                    f"{e}\n\n"
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
    
    def show_customers_view(self):
        """عرض صفحة قائمة العملاء"""
        self.customers_view.refresh()
        self.stack.setCurrentWidget(self.customers_view)
        self.statusBar().showMessage("قائمة العملاء")
    
    def show_customer_ledger(self, customer_id: str):
        """عرض صفحة دفتر العميل"""
        self.ledger_view.set_customer(customer_id)
        self.stack.setCurrentWidget(self.ledger_view)
        self.statusBar().showMessage(f"دفتر العميل")
        
        # التحقق من ضرورة النسخ الاحتياطي التلقائي
        self.check_auto_backup()
    
    def show_suppliers_view(self):
        """عرض صفحة قائمة الموردين"""
        if self.section_disabled("suppliers"):
            return

        self.suppliers_view.load_data()
        self.stack.setCurrentWidget(self.suppliers_view)
        self.statusBar().showMessage("قائمة الموردين - Ctrl+H للعودة للعملاء")
    
    def show_supplier_ledger(self, supplier_id: str):
        """عرض صفحة حساب المورد"""
        # إزالة الصفحة القديمة إذا وجدت
        if self.supplier_ledger_view:
            self.stack.removeWidget(self.supplier_ledger_view)
            self.supplier_ledger_view.deleteLater()
        
        # إنشاء صفحة جديدة
        self.supplier_ledger_view = SupplierLedgerView(self.storage, supplier_id, self)
        self.supplier_ledger_view.back_requested.connect(self.show_suppliers_view)
        self.stack.addWidget(self.supplier_ledger_view)
        self.stack.setCurrentWidget(self.supplier_ledger_view)
        self.statusBar().showMessage(f"حساب المورد")
    
    def show_purchase_orders(self):
        """عرض صفحة فواتير الشراء"""
        if self.section_disabled("suppliers"):
            return

        self.purchase_order_view.refresh()
        self.stack.setCurrentWidget(self.purchase_order_view)
        self.statusBar().showMessage("فواتير الشراء - Ctrl+H للعودة للعملاء")
    
    def show_checks(self):
        """عرض صفحة الشيكات"""
        if self.section_disabled("suppliers"):
            return

        self.checks_view.refresh()
        self.stack.setCurrentWidget(self.checks_view)
        self.statusBar().showMessage("نظام الشيكات - Ctrl+H للعودة للعملاء")
    
    def check_auto_backup(self):
        """التحقق من ضرورة النسخ الاحتياطي التلقائي"""
        current_count = self.storage.get_total_entries_count()
        
        if self.backup_manager.should_backup(current_count):
            reply = QMessageBox.question(
                self, "نسخ احتياطي تلقائي",
                f"تم الوصول إلى {self.backup_manager.interval} إدخال جديد.\n"
                "هل تريد إنشاء نسخة احتياطية الآن؟",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                backup_path = self.backup_manager.perform_backup()
                if backup_path:
                    self.backup_manager.update_last_backup_count(current_count)
                    QMessageBox.information(
                        self, "نجح",
                        f"تم إنشاء النسخة الاحتياطية بنجاح:\n{backup_path}"
                    )
            else:
                # تحديث العداد حتى لا يُطلب مرة أخرى
                self.backup_manager.update_last_backup_count(current_count)
    
    def create_manual_backup(self):
        """إنشاء نسخة احتياطية يدوية"""
        try:
            backup_path = create_backup()
            QMessageBox.information(
                self, "نجح",
                f"تم إنشاء النسخة الاحتياطية بنجاح:\n{backup_path}"
            )
            self.statusBar().showMessage(f"تم إنشاء نسخة احتياطية: {backup_path.name}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في إنشاء النسخة الاحتياطية: {str(e)}")
    
    def export_all_data(self):
        """تصدير جميع البيانات"""
        from PySide6.QtWidgets import QFileDialog
        from core.backup import export_all_data
        
        path, _ = QFileDialog.getSaveFileName(
            self, "تصدير جميع البيانات", "", "ZIP Files (*.zip)"
        )
        
        if path:
            try:
                export_path = export_all_data(path)
                QMessageBox.information(
                    self, "نجح",
                    f"تم تصدير جميع البيانات بنجاح:\n{export_path}"
                )
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في التصدير: {str(e)}")
    
    def toggle_theme(self):
        """تبديل الوضع بين فاتح وداكن"""
        current_theme = self.storage.get_setting("theme", "light")
        new_theme = "dark" if current_theme == "light" else "light"
        
        self.storage.update_setting("theme", new_theme)
        self.apply_theme()
        
        theme_name = "الداكن" if new_theme == "dark" else "الفاتح"
        self.statusBar().showMessage(f"تم التبديل إلى الوضع {theme_name}", 3000)
    
    def apply_theme(self):
        """تطبيق الوضع (فاتح أو داكن)"""
        theme = self.storage.get_setting("theme", "light")
        
        if theme == "dark":
            # وضع داكن
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QTableWidget {
                    background-color: #3b3b3b;
                    alternate-background-color: #454545;
                    color: #ffffff;
                    gridline-color: #555555;
                }
                QHeaderView::section {
                    background-color: #505050;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 5px;
                }
                QPushButton {
                    background-color: #0d6efd;
                    color: #ffffff;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #0b5ed7;
                }
                QLineEdit, QComboBox, QDateTimeEdit {
                    background-color: #3b3b3b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QGroupBox {
                    border: 2px solid #555555;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)
        else:
            # وضع فاتح مشرق
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #f0f7ff;
                    color: #1e293b;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f0f9ff;
                    gridline-color: #e2e8f0;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                }
                QHeaderView::section {
                    background-color: #3b82f6;
                    color: #ffffff;
                    border: none;
                    padding: 8px 5px;
                    font-weight: bold;
                }
                QPushButton {
                    background-color: #3b82f6;
                    color: #ffffff;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
                QPushButton:pressed {
                    background-color: #1d4ed8;
                }
                QLineEdit, QComboBox, QDateTimeEdit {
                    background-color: #ffffff;
                    border: 2px solid #e2e8f0;
                    padding: 8px;
                    border-radius: 6px;
                }
                QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus {
                    border: 2px solid #3b82f6;
                }
                QGroupBox {
                    border: 2px solid #3b82f6;
                    border-radius: 8px;
                    margin-top: 12px;
                    font-weight: bold;
                    background-color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px;
                    color: #3b82f6;
                }
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QMenuBar {
                    background-color: #3b82f6;
                    color: #ffffff;
                    padding: 4px;
                }
                QMenuBar::item:selected {
                    background-color: #2563eb;
                }
                QMenu {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                }
                QMenu::item:selected {
                    background-color: #3b82f6;
                    color: #ffffff;
                }
                QStatusBar {
                    background-color: #3b82f6;
                    color: #ffffff;
                }
            """)
    
    def setup_app_lock(self):
        """إعداد قفل التطبيق"""
        dialog = AppLockDialog(mode="setup", parent=self)
        if dialog.exec():
            password_hash = hash_password(dialog.password)
            self.storage.update_setting("password_hash", password_hash)
            QMessageBox.information(
                self, "نجح",
                "تم تفعيل قفل التطبيق بنجاح.\n"
                "سيُطلب منك إدخال كلمة المرور عند فتح التطبيق."
            )
    
    def remove_app_lock(self):
        """إلغاء قفل التطبيق"""
        password_hash = self.storage.get_setting("password_hash")
        
        if not password_hash:
            QMessageBox.information(self, "معلومة", "قفل التطبيق غير مفعّل")
            return
        
        # التحقق من كلمة المرور الحالية
        dialog = AppLockDialog(mode="verify", parent=self)
        if dialog.exec():
            if verify_password(dialog.password, password_hash):
                self.storage.update_setting("password_hash", None)
                QMessageBox.information(self, "نجح", "تم إلغاء قفل التطبيق بنجاح")
            else:
                QMessageBox.warning(self, "خطأ", "كلمة مرور خاطئة")
    
    def configure_backup(self):
        """إعدادات النسخ الاحتياطي"""
        current_interval = self.storage.get_setting("auto_backup_interval", 200)
        
        interval, ok = QInputDialog.getInt(
            self, "إعدادات النسخ الاحتياطي",
            "عدد الإدخالات بين كل نسخة احتياطية:",
            current_interval, 10, 10000, 10
        )
        
        if ok:
            self.storage.update_setting("auto_backup_interval", interval)
            self.backup_manager.interval = interval
            QMessageBox.information(
                self, "نجح",
                f"تم تحديث إعدادات النسخ الاحتياطي.\n"
                f"سيتم إنشاء نسخة احتياطية كل {interval} إدخال."
            )
    
    def show_about(self):
        """عرض معلومات عن التطبيق"""
        QMessageBox.about(
            self, "حول التطبيق",
            "<h2>إدارة ديون العملاء</h2>"
            "<p>نظام لإدارة ديون عملاء محل الخضار والفواكه</p>"
            f"<p><b>الإصدار:</b> {__version__}</p>"
            "<p><b>المطور:</b> AbuDergham - 0569337729</p>"
            "<hr>"
            "<p>التخزين: ملفات JSON/JSONL محلية</p>"
            "<p>النسخ الاحتياطي: تلقائي ويدوي</p>"
            "<p>التصدير والطباعة: PDF, Excel, CSV, JSON</p>"
        )

    def configure_shop_info(self):
        """
        تعديل اسم المحل ورقم هاتفه
        Edit shop name and phone

        يظهران في ترويسة كل مطبوعة — كشف حساب يُسلَّم للزبون بلا اسم المحل
        غير مقبول.
        """
        from PySide6.QtWidgets import (
            QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("معلومات المحل")
        dialog.setModal(True)
        dialog.setMinimumWidth(380)

        name_input = QLineEdit(
            self.storage.get_setting("shop_name", "محل الخضار والفواكه"))
        name_input.setPlaceholderText("اسم المحل كما يظهر في المطبوعات")

        phone_input = QLineEdit(self.storage.get_setting("shop_phone", ""))
        phone_input.setPlaceholderText("مثال: 0569337729")

        form = QFormLayout()
        form.addRow("اسم المحل:", name_input)
        form.addRow("رقم الهاتف:", phone_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("💾 حفظ")
        buttons.button(QDialogButtonBox.Cancel).setText("إلغاء")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout = QVBoxLayout(dialog)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if not dialog.exec():
            return

        name = name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم المحل")
            return

        self.storage.update_setting("shop_name", name)
        self.storage.update_setting("shop_phone", phone_input.text().strip())
        self.statusBar().showMessage("تم حفظ معلومات المحل", 3000)

    # ============ التحديث التلقائي - Auto-update ============

    def start_update_check(self):
        """
        فحص التحديثات في الخلفية عند الإقلاع
        Check for updates in the background at startup

        لا يعطّل الواجهة، ولا يعرض شيئاً عند الفشل — التطبيق يعمل بلا
        إنترنت، وصاحب المحل يسجّل ديونه لا يهمّه أن GitHub بعيد.
        """
        if not self.storage.get_setting("check_updates", True):
            return

        from .update_dialog import start_background_check
        start_background_check(self, self.on_update_found)

    def on_update_found(self, info):
        """
        وُجد إصدار أحدث — إشعار هادئ بلا مقاطعة
        A newer release exists: notify quietly, never interrupt
        """
        if info.version == self.storage.get_setting("skipped_version", ""):
            return

        self.available_update = info
        self.update_action.setText(f"🔄 تحديث متاح: {info.version}")
        self.statusBar().showMessage(
            f"يتوفّر إصدار جديد {info.version} — مساعدة ← التحقق من التحديثات",
            15000,
        )

    def check_for_updates_manually(self):
        """التحقق من التحديثات بطلب المستخدم — هنا نُظهر النتيجة دائماً"""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt as _Qt
        from core.updater import check_for_update
        from core.version import GITHUB_OWNER, GITHUB_REPO, __version__
        from .update_dialog import UpdateDialog, current_exe_path

        info = getattr(self, "available_update", None)

        if info is None:
            QApplication.setOverrideCursor(_Qt.WaitCursor)
            self.statusBar().showMessage("جارٍ التحقق من التحديثات...")
            try:
                info = check_for_update(__version__, owner=GITHUB_OWNER,
                                        repo=GITHUB_REPO, timeout=10.0)
            finally:
                QApplication.restoreOverrideCursor()
                self.statusBar().clearMessage()

        if info is None:
            QMessageBox.information(
                self, "لا تحديثات",
                f"إصدارك {__version__} هو الأحدث.\n\n"
                "إن كان الجهاز غير متصل بالإنترنت، حاول لاحقاً."
            )
            return

        if current_exe_path() is None:
            QMessageBox.information(
                self, f"تحديث متاح: {info.version}",
                f"يتوفّر إصدار {info.version}.\n\n"
                "التحديث التلقائي يعمل على النسخة التنفيذية فقط — "
                "أنت تشغّل التطبيق من الكود المصدري."
            )
            return

        dialog = UpdateDialog(info, self.storage, self)
        if dialog.exec():
            self.update_action.setText("🔄 التحقق من التحديثات")
            self.available_update = None

    # ============ سلامة البيانات والاستعادة - Integrity & restore ============

    def restore_backup_dialog(self):
        """فتح نافذة استعادة نسخة احتياطية"""
        from .restore_dialog import RestoreBackupDialog

        if RestoreBackupDialog(self.storage, self).exec():
            self.close()

    def apply_disabled_sections(self):
        """
        تعطيل شاشات الأقسام التي تعذّرت قراءة ملفاتها
        Disable sections whose data files could not be read

        التعطيل **ظاهر دائماً**: أرصدة الموردين تُحسب من الشيكات ومن بنود
        الشراء، فتعطيل صامت يعني عرض أرقام غلط بلا أن يدري المستخدم.
        """
        if "suppliers" not in self.disabled_sections:
            return

        for action in (self.suppliers_action, self.purchases_action,
                       self.checks_action):
            action.setEnabled(False)
            action.setText(action.text() + "  (معطّل — ملف تالف)")

        self.statusBar().showMessage(
            "⚠️ تعذّرت قراءة أحد ملفات الموردين — شاشات الموردين والشيكات "
            "وفواتير الشراء معطّلة. ملف ← استعادة نسخة احتياطية."
        )

    def section_disabled(self, name: str) -> bool:
        """هل هذا القسم معطّل؟ يمنع فتحه عبر اختصار لوحة المفاتيح أيضاً"""
        if name not in self.disabled_sections:
            return False
        QMessageBox.warning(
            self, "القسم معطّل",
            "تعذّرت قراءة أحد ملفات هذا القسم، فعُطّل حتى لا تظهر أرقام خاطئة.\n\n"
            "جرّب: ملف ← استعادة نسخة احتياطية."
        )
        return True
