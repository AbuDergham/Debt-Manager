"""
عرض قائمة العملاء
Customers list view
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLineEdit, QPushButton, QLabel, QHeaderView, QMessageBox, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QAction
from decimal import Decimal
from typing import List
from core.models import Customer, Summary
from core.storage import StorageManager
from core.summaries import recalculate_all_summaries
from core.utils import format_currency
from .dialogs import AddCustomerDialog


class CustomersView(QWidget):
    """
    عرض قائمة العملاء مع البحث والملخصات
    Customers list view with search and summaries
    """
    
    # إشارة لفتح صفحة دفتر العميل
    customer_selected = Signal(str)  # customer_id
    
    def __init__(self, storage: StorageManager, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.customers: List[Customer] = []
        self.summaries: dict[str, Summary] = {}
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout()
        
        # الشريط العلوي
        top_bar = QHBoxLayout()
        
        # عنوان
        title = QLabel("إدارة ديون العملاء")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        top_bar.addWidget(title)
        
        top_bar.addStretch()
        
        # زر تحديث
        self.refresh_btn = QPushButton("🔄 تحديث")
        self.refresh_btn.clicked.connect(self.refresh)
        top_bar.addWidget(self.refresh_btn)
        
        # زر إضافة عميل
        self.add_customer_btn = QPushButton("+ إضافة عميل")
        self.add_customer_btn.clicked.connect(self.add_customer)
        top_bar.addWidget(self.add_customer_btn)
        
        layout.addLayout(top_bar)
        
        # شريط البحث
        search_layout = QHBoxLayout()
        
        search_label = QLabel("بحث:")
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث عن عميل...")
        self.search_input.textChanged.connect(self.filter_customers)
        search_layout.addWidget(self.search_input)
        
        layout.addLayout(search_layout)
        
        # جدول العملاء
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "اسم العميل",
            "الرصيد الحالي",
            "مبيعات اليوم",
            "مبيعات الشهر"
        ])
        
        # إعدادات الجدول
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # تمديد الأعمدة
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(4):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        # الاتصال بالنقر المزدوج
        self.table.cellDoubleClicked.connect(self.on_customer_double_clicked)
        
        # تفعيل قائمة السياق (النقر بالزر الأيمن)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.table)
        
        # شريط المعلومات السفلي
        bottom_bar = QHBoxLayout()
        
        self.total_customers_label = QLabel("إجمالي العملاء: 0")
        bottom_bar.addWidget(self.total_customers_label)
        
        bottom_bar.addStretch()
        
        self.total_debt_label = QLabel("إجمالي الديون: 0.00 ج.م")
        bottom_bar.addWidget(self.total_debt_label)
        
        layout.addLayout(bottom_bar)
        
        self.setLayout(layout)
    
    def load_data(self):
        """تحميل البيانات من التخزين"""
        # تحميل العملاء
        self.customers = self.storage.load_customers()
        
        # تحميل الملخصات
        self.summaries = self.storage.load_summaries()
        
        # إذا لم تكن هناك ملخصات، احسبها
        if not self.summaries:
            entries = self.storage.load_entries()
            self.summaries = recalculate_all_summaries(self.customers, entries)
            self.storage.save_summaries(self.summaries)
        
        # تحديث الجدول
        self.update_table()
    
    def update_table(self, filter_text: str = ""):
        """تحديث جدول العملاء"""
        # تصفية العملاء
        if filter_text:
            filtered_customers = [
                c for c in self.customers 
                if filter_text.lower() in c.name.lower() or 
                   filter_text.lower() in c.id.lower()
            ]
        else:
            filtered_customers = self.customers
        
        # تحديث الجدول
        self.table.setRowCount(len(filtered_customers))
        
        total_debt = Decimal("0.00")
        
        for row, customer in enumerate(filtered_customers):
            # الحصول على الملخص
            summary = self.summaries.get(customer.id, Summary.empty())
            
            # اسم العميل
            name_item = QTableWidgetItem(customer.name)
            name_item.setData(Qt.UserRole, customer.id)  # حفظ المعرف
            self.table.setItem(row, 0, name_item)
            
            # الرصيد الحالي
            balance = summary.balance_decimal
            balance_item = QTableWidgetItem(format_currency(balance))
            
            # تلوين الرصيد (أحمر إذا كان موجب، أخضر إذا كان سالب)
            if balance > 0:
                balance_item.setForeground(QColor(220, 53, 69))  # أحمر
            elif balance < 0:
                balance_item.setForeground(QColor(40, 167, 69))  # أخضر
            
            self.table.setItem(row, 1, balance_item)
            
            # مبيعات اليوم
            today_sales = summary.today_sales_decimal
            today_item = QTableWidgetItem(format_currency(today_sales))
            self.table.setItem(row, 2, today_item)
            
            # مبيعات الشهر
            month_sales = summary.month_sales_decimal
            month_item = QTableWidgetItem(format_currency(month_sales))
            self.table.setItem(row, 3, month_item)
            
            # إضافة للديون الإجمالية
            if balance > 0:
                total_debt += balance
        
        # تحديث التسميات السفلية
        self.total_customers_label.setText(f"إجمالي العملاء: {len(filtered_customers)}")
        self.total_debt_label.setText(f"إجمالي الديون: {format_currency(total_debt)}")
    
    def filter_customers(self):
        """تصفية العملاء حسب النص المدخل"""
        filter_text = self.search_input.text().strip()
        self.update_table(filter_text)
    
    def add_customer(self):
        """إضافة عميل جديد"""
        dialog = AddCustomerDialog(self)
        if dialog.exec():
            # إنشاء العميل
            customer = Customer(
                id=dialog.customer_id,
                name=dialog.customer_name,
                credit_limit=str(dialog.credit_limit)
            )
            
            try:
                # حفظ العميل
                self.storage.add_customer(customer)
                
                # إعادة تحميل البيانات
                self.load_data()
                
                QMessageBox.information(
                    self, "نجح", 
                    f"تم إضافة العميل '{customer.name}' بنجاح"
                )
            except ValueError as e:
                QMessageBox.warning(self, "خطأ", str(e))
    
    def on_customer_double_clicked(self, row, column):
        """النقر المزدوج على عميل"""
        customer_id = self.table.item(row, 0).data(Qt.UserRole)
        self.customer_selected.emit(customer_id)
    
    def refresh(self):
        """تحديث والبيانات وإعادة حساب الملخصات"""
        # تحميل أحدث البيانات
        self.customers = self.storage.load_customers()
        entries = self.storage.load_entries()
        
        # إعادة حساب جميع الملخصات (Hard Refresh)
        self.summaries = recalculate_all_summaries(self.customers, entries)
        self.storage.save_summaries(self.summaries)
        
        # تحديث الجدول
        self.update_table()
    
    def show_context_menu(self, position):
        """
        عرض قائمة السياق عند النقر بالزر الأيمن
        Show context menu on right-click
        """
        # الحصول على الصف المحدد
        row = self.table.rowAt(position.y())
        if row < 0:
            return
        
        # الحصول على معرف العميل
        customer_id = self.table.item(row, 0).data(Qt.UserRole)
        customer_name = self.table.item(row, 0).text()
        
        # إنشاء القائمة
        menu = QMenu(self)
        
        # فتح دفتر العميل
        open_ledger_action = QAction("📖 فتح دفتر العميل", self)
        open_ledger_action.triggered.connect(lambda: self.customer_selected.emit(customer_id))
        menu.addAction(open_ledger_action)
        
        menu.addSeparator()
        
        # إضافة دين
        add_purchase_action = QAction("🛒 إضافة دين", self)
        add_purchase_action.triggered.connect(lambda: self.quick_add_entry(customer_id, customer_name, "purchase"))
        menu.addAction(add_purchase_action)
        
        # إضافة دفع
        add_payment_action = QAction("💰 إضافة دفع", self)
        add_payment_action.triggered.connect(lambda: self.quick_add_entry(customer_id, customer_name, "payment"))
        menu.addAction(add_payment_action)
        
        menu.addSeparator()
        
        # تعديل معلومات العميل
        edit_info_action = QAction("✏️ تعديل معلومات العميل", self)
        edit_info_action.triggered.connect(lambda: self.edit_customer_info(customer_id))
        menu.addAction(edit_info_action)
        
        # حذف العميل
        delete_action = QAction("🗑️ حذف العميل", self)
        delete_action.triggered.connect(lambda: self.delete_customer(customer_id, customer_name))
        menu.addAction(delete_action)
        
        # عرض القائمة
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def quick_add_entry(self, customer_id: str, customer_name: str, entry_type: str):
        """
        إضافة إدخال سريع من قائمة السياق
        Quick add entry from context menu
        """
        from .dialogs import AddEntryDialog
        from core.summaries import calculate_customer_summary
        
        # الحصول على الرصيد الحالي للتحقق من حد الائتمان
        current_balance = Decimal("0")
        if customer_id in self.summaries:
            current_balance = self.summaries[customer_id].balance_decimal
            
        # الحصول على كائن العميل الكامل
        customer = next((c for c in self.customers if c.id == customer_id), None)
        
        if not customer:
            # حالة نادرة، إنشاء كائن مؤقت
            customer = Customer(customer_id, customer_name)
        
        dialog = AddEntryDialog(
            customer_id, 
            customer_name, 
            customer=customer,
            current_balance=current_balance,
            parent=self
        )
        
        # تعيين النوع الافتراضي
        if entry_type == "payment":
            dialog.type_combo.setCurrentIndex(1)
            dialog.on_type_changed(1)
        
        if dialog.exec():
            try:
                # حفظ الإدخال
                self.storage.add_entry(dialog.entry)
                
                # تحديث ملخص العميل فوراً
                # نحتاج تحميل كل الإدخالات لإعادة الحساب بدقة
                all_entries = self.storage.load_entries()
                new_summary = calculate_customer_summary(customer_id, all_entries)
                
                # تحديث التخزين والذاكرة
                self.summaries = self.storage.load_summaries()  # تحميل الحالي
                self.summaries[customer_id] = new_summary
                self.storage.save_summaries(self.summaries)
                
                # تحديث الجدول فقط
                self.update_table(self.search_input.text())
                
                QMessageBox.information(
                    self, "نجح", 
                    f"تم إضافة {'الدين' if entry_type == 'purchase' else 'الدفع'} وتحديث الرصيد بنجاح"
                )
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في حفظ الإدخال وتحديث الرصيد: {str(e)}")
    
    def edit_customer_info(self, customer_id: str):
        """
        تعديل معلومات العميل
        Edit customer information
        """
        # الحصول على العميل
        customers = self.storage.load_customers()
        customer = next((c for c in customers if c.id == customer_id), None)
        
        if not customer:
            QMessageBox.warning(self, "خطأ", "لم يتم العثور على العميل")
            return
        
        # فتح نافذة التعديل
        from .dialogs import EditCustomerDialog
        dialog = EditCustomerDialog(customer, self)
        
        if dialog.exec():
            try:
                # تحديث العميل في القائمة
                updated_customer = dialog.updated_customer
                for i, c in enumerate(customers):
                    if c.id == customer_id:
                        customers[i] = updated_customer
                        break
                
                self.storage.save_customers(customers)
                
                # إعادة تحميل البيانات
                self.load_data()
                
                QMessageBox.information(
                    self, "نجح",
                    f"تم تحديث معلومات العميل '{updated_customer.name}' بنجاح"
                )
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في تحديث العميل: {str(e)}")
    
    def delete_customer(self, customer_id: str, customer_name: str):
        """
        حذف العميل
        Delete customer
        """
        # التحقق مع المستخدم
        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من حذف العميل '{customer_name}'?\n\n"
            "سيتم حذف جميع إدخالات هذا العميل أيضاً.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # حذف العميل من القائمة
            customers = self.storage.load_customers()
            customers = [c for c in customers if c.id != customer_id]
            self.storage.save_customers(customers)
            
            # حذف ملخص العميل
            summaries = self.storage.load_summaries()
            if customer_id in summaries:
                del summaries[customer_id]
                self.storage.save_summaries(summaries)
            
            # ملاحظة: الإدخالات تبقى في entries.jsonl ولكن يمكن تجاهلها
            # في تطبيق أكثر تقدماً، يمكن إعادة كتابة ملف entries.jsonl بدون إدخالات هذا العميل
            
            # إعادة تحميل البيانات
            self.load_data()
            
            QMessageBox.information(
                self, "نجح",
                f"تم حذف العميل '{customer_name}' بنجاح"
            )

