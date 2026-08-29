"""
حوار البحث الشامل
Global search dialog
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QComboBox,
    QGroupBox, QFormLayout, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from decimal import Decimal

from core.storage import StorageManager
from core.analytics import AnalyticsEngine
from core.utils import format_currency, format_datetime_arabic


class SearchDialog(QDialog):
    """حوار البحث الشامل"""
    
    entry_selected = Signal(str, str)  # customer_id, entry_date
    
    def __init__(self, storage: StorageManager, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.analytics = AnalyticsEngine(storage)
        
        self.setWindowTitle("🔍 بحث شامل")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        
        self.setup_ui()
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        
        # منطقة البحث
        search_group = QGroupBox("معايير البحث")
        search_layout = QFormLayout(search_group)
        
        # البحث النصي
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث في الأسماء، الأوصاف، المبالغ...")
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addRow("البحث:", self.search_input)
        
        # فلاتر
        filters_layout = QHBoxLayout()
        
        # نوع الإدخال
        self.type_combo = QComboBox()
        self.type_combo.addItem("الكل", None)
        self.type_combo.addItem("دين", "purchase")
        self.type_combo.addItem("دفع", "payment")
        self.type_combo.currentIndexChanged.connect(self.on_search)
        filters_layout.addWidget(QLabel("النوع:"))
        filters_layout.addWidget(self.type_combo)
        
        filters_layout.addSpacing(20)
        
        # نطاق المبلغ
        self.min_amount = QLineEdit()
        self.min_amount.setPlaceholderText("0")
        self.min_amount.setMaximumWidth(100)
        self.min_amount.textChanged.connect(self.on_search)
        filters_layout.addWidget(QLabel("من:"))
        filters_layout.addWidget(self.min_amount)
        
        self.max_amount = QLineEdit()
        self.max_amount.setPlaceholderText("∞")
        self.max_amount.setMaximumWidth(100)
        self.max_amount.textChanged.connect(self.on_search)
        filters_layout.addWidget(QLabel("إلى:"))
        filters_layout.addWidget(self.max_amount)
        
        filters_layout.addStretch()
        
        search_layout.addRow("الفلاتر:", filters_layout)
        
        layout.addWidget(search_group)
        
        # عدد النتائج
        self.results_label = QLabel("النتائج: 0")
        self.results_label.setFont(QFont("Arial", 11))
        layout.addWidget(self.results_label)
        
        # جدول النتائج
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "العميل", "النوع", "المبلغ", "الوصف", "التاريخ", "الملاحظات"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)
        
        # أزرار
        buttons = QHBoxLayout()
        
        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.close)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        
        layout.addLayout(buttons)
        
        # تحميل كل النتائج
        self.on_search()
    
    def on_search(self):
        """تنفيذ البحث"""
        query = self.search_input.text()
        entry_type = self.type_combo.currentData()
        
        min_amount = None
        max_amount = None
        
        try:
            if self.min_amount.text():
                min_amount = Decimal(self.min_amount.text())
        except:
            pass
        
        try:
            if self.max_amount.text():
                max_amount = Decimal(self.max_amount.text())
        except:
            pass
        
        results = self.analytics.search_entries(
            query=query,
            entry_type=entry_type,
            min_amount=min_amount,
            max_amount=max_amount
        )
        
        self.display_results(results)
    
    def display_results(self, results):
        """عرض نتائج البحث"""
        self.table.setRowCount(len(results))
        self.results_label.setText(f"النتائج: {len(results)}")
        
        for row, (entry, customer) in enumerate(results):
            # العميل
            customer_item = QTableWidgetItem(customer.name)
            customer_item.setData(Qt.UserRole, customer.id)
            customer_item.setData(Qt.UserRole + 1, entry.date)
            self.table.setItem(row, 0, customer_item)
            
            # النوع
            type_text = "دين" if entry.type == "purchase" else "دفع"
            type_item = QTableWidgetItem(type_text)
            self.table.setItem(row, 1, type_item)
            
            # المبلغ
            amount_item = QTableWidgetItem(format_currency(entry.amount_decimal))
            self.table.setItem(row, 2, amount_item)
            
            # الوصف
            desc_item = QTableWidgetItem(entry.desc)
            self.table.setItem(row, 3, desc_item)
            
            # التاريخ
            date_item = QTableWidgetItem(format_datetime_arabic(entry.datetime))
            self.table.setItem(row, 4, date_item)
            
            # الملاحظات
            notes_item = QTableWidgetItem(entry.notes if entry.notes else "-")
            self.table.setItem(row, 5, notes_item)
    
    def on_row_double_clicked(self, index):
        """عند النقر المزدوج على سطر"""
        row = index.row()
        customer_item = self.table.item(row, 0)
        if customer_item:
            customer_id = customer_item.data(Qt.UserRole)
            entry_date = customer_item.data(Qt.UserRole + 1)
            self.entry_selected.emit(customer_id, entry_date)
            self.accept()
