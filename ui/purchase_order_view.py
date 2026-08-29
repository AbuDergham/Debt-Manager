"""
عرض فواتير الشراء (الطلبيات)
Purchase orders view
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QComboBox, QHeaderView, QFrame, QMessageBox,
    QDateEdit, QCheckBox, QFormLayout, QGroupBox,
    QSplitter, QMenu
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QFont, QDoubleValidator, QAction
from decimal import Decimal
from datetime import datetime

from core.storage import StorageManager
from core.models import (
    Supplier, PurchaseOrder, PurchaseItem
)
from core.supplier_summaries import SupplierSummaryEngine
from core.utils import format_currency, generate_order_id, format_datetime_arabic


class PurchaseOrderView(QWidget):
    """
    عرض فواتير الشراء مع إمكانية إنشاء طلبيات جديدة
    Purchase order view with order creation
    """
    
    back_requested = Signal()
    
    def __init__(self, storage: StorageManager, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.summary_engine = SupplierSummaryEngine(storage)
        self.current_order_items = []  # بنود الطلبية الحالية (قبل الحفظ)
        self.setup_ui()
        self.load_suppliers()
        self.load_orders_history()
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === الهيدر ===
        header = QHBoxLayout()
        
        title = QLabel("🧾 فواتير الشراء")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(title)
        
        header.addStretch()
        
        # زر رجوع
        back_btn = QPushButton("← رجوع")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        
        layout.addLayout(header)
        
        # === قسمين: نموذج إضافة + تاريخ الطلبيات ===
        splitter = QSplitter(Qt.Vertical)
        
        # --- القسم العلوي: إنشاء طلبية جديدة ---
        new_order_widget = QWidget()
        new_order_layout = QVBoxLayout(new_order_widget)
        
        # عنوان
        new_order_header = QHBoxLayout()
        new_order_title = QLabel("➕ إنشاء طلبية جديدة")
        new_order_title.setFont(QFont("Arial", 14, QFont.Bold))
        new_order_header.addWidget(new_order_title)
        
        new_order_header.addStretch()
        
        # تاريخ الطلبية
        new_order_header.addWidget(QLabel("📅 التاريخ:"))
        self.order_date_edit = QDateEdit()
        self.order_date_edit.setCalendarPopup(True)
        self.order_date_edit.setDate(QDate.currentDate())
        self.order_date_edit.setDisplayFormat("dd/MM/yyyy")
        new_order_header.addWidget(self.order_date_edit)
        
        new_order_layout.addLayout(new_order_header)
        
        # === نموذج إضافة بند ===
        item_form_group = QGroupBox("إضافة صنف")
        item_form = QHBoxLayout(item_form_group)
        
        # المورد
        item_form.addWidget(QLabel("المورد:"))
        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumWidth(150)
        item_form.addWidget(self.supplier_combo)
        
        # الصنف
        item_form.addWidget(QLabel("الصنف:"))
        self.item_name_input = QLineEdit()
        self.item_name_input.setPlaceholderText("بندورة، خيار...")
        self.item_name_input.setMinimumWidth(100)
        item_form.addWidget(self.item_name_input)
        
        # العدد
        item_form.addWidget(QLabel("العدد:"))
        self.quantity_input = QLineEdit()
        self.quantity_input.setPlaceholderText("0")
        self.quantity_input.setMaximumWidth(60)
        self.quantity_input.setValidator(QDoubleValidator(0, 99999, 2))
        self.quantity_input.textChanged.connect(self.auto_calculate_total)
        item_form.addWidget(self.quantity_input)
        
        # الوزن
        item_form.addWidget(QLabel("الوزن:"))
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("0")
        self.weight_input.setMaximumWidth(60)
        self.weight_input.setValidator(QDoubleValidator(0, 99999, 2))
        self.weight_input.textChanged.connect(self.auto_calculate_total)
        item_form.addWidget(self.weight_input)
        
        # السعر
        item_form.addWidget(QLabel("السعر:"))
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("0")
        self.price_input.setMaximumWidth(60)
        self.price_input.setValidator(QDoubleValidator(0, 99999, 2))
        self.price_input.textChanged.connect(self.auto_calculate_total)
        item_form.addWidget(self.price_input)
        
        # التعبئة
        self.packaging_combo = QComboBox()
        self.packaging_combo.addItem("بلدية", "municipal")
        self.packaging_combo.addItem("بلاستيك", "plastic")
        self.packaging_combo.setMaximumWidth(80)
        item_form.addWidget(self.packaging_combo)
        
        # طريقة الدفع
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItem("آجل", "credit")
        self.payment_method_combo.addItem("نقدي", "cash")
        self.payment_method_combo.setMaximumWidth(70)
        item_form.addWidget(self.payment_method_combo)
        
        # المجموع
        item_form.addWidget(QLabel("المجموع:"))
        self.total_input = QLineEdit()
        self.total_input.setPlaceholderText("0.00")
        self.total_input.setMaximumWidth(80)
        self.total_input.setValidator(QDoubleValidator(0, 999999, 2))
        self.total_input.setStyleSheet("font-weight: bold; font-size: 13px;")
        item_form.addWidget(self.total_input)
        
        # زر إضافة
        add_item_btn = QPushButton("✅ إضافة")
        add_item_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        add_item_btn.clicked.connect(self.add_item_to_order)
        item_form.addWidget(add_item_btn)
        
        new_order_layout.addWidget(item_form_group)
        
        # === جدول بنود الطلبية الحالية ===
        items_header = QHBoxLayout()
        self.items_count_label = QLabel("📦 بنود الطلبية: 0")
        self.items_count_label.setFont(QFont("Arial", 12))
        items_header.addWidget(self.items_count_label)
        
        items_header.addStretch()
        
        self.order_total_label = QLabel("💰 المجموع الكلي: 0.00 شيكل")
        self.order_total_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.order_total_label.setStyleSheet("color: #3b82f6;")
        items_header.addWidget(self.order_total_label)
        
        # زر حفظ الطلبية
        save_order_btn = QPushButton("💾 حفظ الطلبية")
        save_order_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        save_order_btn.clicked.connect(self.save_order)
        items_header.addWidget(save_order_btn)
        
        new_order_layout.addLayout(items_header)
        
        # جدول البنود الحالية
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(9)
        self.items_table.setHorizontalHeaderLabels([
            "المورد", "الصنف", "العدد", "الوزن", "السعر",
            "التعبئة", "الدفع", "المجموع", "حذف"
        ])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setMaximumHeight(200)
        
        new_order_layout.addWidget(self.items_table)
        
        splitter.addWidget(new_order_widget)
        
        # --- القسم السفلي: تاريخ الطلبيات ---
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        
        history_header = QHBoxLayout()
        history_title = QLabel("📋 الطلبيات السابقة")
        history_title.setFont(QFont("Arial", 14, QFont.Bold))
        history_header.addWidget(history_title)
        
        history_header.addStretch()
        
        # فلتر الفترة
        self.history_filter = QComboBox()
        self.history_filter.addItem("📅 اليوم", "today")
        self.history_filter.addItem("📆 هذا الشهر", "month")
        self.history_filter.addItem("🗓️ الكل", "all")
        self.history_filter.setCurrentIndex(0)
        self.history_filter.currentIndexChanged.connect(self.load_orders_history)
        history_header.addWidget(QLabel("الفترة:"))
        history_header.addWidget(self.history_filter)
        
        history_layout.addLayout(history_header)
        
        # جدول الطلبيات
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(4)
        self.orders_table.setHorizontalHeaderLabels([
            "التاريخ", "عدد البنود", "المجموع", "ملاحظات"
        ])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.orders_table.setAlternatingRowColors(True)
        self.orders_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.orders_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.orders_table.customContextMenuRequested.connect(self.show_order_context_menu)
        self.orders_table.doubleClicked.connect(self.on_order_double_clicked)
        
        history_layout.addWidget(self.orders_table)
        
        splitter.addWidget(history_widget)
        
        layout.addWidget(splitter)
    
    def load_suppliers(self):
        """تحميل قائمة الموردين"""
        self.supplier_combo.clear()
        suppliers = self.storage.load_suppliers()
        for supplier in suppliers:
            self.supplier_combo.addItem(supplier.name, supplier.id)
    
    def auto_calculate_total(self):
        """حساب المجموع تلقائياً"""
        try:
            quantity = self.quantity_input.text().strip()
            weight = self.weight_input.text().strip()
            price = self.price_input.text().strip()
            
            total = PurchaseItem.calculate_total(quantity, weight, price)
            
            if total > 0:
                self.total_input.setText(f"{total:.2f}")
        except:
            pass
    
    def add_item_to_order(self):
        """إضافة بند للطلبية الحالية"""
        # التحقق من الحقول
        if self.supplier_combo.count() == 0:
            QMessageBox.warning(self, "خطأ", "لا يوجد موردين. أضف مورد أولاً من قائمة الموردين.")
            return
        
        item_name = self.item_name_input.text().strip()
        if not item_name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم الصنف")
            return
        
        total_text = self.total_input.text().strip()
        if not total_text:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال المجموع")
            return
        
        try:
            total = Decimal(total_text)
            if total <= 0:
                QMessageBox.warning(self, "خطأ", "المجموع يجب أن يكون أكبر من صفر")
                return
        except:
            QMessageBox.warning(self, "خطأ", "المجموع غير صالح")
            return
        
        # إنشاء البند
        supplier_id = self.supplier_combo.currentData()
        supplier_name = self.supplier_combo.currentText()
        
        item_data = {
            'supplier_id': supplier_id,
            'supplier_name': supplier_name,
            'item_name': item_name,
            'quantity': self.quantity_input.text().strip() or "0",
            'weight': self.weight_input.text().strip() or "0",
            'price': self.price_input.text().strip() or "0",
            'packaging': self.packaging_combo.currentData(),
            'payment_method': self.payment_method_combo.currentData(),
            'total': f"{total:.2f}"
        }
        
        self.current_order_items.append(item_data)
        self.refresh_items_table()
        self.clear_item_form()
    
    def clear_item_form(self):
        """مسح نموذج إضافة البند"""
        self.item_name_input.clear()
        self.quantity_input.clear()
        self.weight_input.clear()
        self.price_input.clear()
        self.total_input.clear()
        self.item_name_input.setFocus()
    
    def refresh_items_table(self):
        """تحديث جدول البنود الحالية"""
        self.items_table.setRowCount(len(self.current_order_items))
        
        order_total = Decimal("0")
        
        for row, item in enumerate(self.current_order_items):
            # المورد
            self.items_table.setItem(row, 0, QTableWidgetItem(item['supplier_name']))
            
            # الصنف
            self.items_table.setItem(row, 1, QTableWidgetItem(item['item_name']))
            
            # العدد
            self.items_table.setItem(row, 2, QTableWidgetItem(item['quantity']))
            
            # الوزن
            self.items_table.setItem(row, 3, QTableWidgetItem(item['weight']))
            
            # السعر
            self.items_table.setItem(row, 4, QTableWidgetItem(item['price']))
            
            # التعبئة
            packaging_ar = "بلدية" if item['packaging'] == 'municipal' else "بلاستيك"
            self.items_table.setItem(row, 5, QTableWidgetItem(packaging_ar))
            
            # الدفع
            payment_ar = "آجل" if item['payment_method'] == 'credit' else "نقدي"
            self.items_table.setItem(row, 6, QTableWidgetItem(payment_ar))
            
            # المجموع
            total_item = QTableWidgetItem(item['total'])
            total_item.setFont(QFont("Arial", 11, QFont.Bold))
            self.items_table.setItem(row, 7, total_item)
            
            order_total += Decimal(item['total'])
            
            # زر حذف
            delete_btn = QPushButton("🗑️")
            delete_btn.setStyleSheet("background: #fee2e2; border: none; padding: 5px;")
            delete_btn.clicked.connect(lambda checked, r=row: self.remove_item(r))
            self.items_table.setCellWidget(row, 8, delete_btn)
        
        # تحديث العدادات
        self.items_count_label.setText(f"📦 بنود الطلبية: {len(self.current_order_items)}")
        self.order_total_label.setText(f"💰 المجموع الكلي: {format_currency(order_total)}")
    
    def remove_item(self, row):
        """حذف بند من الطلبية"""
        if 0 <= row < len(self.current_order_items):
            self.current_order_items.pop(row)
            self.refresh_items_table()
    
    def save_order(self):
        """حفظ الطلبية"""
        if not self.current_order_items:
            QMessageBox.warning(self, "خطأ", "لا يوجد بنود في الطلبية")
            return
        
        try:
            # إنشاء الطلبية
            order_id = generate_order_id()
            date = self.order_date_edit.date().toPython()
            
            order = PurchaseOrder(
                id=order_id,
                date=datetime(date.year, date.month, date.day).isoformat()
            )
            
            # حفظ الطلبية
            self.storage.add_purchase_order(order)
            
            # حفظ البنود
            for item_data in self.current_order_items:
                item = PurchaseItem(
                    order_id=order_id,
                    supplier_id=item_data['supplier_id'],
                    item_name=item_data['item_name'],
                    quantity=item_data['quantity'],
                    weight=item_data['weight'],
                    price=item_data['price'],
                    packaging=item_data['packaging'],
                    payment_method=item_data['payment_method'],
                    total=item_data['total']
                )
                self.storage.add_purchase_item(item)
            
            # إعادة حساب ملخصات الموردين
            self.summary_engine.recalculate_all_summaries()
            
            # تنظيف
            items_count = len(self.current_order_items)
            total = sum(Decimal(i['total']) for i in self.current_order_items)
            
            self.current_order_items.clear()
            self.refresh_items_table()
            self.load_orders_history()
            
            QMessageBox.information(
                self, "نجح",
                f"تم حفظ الطلبية بنجاح!\n"
                f"عدد الأصناف: {items_count}\n"
                f"المجموع: {format_currency(total)}"
            )
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في حفظ الطلبية: {str(e)}")
    
    def load_orders_history(self):
        """تحميل تاريخ الطلبيات"""
        orders = self.storage.load_purchase_orders()
        all_items = self.storage.load_purchase_items()
        
        # ترتيب بالتاريخ (الأحدث أولاً)
        orders.sort(key=lambda o: o.date, reverse=True)
        
        # تصفية حسب الفترة
        period = self.history_filter.currentData()
        now = datetime.now()
        
        if period == "today":
            orders = [o for o in orders if o.datetime.date() == now.date()]
        elif period == "month":
            orders = [o for o in orders if o.datetime.year == now.year and o.datetime.month == now.month]
        
        self.orders_table.setRowCount(len(orders))
        
        for row, order in enumerate(orders):
            # التاريخ
            date_item = QTableWidgetItem(format_datetime_arabic(order.datetime))
            date_item.setData(Qt.UserRole, order.id)
            self.orders_table.setItem(row, 0, date_item)
            
            # عدد البنود
            order_items = [i for i in all_items if i.order_id == order.id]
            count_item = QTableWidgetItem(str(len(order_items)))
            self.orders_table.setItem(row, 1, count_item)
            
            # المجموع
            order_total = sum(i.total_decimal for i in order_items)
            total_item = QTableWidgetItem(format_currency(order_total))
            total_item.setFont(QFont("Arial", 11, QFont.Bold))
            self.orders_table.setItem(row, 2, total_item)
            
            # الملاحظات
            notes_item = QTableWidgetItem(order.notes if order.notes else "-")
            self.orders_table.setItem(row, 3, notes_item)
    
    def show_order_context_menu(self, position):
        """عرض قائمة السياق للطلبية"""
        row = self.orders_table.rowAt(position.y())
        if row < 0:
            return
        
        date_item = self.orders_table.item(row, 0)
        if not date_item:
            return
        
        order_id = date_item.data(Qt.UserRole)
        
        menu = QMenu(self)
        
        # عرض التفاصيل
        details_action = QAction("📋 عرض التفاصيل", self)
        details_action.triggered.connect(lambda: self.show_order_details(order_id))
        menu.addAction(details_action)
        
        menu.exec(self.orders_table.viewport().mapToGlobal(position))
    
    def on_order_double_clicked(self, index):
        """النقر المزدوج - عرض تفاصيل الطلبية"""
        row = index.row()
        date_item = self.orders_table.item(row, 0)
        if date_item:
            order_id = date_item.data(Qt.UserRole)
            self.show_order_details(order_id)
    
    def show_order_details(self, order_id: str):
        """عرض تفاصيل طلبية"""
        order = self.storage.get_purchase_order(order_id)
        if not order:
            return
        
        items = self.storage.get_order_items(order_id)
        suppliers = {s.id: s for s in self.storage.load_suppliers()}
        
        # بناء النص
        details = f"📋 تفاصيل الطلبية\n"
        details += f"التاريخ: {format_datetime_arabic(order.datetime)}\n"
        details += f"عدد الأصناف: {len(items)}\n\n"
        
        total = Decimal("0")
        for item in items:
            supplier = suppliers.get(item.supplier_id)
            supplier_name = supplier.name if supplier else item.supplier_id
            packaging_ar = "بلدية" if item.packaging == 'municipal' else "بلاستيك"
            payment_ar = "آجل" if item.payment_method == 'credit' else "نقدي"
            
            details += f"• {item.item_name} - {supplier_name}\n"
            details += f"  العدد: {item.quantity} | الوزن: {item.weight} | السعر: {item.price}\n"
            details += f"  التعبئة: {packaging_ar} | الدفع: {payment_ar}\n"
            details += f"  المجموع: {format_currency(item.total_decimal)}\n\n"
            total += item.total_decimal
        
        details += f"━━━━━━━━━━━━━━━━━━━━\n"
        details += f"المجموع الكلي: {format_currency(total)}"
        
        QMessageBox.information(self, "تفاصيل الطلبية", details)
    
    def refresh(self):
        """تحديث البيانات"""
        self.load_suppliers()
        self.load_orders_history()
