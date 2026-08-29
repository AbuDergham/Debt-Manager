"""
عرض حساب المورد (كشف حساب)
Supplier ledger view
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QHeaderView, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from datetime import datetime

from core.storage import StorageManager
from core.models import Supplier
from core.supplier_summaries import SupplierSummaryEngine
from core.utils import format_currency, format_datetime_arabic
from .table_items import DateTimeItem, NumericItem, sorted_table


class SupplierLedgerView(QWidget):
    """
    عرض حساب المورد
    Supplier ledger/account view
    """
    
    back_requested = Signal()
    
    def __init__(self, storage: StorageManager, supplier_id: str, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.supplier_id = supplier_id
        self.supplier = storage.get_supplier(supplier_id)
        self.summary_engine = SupplierSummaryEngine(storage)
        self.current_filter = "all"
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === الهيدر ===
        header = QHBoxLayout()
        
        title = QLabel(f"📋 حساب المورد: {self.supplier.name}")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        header.addWidget(title)
        
        header.addStretch()
        
        # فلتر الفترة
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("📅 اليوم", "today")
        self.filter_combo.addItem("📆 هذا الشهر", "month")
        self.filter_combo.addItem("🗓️ الكل", "all")
        self.filter_combo.setCurrentIndex(2)
        self.filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        header.addWidget(QLabel("الفترة:"))
        header.addWidget(self.filter_combo)
        
        # زر إضافة دفعة
        payment_btn = QPushButton("💰 إضافة دفعة")
        payment_btn.clicked.connect(self.add_payment)
        header.addWidget(payment_btn)
        
        # زر تصدير
        export_btn = QPushButton("📤 تصدير")
        export_btn.clicked.connect(self.export_ledger)
        header.addWidget(export_btn)
        
        # زر رجوع
        back_btn = QPushButton("← رجوع")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        
        layout.addLayout(header)
        
        # === بطاقات الملخص ===
        summary_layout = QHBoxLayout()
        
        self.purchases_card = self._create_stat_card("🛒 إجمالي المشتريات الآجلة", "0.00 شيكل", "#3b82f6")
        summary_layout.addWidget(self.purchases_card)
        
        self.payments_card = self._create_stat_card("💰 إجمالي الدفعات", "0.00 شيكل", "#10b981")
        summary_layout.addWidget(self.payments_card)
        
        self.balance_card = self._create_stat_card("📊 الرصيد المستحق", "0.00 شيكل", "#ef4444")
        summary_layout.addWidget(self.balance_card)
        
        layout.addLayout(summary_layout)
        
        # === جدول الحساب ===
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "التاريخ", "النوع", "الوصف", "المبلغ", "الرصيد التراكمي"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
    
    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """إنشاء بطاقة إحصائية"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 10px;
                padding: 15px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 11))
        title_label.setStyleSheet("color: #ffffff;")
        card_layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setFont(QFont("Arial", 16, QFont.Bold))
        value_label.setStyleSheet("color: #ffffff;")
        value_label.setObjectName("value_label")
        card_layout.addWidget(value_label)
        
        return card
    
    def _update_card_value(self, card: QFrame, value: str):
        """تحديث قيمة البطاقة"""
        value_label = card.findChild(QLabel, "value_label")
        if value_label:
            value_label.setText(value)
    
    def load_data(self):
        """تحميل وعرض البيانات"""
        # حساب الملخص
        summary = self.summary_engine.calculate_supplier_summary(self.supplier_id)
        
        self._update_card_value(self.purchases_card, format_currency(summary.total_purchases_decimal))
        self._update_card_value(self.payments_card, format_currency(summary.total_payments_decimal))
        self._update_card_value(self.balance_card, format_currency(summary.balance_decimal))
        
        # الحصول على الرصيد التراكمي
        running_entries = self.summary_engine.get_supplier_running_balance(self.supplier_id)
        
        # تصفية حسب الفترة
        now = datetime.now()
        if self.current_filter == "today":
            running_entries = [
                e for e in running_entries
                if datetime.fromisoformat(e['date']).date() == now.date()
            ]
        elif self.current_filter == "month":
            running_entries = [
                e for e in running_entries
                if datetime.fromisoformat(e['date']).year == now.year
                and datetime.fromisoformat(e['date']).month == now.month
            ]
        
        # عرض في الجدول — الافتراضي: التاريخ تنازلياً (الأحدث أولاً)
        with sorted_table(self.table, column=0, order=Qt.DescendingOrder):
            self.table.setRowCount(len(running_entries))

            for row, entry in enumerate(running_entries):
                # التاريخ — ترتيب زمني لا نصّي
                dt = datetime.fromisoformat(entry['date'])
                self.table.setItem(row, 0, DateTimeItem(
                    format_datetime_arabic(dt), dt))

                # النوع
                type_text = "🛒 شراء" if entry['type'] == 'purchase' else "💰 دفعة"
                self.table.setItem(row, 1, QTableWidgetItem(type_text))

                # الوصف
                self.table.setItem(row, 2, QTableWidgetItem(entry['description']))

                # المبلغ — ترتيب رقمي
                amount_item = NumericItem(
                    format_currency(entry['amount']), entry['amount'])
                amount_item.setFont(QFont("Arial", 11, QFont.Bold))
                amount_item.setForeground(
                    Qt.red if entry['type'] == 'purchase' else Qt.darkGreen)
                self.table.setItem(row, 3, amount_item)

                # الرصيد التراكمي — يُرتَّب زمنياً لا بقيمته، لأنه تراكمي
                # فلا معنى له إلا بالترتيب الزمني
                balance_item = DateTimeItem(
                    format_currency(entry['running_balance']), dt)
                balance_item.setFont(QFont("Arial", 11, QFont.Bold))
                balance_item.setForeground(
                    Qt.red if entry['running_balance'] > 0 else Qt.darkGreen)
                self.table.setItem(row, 4, balance_item)

    def on_filter_changed(self):
        """تغيير الفلتر"""
        self.current_filter = self.filter_combo.currentData()
        self.load_data()
    
    def add_payment(self):
        """إضافة دفعة"""
        from .dialogs import AddSupplierPaymentDialog
        
        summary = self.storage.get_supplier_summary(self.supplier_id)
        dialog = AddSupplierPaymentDialog(self.supplier, summary.balance_decimal, self)
        
        if dialog.exec():
            try:
                self.storage.add_supplier_payment(dialog.payment)
                self.summary_engine.recalculate_all_summaries()
                self.load_data()
                QMessageBox.information(self, "نجح", "تم إضافة الدفعة بنجاح")
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في إضافة الدفعة: {str(e)}")
    
    def export_ledger(self):
        """تصدير كشف الحساب"""
        from PySide6.QtWidgets import QFileDialog
        
        # اختيار صيغة التصدير
        path, _ = QFileDialog.getSaveFileName(
            self, "تصدير كشف حساب المورد",
            f"كشف_حساب_{self.supplier.name}",
            "CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if not path:
            return
        
        try:
            running_entries = self.summary_engine.get_supplier_running_balance(self.supplier_id)
            
            if path.endswith('.csv'):
                import csv
                with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["التاريخ", "النوع", "الوصف", "المبلغ", "الرصيد التراكمي"])
                    for entry in running_entries:
                        dt = datetime.fromisoformat(entry['date'])
                        writer.writerow([
                            format_datetime_arabic(dt),
                            "شراء" if entry['type'] == 'purchase' else "دفعة",
                            entry['description'],
                            f"{entry['amount']:.2f}",
                            f"{entry['running_balance']:.2f}"
                        ])
            
            elif path.endswith('.json'):
                import json
                export_data = {
                    "supplier": self.supplier.to_dict(),
                    "summary": self.summary_engine.calculate_supplier_summary(self.supplier_id).to_dict(),
                    "entries": [
                        {
                            "date": entry['date'],
                            "type": entry['type'],
                            "description": entry['description'],
                            "amount": str(entry['amount']),
                            "running_balance": str(entry['running_balance'])
                        }
                        for entry in running_entries
                    ]
                }
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "نجح", f"تم تصدير كشف الحساب إلى:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في التصدير: {str(e)}")
