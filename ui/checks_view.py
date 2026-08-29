"""
عرض نظام الشيكات
Checks management view
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QComboBox, QHeaderView, QFrame, QMessageBox, QDateEdit, QFormLayout, QDialog, QTextEdit
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QFont, QDoubleValidator
from decimal import Decimal
from datetime import datetime, timedelta

from core.storage import StorageManager
from core.models import Check
from core.supplier_summaries import SupplierSummaryEngine
from core.utils import format_currency, generate_check_id


class AddCheckDialog(QDialog):
    """نافذة إضافة شيك جديد"""
    
    def __init__(self, suppliers, parent=None):
        super().__init__(parent)
        self.suppliers = suppliers
        self.setWindowTitle("إضافة شيك جديد")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setup_ui()
        
        self.check = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QFormLayout()
        
        # رقم الشيك
        self.check_number_input = QLineEdit()
        self.check_number_input.setPlaceholderText("رقم الشيك")
        layout.addRow("رقم الشيك:", self.check_number_input)
        
        # اسم البنك
        self.bank_input = QLineEdit()
        self.bank_input.setPlaceholderText("اسم البنك")
        layout.addRow("البنك:", self.bank_input)
        
        # المبلغ
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        self.amount_input.setValidator(QDoubleValidator(0.01, 999999.99, 2))
        layout.addRow("المبلغ:", self.amount_input)
        
        # الاتجاه
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("صادر (لمورد)", "outgoing")
        self.direction_combo.addItem("وارد", "incoming")
        self.direction_combo.currentIndexChanged.connect(self.on_direction_changed)
        layout.addRow("الاتجاه:", self.direction_combo)
        
        # الجهة (مورد)
        self.party_combo = QComboBox()
        for supplier in self.suppliers:
            self.party_combo.addItem(supplier.name, supplier.id)
        
        # إضافة "جهة أخرى" كخيار
        self.party_combo.addItem("جهة أخرى...", "other")
        self.party_combo.currentIndexChanged.connect(self.on_party_changed)
        layout.addRow("الجهة:", self.party_combo)
        
        # اسم الجهة (يظهر فقط عند اختيار "جهة أخرى")
        self.party_name_input = QLineEdit()
        self.party_name_input.setPlaceholderText("اسم الجهة")
        self.party_name_input.hide()
        self.party_name_label = QLabel("اسم الجهة:")
        self.party_name_label.hide()
        layout.addRow(self.party_name_label, self.party_name_input)
        
        # تاريخ الإصدار
        self.issue_date_edit = QDateEdit()
        self.issue_date_edit.setCalendarPopup(True)
        self.issue_date_edit.setDate(QDate.currentDate())
        self.issue_date_edit.setDisplayFormat("dd/MM/yyyy")
        layout.addRow("تاريخ الإصدار:", self.issue_date_edit)
        
        # تاريخ الاستحقاق
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate().addMonths(1))
        self.due_date_edit.setDisplayFormat("dd/MM/yyyy")
        layout.addRow("تاريخ الاستحقاق:", self.due_date_edit)
        
        # الملاحظات
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات (اختياري)")
        self.notes_input.setMaximumHeight(60)
        layout.addRow("الملاحظات:", self.notes_input)
        
        # الأزرار
        buttons = QHBoxLayout()
        save_btn = QPushButton("💾 حفظ")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons)
        self.setLayout(main_layout)
    
    def on_direction_changed(self):
        """تغيير الاتجاه"""
        pass
    
    def on_party_changed(self):
        """تغيير الجهة"""
        if self.party_combo.currentData() == "other":
            self.party_name_input.show()
            self.party_name_label.show()
        else:
            self.party_name_input.hide()
            self.party_name_label.hide()
    
    def accept(self):
        """التحقق والحفظ"""
        check_number = self.check_number_input.text().strip()
        if not check_number:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال رقم الشيك")
            return
        
        bank = self.bank_input.text().strip()
        if not bank:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم البنك")
            return
        
        amount_text = self.amount_input.text().strip()
        if not amount_text:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال المبلغ")
            return
        
        try:
            amount = Decimal(amount_text)
            if amount <= 0:
                QMessageBox.warning(self, "خطأ", "المبلغ يجب أن يكون أكبر من صفر")
                return
        except:
            QMessageBox.warning(self, "خطأ", "المبلغ غير صالح")
            return
        
        direction = self.direction_combo.currentData()
        party_id = self.party_combo.currentData()
        
        if party_id == "other":
            party_name = self.party_name_input.text().strip()
            if not party_name:
                QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم الجهة")
                return
            party_type = "other"
        else:
            party_name = self.party_combo.currentText()
            party_type = "supplier"
        
        issue_date = self.issue_date_edit.date().toPython()
        due_date = self.due_date_edit.date().toPython()
        notes = self.notes_input.toPlainText().strip()
        
        self.check = Check(
            id=generate_check_id(),
            check_number=check_number,
            bank_name=bank,
            amount=f"{amount:.2f}",
            issue_date=datetime(issue_date.year, issue_date.month, issue_date.day).isoformat(),
            due_date=datetime(due_date.year, due_date.month, due_date.day).isoformat(),
            status="pending",
            direction=direction,
            party_type=party_type,
            party_id=party_id if party_id != "other" else "",
            party_name=party_name,
            notes=notes
        )
        
        super().accept()


class ChecksView(QWidget):
    """
    عرض نظام الشيكات
    Checks management view
    """
    
    back_requested = Signal()
    
    def __init__(self, storage: StorageManager, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.summary_engine = SupplierSummaryEngine(storage)
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === الهيدر ===
        header = QHBoxLayout()
        
        title = QLabel("💳 نظام الشيكات")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(title)
        
        header.addStretch()
        
        # زر إضافة شيك
        add_btn = QPushButton("➕ إضافة شيك")
        add_btn.clicked.connect(self.add_check)
        header.addWidget(add_btn)
        
        # زر رجوع
        back_btn = QPushButton("← رجوع")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        
        layout.addLayout(header)
        
        # === بطاقات الملخص ===
        stats_layout = QHBoxLayout()
        
        self.pending_card = self._create_stat_card("⏳ شيكات معلقة", "0", "#f59e0b")
        stats_layout.addWidget(self.pending_card)
        
        self.pending_amount_card = self._create_stat_card("💰 مبلغ المعلقة", "0.00 شيكل", "#3b82f6")
        stats_layout.addWidget(self.pending_amount_card)
        
        self.cashed_card = self._create_stat_card("✅ شيكات مصروفة", "0", "#10b981")
        stats_layout.addWidget(self.cashed_card)
        
        self.upcoming_card = self._create_stat_card("🔔 تستحق خلال 7 أيام", "0", "#ef4444")
        stats_layout.addWidget(self.upcoming_card)
        
        layout.addLayout(stats_layout)
        
        # === الفلاتر ===
        filters_layout = QHBoxLayout()
        
        # فلتر الحالة
        filters_layout.addWidget(QLabel("الحالة:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("الكل", None)
        self.status_filter.addItem("⏳ معلق", "pending")
        self.status_filter.addItem("✅ مصروف", "cashed")
        self.status_filter.addItem("❌ مرتجع", "bounced")
        self.status_filter.currentIndexChanged.connect(self.filter_checks)
        filters_layout.addWidget(self.status_filter)
        
        # فلتر الاتجاه
        filters_layout.addWidget(QLabel("الاتجاه:"))
        self.direction_filter = QComboBox()
        self.direction_filter.addItem("الكل", None)
        self.direction_filter.addItem("صادر", "outgoing")
        self.direction_filter.addItem("وارد", "incoming")
        self.direction_filter.currentIndexChanged.connect(self.filter_checks)
        filters_layout.addWidget(self.direction_filter)
        
        filters_layout.addStretch()
        
        layout.addLayout(filters_layout)
        
        # === جدول الشيكات ===
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "رقم الشيك", "البنك", "المبلغ", "الجهة",
            "الاتجاه", "تاريخ الإصدار", "تاريخ الاستحقاق", "الحالة", "إجراء"
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
        """تحميل البيانات"""
        self.all_checks = self.storage.load_checks()
        self.update_stats()
        self.filter_checks()
    
    def update_stats(self):
        """تحديث الإحصائيات"""
        pending = [c for c in self.all_checks if c.status == "pending"]
        cashed = [c for c in self.all_checks if c.status == "cashed"]
        
        # شيكات تستحق خلال 7 أيام
        now = datetime.now()
        week_later = now + timedelta(days=7)
        upcoming = [
            c for c in pending
            if c.due_datetime <= week_later
        ]
        
        pending_amount = sum(c.amount_decimal for c in pending)
        
        self._update_card_value(self.pending_card, str(len(pending)))
        self._update_card_value(self.pending_amount_card, format_currency(pending_amount))
        self._update_card_value(self.cashed_card, str(len(cashed)))
        self._update_card_value(self.upcoming_card, str(len(upcoming)))
    
    def filter_checks(self):
        """تصفية الشيكات"""
        checks = self.all_checks.copy()
        
        status = self.status_filter.currentData()
        if status:
            checks = [c for c in checks if c.status == status]
        
        direction = self.direction_filter.currentData()
        if direction:
            checks = [c for c in checks if c.direction == direction]
        
        self.display_checks(checks)
    
    def display_checks(self, checks):
        """عرض الشيكات في الجدول"""
        self.table.setRowCount(len(checks))
        
        for row, check in enumerate(checks):
            # رقم الشيك
            num_item = QTableWidgetItem(check.check_number)
            num_item.setData(Qt.UserRole, check.id)
            self.table.setItem(row, 0, num_item)
            
            # البنك
            self.table.setItem(row, 1, QTableWidgetItem(check.bank_name))
            
            # المبلغ
            amount_item = QTableWidgetItem(format_currency(check.amount_decimal))
            amount_item.setFont(QFont("Arial", 11, QFont.Bold))
            self.table.setItem(row, 2, amount_item)
            
            # الجهة
            self.table.setItem(row, 3, QTableWidgetItem(check.party_name))
            
            # الاتجاه
            dir_text = "صادر ↗️" if check.direction == "outgoing" else "وارد ↙️"
            self.table.setItem(row, 4, QTableWidgetItem(dir_text))
            
            # تاريخ الإصدار
            self.table.setItem(row, 5, QTableWidgetItem(
                check.issue_datetime.strftime("%Y/%m/%d")
            ))
            
            # تاريخ الاستحقاق
            due_item = QTableWidgetItem(check.due_datetime.strftime("%Y/%m/%d"))
            # تلوين إذا قرب الاستحقاق
            if check.is_pending:
                days_left = (check.due_datetime - datetime.now()).days
                if days_left <= 0:
                    due_item.setForeground(Qt.red)
                elif days_left <= 7:
                    due_item.setForeground(Qt.darkYellow)
            self.table.setItem(row, 6, due_item)
            
            # الحالة
            status_map = {
                "pending": "⏳ معلق",
                "cashed": "✅ مصروف",
                "bounced": "❌ مرتجع"
            }
            status_item = QTableWidgetItem(status_map.get(check.status, check.status))
            self.table.setItem(row, 7, status_item)
            
            # زر إجراء
            if check.is_pending:
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                cash_btn = QPushButton("✅ صرف")
                cash_btn.setStyleSheet("background: #d1fae5; border: none; padding: 4px 8px; border-radius: 3px;")
                cash_btn.clicked.connect(lambda checked, cid=check.id: self.cash_check(cid))
                actions_layout.addWidget(cash_btn)
                
                bounce_btn = QPushButton("❌ رجع")
                bounce_btn.setStyleSheet("background: #fee2e2; border: none; padding: 4px 8px; border-radius: 3px;")
                bounce_btn.clicked.connect(lambda checked, cid=check.id: self.bounce_check(cid))
                actions_layout.addWidget(bounce_btn)
                
                self.table.setCellWidget(row, 8, actions_widget)
            else:
                self.table.setItem(row, 8, QTableWidgetItem("-"))
    
    def add_check(self):
        """إضافة شيك جديد"""
        suppliers = self.storage.load_suppliers()
        dialog = AddCheckDialog(suppliers, self)
        
        if dialog.exec():
            try:
                self.storage.add_check(dialog.check)
                self.load_data()
                QMessageBox.information(self, "نجح", "تم إضافة الشيك بنجاح")
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في إضافة الشيك: {str(e)}")
    
    def cash_check(self, check_id: str):
        """صرف شيك"""
        check = self.storage.get_check(check_id)
        if not check:
            return
        
        reply = QMessageBox.question(
            self, "تأكيد صرف الشيك",
            f"هل تريد صرف الشيك رقم {check.check_number}؟\n"
            f"المبلغ: {format_currency(check.amount_decimal)}\n"
            f"الجهة: {check.party_name}\n\n"
            f"سيتم خصم المبلغ من رصيد الجهة.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.storage.update_check_status(check_id, "cashed")
                # إعادة حساب ملخصات الموردين
                self.summary_engine.recalculate_all_summaries()
                self.load_data()
                QMessageBox.information(self, "نجح", "تم صرف الشيك بنجاح")
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في صرف الشيك: {str(e)}")
    
    def bounce_check(self, check_id: str):
        """إرجاع شيك"""
        check = self.storage.get_check(check_id)
        if not check:
            return
        
        reply = QMessageBox.question(
            self, "تأكيد إرجاع الشيك",
            f"هل تريد إرجاع الشيك رقم {check.check_number}؟\n"
            f"المبلغ: {format_currency(check.amount_decimal)}\n"
            f"الجهة: {check.party_name}\n\n"
            f"لن يتم خصم المبلغ من رصيد الجهة.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.storage.update_check_status(check_id, "bounced")
                self.load_data()
                QMessageBox.information(self, "نجح", "تم إرجاع الشيك")
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في إرجاع الشيك: {str(e)}")
    
    def refresh(self):
        """تحديث البيانات"""
        self.load_data()
