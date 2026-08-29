"""
عرض قائمة الموردين
Suppliers list view
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QMenu, QMessageBox, QHeaderView
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction

from core.storage import StorageManager
from core.supplier_summaries import SupplierSummaryEngine
from core.utils import format_currency
from .table_items import ArabicTextItem, NumericItem, sorted_table


class SuppliersView(QWidget):
    """
    عرض قائمة الموردين مع إحصائيات
    Suppliers list view with statistics
    """
    
    supplier_selected = Signal(str)  # supplier_id
    back_requested = Signal()
    
    def __init__(self, storage: StorageManager, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.summary_engine = SupplierSummaryEngine(storage)
        self.suppliers = []
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === الهيدر ===
        header = QHBoxLayout()
        
        title = QLabel("🏭 الموردون")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(title)
        
        header.addStretch()
        
        # بحث
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 بحث عن مورد...")
        self.search_input.setMaximumWidth(300)
        self.search_input.textChanged.connect(self.filter_suppliers)
        header.addWidget(self.search_input)
        
        # زر إضافة مورد
        add_btn = QPushButton("➕ إضافة مورد")
        add_btn.clicked.connect(self.add_supplier)
        header.addWidget(add_btn)
        
        # زر رجوع
        back_btn = QPushButton("← رجوع")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        
        layout.addLayout(header)
        
        # === بطاقة الإحصائيات ===
        stats_layout = QHBoxLayout()
        
        self.total_suppliers_label = QLabel("👥 عدد الموردين: 0")
        self.total_suppliers_label.setFont(QFont("Arial", 12))
        stats_layout.addWidget(self.total_suppliers_label)
        
        stats_layout.addStretch()
        
        self.total_balance_label = QLabel("💰 إجمالي الأرصدة: 0.00 شيكل")
        self.total_balance_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.total_balance_label.setStyleSheet("color: #ef4444;")
        stats_layout.addWidget(self.total_balance_label)
        
        layout.addLayout(stats_layout)
        
        # === جدول الموردين ===
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "الاسم", "الهاتف", "الرصيد", "الملاحظات"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        
        layout.addWidget(self.table)
    
    def load_data(self):
        """تحميل بيانات الموردين"""
        self.suppliers = self.storage.load_suppliers()
        
        # إعادة حساب الملخصات
        self.summary_engine.recalculate_all_summaries()
        
        self.display_suppliers(self.suppliers)
        self.update_stats()
    
    def display_suppliers(self, suppliers):
        """عرض الموردين في الجدول"""
        from decimal import Decimal

        summaries = self.storage.load_supplier_summaries()

        # الافتراضي: أبجدي حسب الاسم
        with sorted_table(self.table, column=0):
            self.table.setRowCount(len(suppliers))

            for row, supplier in enumerate(suppliers):
                # الاسم — ترتيب أبجدي عربي صحيح
                name_item = ArabicTextItem(supplier.name)
                name_item.setData(Qt.UserRole, supplier.id)
                name_item.setFont(QFont("Arial", 12))
                self.table.setItem(row, 0, name_item)

                # الهاتف
                self.table.setItem(row, 1, QTableWidgetItem(
                    supplier.phone if supplier.phone else "-"))

                # الرصيد — ترتيب رقمي لا نصّي
                summary = summaries.get(supplier.id)
                balance = summary.balance_decimal if summary else Decimal("0")

                balance_item = NumericItem(format_currency(balance), balance)
                balance_item.setFont(QFont("Arial", 12, QFont.Bold))
                balance_item.setForeground(Qt.red if balance > 0 else Qt.darkGreen)
                self.table.setItem(row, 2, balance_item)

                # الملاحظات
                self.table.setItem(row, 3, QTableWidgetItem(
                    supplier.notes if supplier.notes else "-"))
    
    def update_stats(self):
        """تحديث الإحصائيات"""
        total = len(self.suppliers)
        self.total_suppliers_label.setText(f"👥 عدد الموردين: {total}")
        
        total_balance = self.summary_engine.get_total_supplier_balance()
        self.total_balance_label.setText(f"💰 إجمالي الأرصدة: {format_currency(total_balance)}")
    
    def filter_suppliers(self, query):
        """تصفية الموردين حسب البحث"""
        if not query:
            self.display_suppliers(self.suppliers)
            return
        
        query = query.lower()
        filtered = [
            s for s in self.suppliers
            if query in s.name.lower() or
               query in (s.phone or "").lower() or
               query in (s.notes or "").lower()
        ]
        self.display_suppliers(filtered)
    
    def add_supplier(self):
        """إضافة مورد جديد"""
        from .dialogs import AddSupplierDialog
        
        dialog = AddSupplierDialog(self)
        if dialog.exec():
            try:
                self.storage.add_supplier(dialog.supplier)
                self.load_data()
                QMessageBox.information(self, "نجح", f"تم إضافة المورد '{dialog.supplier.name}' بنجاح")
            except ValueError as e:
                QMessageBox.warning(self, "خطأ", str(e))
    
    def edit_supplier(self, supplier):
        """تعديل معلومات مورد"""
        from .dialogs import EditSupplierDialog
        
        dialog = EditSupplierDialog(supplier, self)
        if dialog.exec():
            try:
                suppliers = self.storage.load_suppliers()
                for i, s in enumerate(suppliers):
                    if s.id == supplier.id:
                        suppliers[i] = dialog.updated_supplier
                        break
                self.storage.save_suppliers(suppliers)
                self.load_data()
                QMessageBox.information(self, "نجح", "تم تعديل معلومات المورد بنجاح")
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في تعديل المورد: {str(e)}")
    
    def delete_supplier(self, supplier):
        """حذف مورد"""
        from .search_dialog import DeleteConfirmDialog
        
        # التحقق من وجود مشتريات أو دفعات
        items = self.storage.get_supplier_purchase_items(supplier.id)
        payments = self.storage.get_supplier_payments(supplier.id)
        
        details = ""
        if items or payments:
            details = f"⚠️ المورد لديه {len(items)} بند شراء و {len(payments)} دفعة.\nسيتم حذف المورد فقط وستبقى البيانات."
        
        dialog = DeleteConfirmDialog("مورد", supplier.name, details, self)
        if dialog.exec():
            try:
                suppliers = self.storage.load_suppliers()
                suppliers = [s for s in suppliers if s.id != supplier.id]
                self.storage.save_suppliers(suppliers)
                self.load_data()
                QMessageBox.information(self, "نجح", f"تم حذف المورد '{supplier.name}' بنجاح")
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في حذف المورد: {str(e)}")
    
    def add_payment(self, supplier):
        """إضافة دفعة لمورد"""
        from .dialogs import AddSupplierPaymentDialog
        
        summary = self.storage.get_supplier_summary(supplier.id)
        dialog = AddSupplierPaymentDialog(supplier, summary.balance_decimal, self)
        
        if dialog.exec():
            try:
                self.storage.add_supplier_payment(dialog.payment)
                # إعادة حساب الملخصات
                self.summary_engine.recalculate_all_summaries()
                self.load_data()
                QMessageBox.information(self, "نجح", "تم إضافة الدفعة بنجاح")
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في إضافة الدفعة: {str(e)}")
    
    def show_context_menu(self, position):
        """عرض قائمة السياق"""
        row = self.table.rowAt(position.y())
        if row < 0:
            return
        
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        
        supplier_id = name_item.data(Qt.UserRole)
        supplier = self.storage.get_supplier(supplier_id)
        if not supplier:
            return
        
        menu = QMenu(self)
        
        # فتح حساب المورد
        open_action = QAction("📋 فتح الحساب", self)
        open_action.triggered.connect(lambda: self.supplier_selected.emit(supplier_id))
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        # إضافة دفعة
        payment_action = QAction("💰 إضافة دفعة", self)
        payment_action.triggered.connect(lambda: self.add_payment(supplier))
        menu.addAction(payment_action)
        
        menu.addSeparator()
        
        # تعديل
        edit_action = QAction("✏️ تعديل", self)
        edit_action.triggered.connect(lambda: self.edit_supplier(supplier))
        menu.addAction(edit_action)
        
        # حذف
        delete_action = QAction("🗑️ حذف", self)
        delete_action.triggered.connect(lambda: self.delete_supplier(supplier))
        menu.addAction(delete_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def on_row_double_clicked(self, index):
        """النقر المزدوج - فتح حساب المورد"""
        row = index.row()
        name_item = self.table.item(row, 0)
        if name_item:
            supplier_id = name_item.data(Qt.UserRole)
            self.supplier_selected.emit(supplier_id)
