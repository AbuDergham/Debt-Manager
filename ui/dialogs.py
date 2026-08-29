"""
نوافذ الحوار - Dialogs
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, QComboBox, QDateTimeEdit, QLabel, QMessageBox, QFileDialog, QTextEdit
from PySide6.QtCore import Qt, QDateTime, QDate
from PySide6.QtGui import QDoubleValidator
from decimal import Decimal
from datetime import datetime
from core.models import Entry, PaymentMethod, EntryType, Supplier, SupplierPayment
from core.utils import validate_customer_id


class AddCustomerDialog(QDialog):
    """
    نافذة إضافة عميل جديد
    Add customer dialog
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إضافة عميل جديد")
        self.setModal(True)
        self.setup_ui()
        
        # النتائج
        self.customer_id = None
        self.customer_name = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QFormLayout()
        
        # حقل الاسم
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("أدخل اسم العميل")
        layout.addRow("الاسم:", self.name_input)
        
        # حقل المعرف (اختياري - سيتم توليده تلقائياً من الاسم)
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("سيتم توليده تلقائياً من الاسم")
        layout.addRow("المعرف:", self.id_input)
        
        # حد الائتمان (اختياري - الافتراضي 0)
        self.credit_limit_input = QLineEdit()
        self.credit_limit_input.setPlaceholderText("0 = غير محدود")
        self.credit_limit_input.setText("0")
        validator = QDoubleValidator(0.0, 999999.99, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.credit_limit_input.setValidator(validator)
        layout.addRow("حد الائتمان:", self.credit_limit_input)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        self.save_button = QPushButton("حفظ")
        self.save_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
    
    def accept(self):
        """التحقق من البيانات والحفظ"""
        name = self.name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم العميل")
            return
        
        # إنشاء المعرف تلقائياً إذا لم يتم إدخاله
        customer_id = self.id_input.text().strip()
        if not customer_id:
            # توليد معرف من الاسم (استبدال المسافات بـ _)
            customer_id = name.replace(" ", "_").lower()
            # إضافة رقم عشوائي في النهاية لضمان التفرد
            import random
            customer_id = f"{customer_id}_{random.randint(1000, 9999)}"
        
        # التحقق من صحة المعرف
        if not validate_customer_id(customer_id):
            QMessageBox.warning(
                self, "خطأ", 
                "المعرف غير صالح. يجب أن يحتوي على حروف وأرقام فقط."
            )
            return
        
        self.customer_id = customer_id
        self.customer_name = name
        
        # حد الائتمان
        credit_limit_text = self.credit_limit_input.text().strip()
        if credit_limit_text:
            try:
                self.credit_limit = Decimal(credit_limit_text)
                if self.credit_limit < 0:
                    QMessageBox.warning(self, "خطأ", "حد الائتمان يجب أن يكون صفر أو أكبر")
                    return
            except:
                QMessageBox.warning(self, "خطأ", "حد الائتمان غير صالح")
                return
        else:
            self.credit_limit = Decimal("0")
        
        super().accept()


class EditCustomerDialog(QDialog):
    """
    نافذة تعديل معلومات عميل
    Edit customer information dialog
    """
    
    def __init__(self, customer, parent=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle(f"تعديل معلومات العميل - {customer.name}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setup_ui()
        self.load_customer_data()
        
        # النتائج
        self.updated_customer = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QFormLayout()
        
        # الاسم
        self.name_input = QLineEdit()
        layout.addRow("الاسم:", self.name_input)
        
        # رقم الهاتف
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("مثال: 0599123456")
        layout.addRow("رقم الهاتف:", self.phone_input)
        
        # حد الائتمان
        self.credit_limit_input = QLineEdit()
        self.credit_limit_input.setPlaceholderText("0 = غير محدود")
        validator = QDoubleValidator(0.0, 999999.99, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.credit_limit_input.setValidator(validator)
        layout.addRow("حد الائتمان:", self.credit_limit_input)
        
        # ملاحظة توضيحية
        note_label = QLabel("💡 حد الائتمان هو الحد الأقصى للدين المسموح")
        note_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        note_label.setWordWrap(True)
        layout.addRow("", note_label)
        
        # الملاحظات
        from PySide6.QtWidgets import QTextEdit
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات داخلية عن العميل...")
        self.notes_input.setMaximumHeight(80)
        layout.addRow("الملاحظات:", self.notes_input)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
    
    def load_customer_data(self):
        """تحميل بيانات العميل الحالية"""
        self.name_input.setText(self.customer.name)
        self.phone_input.setText(self.customer.phone if self.customer.phone else "")
        
        # حد الائتمان
        credit_limit = float(self.customer.credit_limit_decimal)
        if credit_limit > 0:
            self.credit_limit_input.setText(f"{credit_limit:.2f}")
        else:
            self.credit_limit_input.setText("0")
        
        self.notes_input.setPlainText(self.customer.notes if self.customer.notes else "")
    
    def accept(self):
        """التحقق من البيانات والحفظ"""
        name = self.name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم العميل")
            return
        
        phone = self.phone_input.text().strip()
        
        # حد الائتمان
        credit_limit_text = self.credit_limit_input.text().strip()
        if credit_limit_text:
            try:
                credit_limit = Decimal(credit_limit_text)
                if credit_limit < 0:
                    QMessageBox.warning(self, "خطأ", "حد الائتمان يجب أن يكون صفر أو أكبر")
                    return
            except:
                QMessageBox.warning(self, "خطأ", "حد الائتمان غير صالح")
                return
        else:
            credit_limit = Decimal("0")
        
        notes = self.notes_input.toPlainText().strip()
        
        # إنشاء كائن العميل المحدث
        from core.models import Customer
        self.updated_customer = Customer(
            id=self.customer.id,
            name=name,
            phone=phone,
            credit_limit=f"{credit_limit:.2f}",
            notes=notes
        )
        
        super().accept()


class AddEntryDialog(QDialog):
    """
    نافذة إضافة إدخال (شراء أو دفع)
    Add entry dialog
    """
    
    def __init__(self, customer_id: str, customer_name: str, customer=None, current_balance=None, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.customer = customer  # كائن العميل الكامل
        self.current_balance = current_balance  # الرصيد الحالي
        self.setWindowTitle(f"إضافة إدخال - {customer_name}")
        self.setModal(True)
        self.setup_ui()
        
        # النتائج
        self.entry = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QFormLayout()
        
        # نوع الإدخال
        self.type_combo = QComboBox()
        self.type_combo.addItem("دين", "purchase")
        self.type_combo.addItem("دفع", "payment")
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addRow("نوع الإدخال:", self.type_combo)
        
        # المبلغ
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        validator = QDoubleValidator(0.01, 999999.99, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.amount_input.setValidator(validator)
        layout.addRow("المبلغ:", self.amount_input)
        
        # الوصف
        self.desc_input = QLineEdit()
        self.desc_input.setText("أغراض")  # القيمة الافتراضية
        layout.addRow("الوصف:", self.desc_input)
        
        # طريقة الدفع (مخفية افتراضياً للدين)
        self.payment_method_label = QLabel("طريقة الدفع:")
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItem("نقداً", "cash")
        self.payment_method_combo.addItem("تحويل", "transfer")
        self.payment_method_row = layout.rowCount()
        layout.addRow(self.payment_method_label, self.payment_method_combo)
        
        # إخفاء طريقة الدفع للدين (فقط للدفع)
        self.payment_method_label.hide()
        self.payment_method_combo.hide()
        
        # التاريخ والوقت
        self.datetime_edit = QDateTimeEdit()
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        # Format reversed to compensate for RTL reversal: "AP mm:hh dd/MM/yyyy" becomes "yyyy/MM/dd hh:mm AP" after RTL
        self.datetime_edit.setDisplayFormat("AP mm:hh dd/MM/yyyy")
        self.datetime_edit.setAlignment(Qt.AlignLeft)
        layout.addRow("التاريخ والوقت:", self.datetime_edit)
        
        # الملاحظات الداخلية
        from PySide6.QtWidgets import QTextEdit
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات داخلية (اختياري)")
        self.notes_input.setMaximumHeight(60)
        layout.addRow("الملاحظات:", self.notes_input)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        self.save_button = QPushButton("حفظ")
        self.save_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
    
    def on_type_changed(self, index):
        """تغيير الوصف الافتراضي حسب النوع وإظهار/إخفاء طريقة الدفع"""
        entry_type = self.type_combo.currentData()
        if entry_type == "purchase":
            self.desc_input.setText("أغراض")
            # إخفاء طريقة الدفع للدين
            self.payment_method_label.hide()
            self.payment_method_combo.hide()
        elif entry_type == "payment":
            self.desc_input.setText("دفعة")
            # إظهار طريقة الدفع للدفع
            self.payment_method_label.show()
            self.payment_method_combo.show()
    
    def accept(self):
        """التحقق من البيانات والحفظ"""
        # التحقق من المبلغ
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
        
        # الحصول على البيانات
        entry_type: EntryType = self.type_combo.currentData()
        desc = self.desc_input.text().strip() or "بدون وصف"
        payment_method: PaymentMethod = self.payment_method_combo.currentData()
        dt = self.datetime_edit.dateTime().toPython()
        notes = self.notes_input.toPlainText().strip()
        
        # فحص حد الائتمان للديون فقط
        if entry_type == "purchase" and self.customer and self.current_balance is not None:
            credit_limit = self.customer.credit_limit_decimal
            
            # إذا كان هناك حد ائتمان محدد (ليس صفر = غير محدود)
            if credit_limit > 0:
                new_balance = self.current_balance + amount
                
                if new_balance > credit_limit:
                    # عرض تحذير
                    from core.utils import format_currency
                    warning_msg = (
                        f"⚠️ تحذير: تجاوز حد الائتمان!\n\n"
                        f"الرصيد الحالي: {format_currency(self.current_balance)}\n"
                        f"المبلغ المطلوب: {format_currency(amount)}\n"
                        f"الرصيد الجديد: {format_currency(new_balance)}\n"
                        f"حد الائتمان المسموح: {format_currency(credit_limit)}\n\n"
                        f"التجاوز: {format_currency(new_balance - credit_limit)}\n\n"
                        f"هل تريد المتابعة رغم ذلك؟"
                    )
                    
                    reply = QMessageBox.warning(
                        self,
                        "⚠️ تحذير حد الائتمان",
                        warning_msg,
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply == QMessageBox.No:
                        return
        
        # إنشاء الإدخال
        self.entry = Entry(
            customer_id=self.customer_id,
            type=entry_type,
            amount=f"{amount:.2f}",
            date=dt.isoformat(),
            desc=desc,
            pay_method=payment_method,
            notes=notes
        )
        
        super().accept()


class EditEntryDialog(QDialog):
    """
    نافذة تعديل إدخال موجود
    Edit existing entry dialog
    """
    
    def __init__(self, entry: Entry, customer_name: str, parent=None):
        super().__init__(parent)
        self.original_entry = entry
        self.customer_name = customer_name
        self.setWindowTitle(f"تعديل إدخال - {customer_name}")
        self.setModal(True)
        self.setup_ui()
        
        # تعبئة البيانات الحالية
        self.load_entry_data()
        
        # النتائج
        self.updated_entry = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QFormLayout()
        
        # نوع الإدخال (للعرض فقط)
        self.type_label = QLabel("دين" if self.original_entry.type == "purchase" else "دفع")
        layout.addRow("نوع الإدخال:", self.type_label)
        
        # المبلغ
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        validator = QDoubleValidator(0.01, 999999.99, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.amount_input.setValidator(validator)
        layout.addRow("المبلغ:", self.amount_input)
        
        # الوصف
        self.desc_input = QLineEdit()
        layout.addRow("الوصف:", self.desc_input)
        
        # طريقة الدفع (فقط للدفع)
        if self.original_entry.type == "payment":
            self.payment_method_combo = QComboBox()
            self.payment_method_combo.addItem("نقداً", "cash")
            self.payment_method_combo.addItem("تحويل", "transfer")
            layout.addRow("طريقة الدفع:", self.payment_method_combo)
        
        # التاريخ والوقت
        self.datetime_edit = QDateTimeEdit()
        self.datetime_edit.setCalendarPopup(True)
        # Format reversed to compensate for RTL reversal
        self.datetime_edit.setDisplayFormat("AP mm:hh dd/MM/yyyy")
        self.datetime_edit.setAlignment(Qt.AlignLeft)
        layout.addRow("التاريخ والوقت:", self.datetime_edit)
        
        # الملاحظات الداخلية
        from PySide6.QtWidgets import QTextEdit
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات داخلية (اختياري)")
        self.notes_input.setMaximumHeight(60)
        layout.addRow("الملاحظات:", self.notes_input)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        self.save_button = QPushButton("حفظ")
        self.save_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
    
    def load_entry_data(self):
        """تحميل بيانات الإدخال الحالية"""
        self.amount_input.setText(self.original_entry.amount)
        self.desc_input.setText(self.original_entry.desc)
        self.notes_input.setPlainText(self.original_entry.notes if self.original_entry.notes else "")
        
        if self.original_entry.type == "payment":
            index = 0 if self.original_entry.pay_method == "cash" else 1
            self.payment_method_combo.setCurrentIndex(index)
        
        # تحويل ISO datetime إلى QDateTime
        dt = datetime.fromisoformat(self.original_entry.date)
        from PySide6.QtCore import QDateTime, QDate, QTime
        qdate = QDate(dt.year, dt.month, dt.day)
        qtime = QTime(dt.hour, dt.minute, dt.second if hasattr(dt, 'second') else 0)
        qdt = QDateTime(qdate, qtime)
        self.datetime_edit.setDateTime(qdt)
    
    def accept(self):
        """التحقق من البيانات والحفظ"""
        # التحقق من المبلغ
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
        
        # الحصول على البيانات
        desc = self.desc_input.text().strip() or "بدون وصف"
        notes = self.notes_input.toPlainText().strip()
        
        payment_method = self.original_entry.pay_method
        if self.original_entry.type == "payment":
            payment_method = self.payment_method_combo.currentData()
        
        dt = self.datetime_edit.dateTime().toPython()
        
        # إنشاء الإدخال المحدث
        self.updated_entry = Entry(
            customer_id=self.original_entry.customer_id,
            type=self.original_entry.type,
            amount=f"{amount:.2f}",
            date=dt.isoformat(),
            desc=desc,
            pay_method=payment_method,
            notes=notes
        )
        
        super().accept()


class ExportDialog(QDialog):
    """
    نافذة تصدير البيانات
    Export dialog
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تصدير البيانات")
        self.setModal(True)
        self.setup_ui()
        
        # النتائج
        self.export_path = None
        self.export_format = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout()
        
        # التنسيق
        format_layout = QFormLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItem("CSV", "csv")
        self.format_combo.addItem("JSON", "json")
        self.format_combo.addItem("PDF", "pdf")
        self.format_combo.addItem("Excel (xlsx)", "excel")
        format_layout.addRow("التنسيق:", self.format_combo)
        
        layout.addLayout(format_layout)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        self.export_button = QPushButton("تصدير")
        self.export_button.clicked.connect(self.select_export_path)
        
        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addWidget(self.cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def select_export_path(self):
        """اختيار مسار التصدير"""
        format_type = self.format_combo.currentData()
        
        if format_type == "csv":
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ كـ CSV", "", "CSV Files (*.csv)"
            )
        elif format_type == "json":
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ كـ JSON", "", "JSON Files (*.json)"
            )
        elif format_type == "pdf":
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ كـ PDF", "", "PDF Files (*.pdf)"
            )
        elif format_type == "excel":
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ كـ Excel", "", "Excel Files (*.xlsx)"
            )
        else:
            path = None
        
        if path:
            self.export_path = path
            self.export_format = format_type
            self.accept()


class AppLockDialog(QDialog):
    """
    نافذة قفل التطبيق
    App lock dialog
    """
    
    def __init__(self, mode: str = "setup", parent=None):
        """
        Args:
            mode: "setup" لإعداد كلمة المرور، "verify" للتحقق منها
        """
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle("قفل التطبيق" if mode == "setup" else "فتح القفل")
        self.setModal(True)
        self.setup_ui()
        
        # النتائج
        self.password = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout()
        
        if self.mode == "setup":
            # إعداد كلمة مرور جديدة
            form_layout = QFormLayout()
            
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("كلمة المرور:", self.password_input)
            
            self.confirm_input = QLineEdit()
            self.confirm_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("تأكيد كلمة المرور:", self.confirm_input)
            
            layout.addLayout(form_layout)
        else:
            # التحقق من كلمة المرور
            form_layout = QFormLayout()
            
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("كلمة المرور:", self.password_input)
            
            layout.addLayout(form_layout)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("موافق")
        self.ok_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("إلغاء")
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def accept(self):
        """التحقق من البيانات"""
        password = self.password_input.text()
        
        if not password:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال كلمة المرور")
            return
        
        if self.mode == "setup":
            confirm = self.confirm_input.text()
            if password != confirm:
                QMessageBox.warning(self, "خطأ", "كلمتا المرور غير متطابقتين")
                return
        
        self.password = password
        super().accept()


class AddSupplierDialog(QDialog):
    """
    نافذة إضافة مورد جديد
    Add supplier dialog
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إضافة مورد جديد")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setup_ui()
        
        # النتائج
        self.supplier = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QFormLayout()
        
        # حقل الاسم
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("أدخل اسم المورد")
        layout.addRow("الاسم:", self.name_input)
        
        # رقم الهاتف
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("مثال: 0599123456")
        layout.addRow("رقم الهاتف:", self.phone_input)
        
        # الملاحظات
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات عن المورد...")
        self.notes_input.setMaximumHeight(80)
        layout.addRow("الملاحظات:", self.notes_input)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
    
    def accept(self):
        """التحقق من البيانات والحفظ"""
        name = self.name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم المورد")
            return
        
        # توليد معرف فريد
        import random
        supplier_id = f"SUP_{name.replace(' ', '_')}_{random.randint(1000, 9999)}"
        
        phone = self.phone_input.text().strip()
        notes = self.notes_input.toPlainText().strip()
        
        self.supplier = Supplier(
            id=supplier_id,
            name=name,
            phone=phone,
            notes=notes
        )
        
        super().accept()


class EditSupplierDialog(QDialog):
    """
    نافذة تعديل معلومات مورد
    Edit supplier information dialog
    """
    
    def __init__(self, supplier: Supplier, parent=None):
        super().__init__(parent)
        self.supplier = supplier
        self.setWindowTitle(f"تعديل معلومات المورد - {supplier.name}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setup_ui()
        self.load_supplier_data()
        
        # النتائج
        self.updated_supplier = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QFormLayout()
        
        # الاسم
        self.name_input = QLineEdit()
        layout.addRow("الاسم:", self.name_input)
        
        # رقم الهاتف
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("مثال: 0599123456")
        layout.addRow("رقم الهاتف:", self.phone_input)
        
        # الملاحظات
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات عن المورد...")
        self.notes_input.setMaximumHeight(80)
        layout.addRow("الملاحظات:", self.notes_input)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        # التخطيط الرئيسي
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
    
    def load_supplier_data(self):
        """تحميل بيانات المورد الحالية"""
        self.name_input.setText(self.supplier.name)
        self.phone_input.setText(self.supplier.phone if self.supplier.phone else "")
        self.notes_input.setPlainText(self.supplier.notes if self.supplier.notes else "")
    
    def accept(self):
        """التحقق من البيانات والحفظ"""
        name = self.name_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "خطأ", "يرجى إدخال اسم المورد")
            return
        
        phone = self.phone_input.text().strip()
        notes = self.notes_input.toPlainText().strip()
        
        self.updated_supplier = Supplier(
            id=self.supplier.id,
            name=name,
            phone=phone,
            notes=notes
        )
        
        super().accept()


class AddSupplierPaymentDialog(QDialog):
    """
    نافذة إضافة دفعة لمورد
    Add supplier payment dialog
    """
    
    def __init__(self, supplier: Supplier, current_balance=None, parent=None):
        super().__init__(parent)
        self.supplier = supplier
        self.current_balance = current_balance
        self.setWindowTitle(f"إضافة دفعة - {supplier.name}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setup_ui()
        
        # النتائج
        self.payment = None
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QFormLayout()
        
        # عرض الرصيد الحالي
        if self.current_balance is not None:
            from core.utils import format_currency
            balance_label = QLabel(f"💰 الرصيد الحالي: {format_currency(self.current_balance)}")
            balance_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ef4444; padding: 10px;")
            layout.addRow("", balance_label)
        
        # المبلغ
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        validator = QDoubleValidator(0.01, 999999.99, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.amount_input.setValidator(validator)
        layout.addRow("المبلغ:", self.amount_input)
        
        # طريقة الدفع
        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItem("نقداً", "cash")
        self.payment_method_combo.addItem("تحويل", "transfer")
        self.payment_method_combo.addItem("شيك", "check")
        layout.addRow("طريقة الدفع:", self.payment_method_combo)
        
        # التاريخ والوقت
        self.datetime_edit = QDateTimeEdit()
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.datetime_edit.setDisplayFormat("AP mm:hh dd/MM/yyyy")
        self.datetime_edit.setAlignment(Qt.AlignLeft)
        layout.addRow("التاريخ:", self.datetime_edit)
        
        # الملاحظات
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("ملاحظات (اختياري)")
        self.notes_input.setMaximumHeight(60)
        layout.addRow("الملاحظات:", self.notes_input)
        
        # الأزرار
        buttons_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 حفظ")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(buttons_layout)
        
        self.setLayout(main_layout)
    
    def accept(self):
        """التحقق من البيانات والحفظ"""
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
        
        from core.utils import generate_payment_id
        
        payment_method = self.payment_method_combo.currentData()
        dt = self.datetime_edit.dateTime().toPython()
        notes = self.notes_input.toPlainText().strip()
        
        self.payment = SupplierPayment(
            id=generate_payment_id(),
            supplier_id=self.supplier.id,
            amount=f"{amount:.2f}",
            date=dt.isoformat(),
            payment_method=payment_method,
            notes=notes
        )
        
        super().accept()
