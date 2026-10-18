"""
طبقة التخزين مع الكتابة الذرية
Storage layer with atomic file operations
"""
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import List, Dict, Any, Optional
from .models import (
    Customer, Entry, Summary,
    Supplier, PurchaseOrder, PurchaseItem,
    SupplierPayment, SupplierSummary, Check
)
from .utils import ensure_data_folder
from .audit import AuditManager, ActionType, EntityType
from .backup import create_backup


def atomic_write_json(path: Path, data: Any) -> None:
    """
    كتابة ملف JSON بشكل ذري
    Atomic JSON file write
    
    الخطوات:
    1. كتابة البيانات إلى ملف مؤقت
    2. نقل/إعادة تسمية الملف المؤقت ليحل محل الملف الأصلي
    
    هذا يضمن عدم حدوث تلف في البيانات في حالة انقطاع التيار الكهربائي
    """
    path = Path(path)
    
    # إنشاء المجلد الأب إذا لم يكن موجوداً
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # كتابة إلى ملف مؤقت في نفس المجلد
    # Writing to a temp file in the same directory ensures atomic rename
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        suffix='.tmp',
        text=True
    )
    
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # نقل الملف المؤقت ليحل محل الملف الأصلي (عملية ذرية)
        # Atomic rename operation
        os.replace(temp_path, path)
    except Exception as e:
        # حذف الملف المؤقت في حالة حدوث خطأ
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except:
            pass
        raise e


def atomic_append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """
    إضافة سطر إلى ملف JSONL بشكل ذري
    Atomic JSONL line append
    
    ملاحظة: في Windows، إضافة سطر واحد إلى ملف نصي عادة ما تكون عملية ذرية
    Note: On Windows, appending a single line to a text file is typically atomic
    """
    path = Path(path)
    
    # إنشاء المجلد الأب إذا لم يكن موجوداً
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # تحويل السجل إلى JSON
    line = json.dumps(record, ensure_ascii=False)
    
    # الإضافة إلى الملف
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def read_json(path: Path, default: Any = None) -> Any:
    """
    قراءة ملف JSON
    Read JSON file
    
    Args:
        path: مسار الملف
        default: القيمة الافتراضية إذا لم يكن الملف موجوداً
    """
    path = Path(path)
    
    if not path.exists():
        return default
    
    try:
        # utf-8-sig يقرأ الملفات بعلامة BOM وبدونها بنفس النتيجة.
        # حادثة واقعية: محرّر نصوص خارجي أضاف BOM إلى checks.json فمات
        # التطبيق عند الإقلاع، رغم أن المحتوى كان JSON صالحاً تماماً.
        # للقراءة فقط — استعماله في الكتابة يضيف BOM لكل الملفات.
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")


def atomic_write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    """
    كتابة ملف JSONL كاملاً بشكل ذري
    Atomic full-file JSONL write

    تُستخدم عند التعديل أو الحذف: JSONL صيغة append-only، فلا يمكن تعديل
    سطر واحد في مكانه — يجب إعادة كتابة الملف كله.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix='.tmp', text=True)

    try:
        # os.fdopen يتملّك الواصف ويغلقه — لا نفتح المسار مرة ثانية
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """
    قراءة جميع السجلات من ملف JSONL
    Read all records from JSONL file
    """
    path = Path(path)
    
    if not path.exists():
        return []
    
    records = []
    # utf-8-sig: يتحمّل علامة BOM التي قد يضيفها محرّر نصوص خارجي.
    # للقراءة فقط — الكتابة تبقى utf-8 بلا BOM.
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num} in {path}: {e}")
    
    return records


class StorageManager:
    """
    مدير التخزين الرئيسي
    Main storage manager
    """
    
    def __init__(self, data_folder: Optional[Path] = None):
        """
        تهيئة مدير التخزين - Initialize storage manager

        Args:
            data_folder: مجلد بيانات مخصص (للاختبارات).
                         الافتراضي: مجلد الإنتاج.
        """
        self.data_folder = ensure_data_folder(data_folder)

        self.customers_file = self.data_folder / "customers.json"
        self.entries_file = self.data_folder / "entries.jsonl"
        self.summaries_file = self.data_folder / "summaries.json"
        self.settings_file = self.data_folder / "settings.json"
        self.suppliers_file = self.data_folder / "suppliers.json"
        self.purchase_orders_file = self.data_folder / "purchase_orders.json"
        self.purchase_items_file = self.data_folder / "purchase_items.jsonl"
        self.supplier_payments_file = self.data_folder / "supplier_payments.jsonl"
        self.supplier_summaries_file = self.data_folder / "supplier_summaries.json"
        self.checks_file = self.data_folder / "checks.json"

        # سجل التدقيق — يُسجَّل تلقائياً داخل دوال التعديل نفسها،
        # فيستحيل أن تنسى الواجهة استدعاءه
        self.audit = AuditManager(self.data_folder)

    def _log(
        self,
        action: ActionType,
        entity_type: EntityType,
        entity_id: str,
        old_data: Optional[dict] = None,
        new_data: Optional[dict] = None,
    ) -> None:
        """
        تسجيل عملية في سجل التدقيق
        Log an operation to the audit trail

        فشل التسجيل لا يوقف العملية التجارية أبداً — لا نخسر تسجيل بيعة
        لأن ملف السجل تعذّرت الكتابة فيه.
        """
        try:
            self.audit.log_action(action, entity_type, entity_id, old_data, new_data)
        except Exception:
            pass

    # ============ إدارة العملاء - Customer Management ============
    
    def load_customers(self) -> List[Customer]:
        """
        تحميل جميع العملاء
        Load all customers
        """
        data = read_json(self.customers_file, default=[])
        return [Customer.from_dict(c) for c in data]
    
    def save_customers(self, customers: List[Customer]) -> None:
        """
        حفظ جميع العملاء
        Save all customers
        """
        data = [c.to_dict() for c in customers]
        atomic_write_json(self.customers_file, data)
    
    def add_customer(self, customer: Customer) -> None:
        """
        إضافة عميل جديد
        Add new customer
        """
        customers = self.load_customers()
        
        # التحقق من عدم وجود عميل بنفس المعرف
        if any(c.id == customer.id for c in customers):
            raise ValueError(f"Customer with ID '{customer.id}' already exists")
        
        customers.append(customer)
        self.save_customers(customers)
        self._log("create", "customer", customer.id, new_data=customer.to_dict())
    
    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """
        الحصول على عميل بواسطة المعرف
        Get customer by ID
        """
        customers = self.load_customers()
        for c in customers:
            if c.id == customer_id:
                return c
        return None
    
    # ============ إدارة الإدخالات - Entry Management ============
    
    def load_entries(self) -> List[Entry]:
        """
        تحميل جميع الإدخالات
        Load all entries
        """
        data = read_jsonl(self.entries_file)
        return [Entry.from_dict(e) for e in data]
    
    def add_entry(self, entry: Entry) -> None:
        """
        إضافة إدخال جديد
        Add new entry
        """
        # التحقق من صحة البيانات
        entry.validate()
        
        # التحقق من وجود العميل
        customer = self.get_customer(entry.customer_id)
        if not customer:
            raise ValueError(f"Customer with ID '{entry.customer_id}' does not exist")
        
        # إضافة الإدخال
        atomic_append_jsonl(self.entries_file, entry.to_dict())
        self._log("create", "entry", entry.id, new_data=entry.to_dict())
    
    def get_customer_entries(self, customer_id: str) -> List[Entry]:
        """
        الحصول على جميع إدخالات عميل معين
        Get all entries for a specific customer
        """
        all_entries = self.load_entries()
        return [e for e in all_entries if e.customer_id == customer_id]
    
    # ============ إدارة الملخصات - Summary Management ============
    
    def load_summaries(self) -> Dict[str, Summary]:
        """
        تحميل جميع الملخصات
        Load all summaries
        """
        data = read_json(self.summaries_file, default={})
        return {
            customer_id: Summary.from_dict(summary_data)
            for customer_id, summary_data in data.items()
        }
    
    def save_summaries(self, summaries: Dict[str, Summary]) -> None:
        """
        حفظ جميع الملخصات
        Save all summaries
        """
        data = {
            customer_id: summary.to_dict()
            for customer_id, summary in summaries.items()
        }
        atomic_write_json(self.summaries_file, data)
    
    def get_customer_summary(self, customer_id: str) -> Summary:
        """
        الحصول على ملخص عميل معين
        Get summary for specific customer
        """
        summaries = self.load_summaries()
        return summaries.get(customer_id, Summary.empty())
    
    # ============ إدارة الإعدادات - Settings Management ============
    
    def load_settings(self) -> Dict[str, Any]:
        """
        تحميل الإعدادات
        Load settings
        """
        default_settings = {
            "theme": "light",
            "auto_backup_interval": 200,
            "password_hash": None
        }
        return read_json(self.settings_file, default=default_settings)
    
    def save_settings(self, settings: Dict[str, Any]) -> None:
        """
        حفظ الإعدادات
        Save settings
        """
        atomic_write_json(self.settings_file, settings)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        الحصول على إعداد معين
        Get specific setting
        """
        settings = self.load_settings()
        return settings.get(key, default)
    
    def update_setting(self, key: str, value: Any) -> None:
        """
        تحديث إعداد معين
        Update specific setting
        """
        settings = self.load_settings()
        settings[key] = value
        self.save_settings(settings)
    
    # ============ معلومات إحصائية - Statistics ============
    
    def get_total_entries_count(self) -> int:
        """
        الحصول على عدد الإدخالات الكلي
        Get total number of entries
        """
        return len(self.load_entries())
    
    # ============ إدارة الموردين - Supplier Management ============
    
    def load_suppliers(self) -> List[Supplier]:
        """
        تحميل جميع الموردين
        Load all suppliers
        """
        data = read_json(self.suppliers_file, default=[])
        return [Supplier.from_dict(s) for s in data]
    
    def save_suppliers(self, suppliers: List[Supplier]) -> None:
        """
        حفظ جميع الموردين
        Save all suppliers
        """
        data = [s.to_dict() for s in suppliers]
        atomic_write_json(self.suppliers_file, data)
    
    def add_supplier(self, supplier: Supplier) -> None:
        """
        إضافة مورد جديد
        Add new supplier
        """
        suppliers = self.load_suppliers()
        if any(s.id == supplier.id for s in suppliers):
            raise ValueError(f"Supplier with ID '{supplier.id}' already exists")
        suppliers.append(supplier)
        self.save_suppliers(suppliers)
        self._log("create", "supplier", supplier.id, new_data=supplier.to_dict())
    
    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        """
        الحصول على مورد بواسطة المعرف
        Get supplier by ID
        """
        suppliers = self.load_suppliers()
        for s in suppliers:
            if s.id == supplier_id:
                return s
        return None
    
    # ============ إدارة الطلبيات - Purchase Order Management ============
    
    def load_purchase_orders(self) -> List[PurchaseOrder]:
        """
        تحميل جميع الطلبيات
        Load all purchase orders
        """
        data = read_json(self.purchase_orders_file, default=[])
        return [PurchaseOrder.from_dict(o) for o in data]
    
    def save_purchase_orders(self, orders: List[PurchaseOrder]) -> None:
        """
        حفظ جميع الطلبيات
        Save all purchase orders
        """
        data = [o.to_dict() for o in orders]
        atomic_write_json(self.purchase_orders_file, data)
    
    def add_purchase_order(self, order: PurchaseOrder) -> None:
        """
        إضافة طلبية جديدة
        Add new purchase order
        """
        orders = self.load_purchase_orders()
        orders.append(order)
        self.save_purchase_orders(orders)
        self._log("create", "purchase_order", order.id, new_data=order.to_dict())
    
    def get_purchase_order(self, order_id: str) -> Optional[PurchaseOrder]:
        """
        الحصول على طلبية بواسطة المعرف
        Get purchase order by ID
        """
        orders = self.load_purchase_orders()
        for o in orders:
            if o.id == order_id:
                return o
        return None
    
    # ============ إدارة بنود الشراء - Purchase Items Management ============
    
    def load_purchase_items(self) -> List[PurchaseItem]:
        """
        تحميل جميع بنود الشراء
        Load all purchase items
        """
        data = read_jsonl(self.purchase_items_file)
        return [PurchaseItem.from_dict(item) for item in data]
    
    def add_purchase_item(self, item: PurchaseItem) -> None:
        """
        إضافة بند شراء جديد
        Add new purchase item
        """
        atomic_append_jsonl(self.purchase_items_file, item.to_dict())
        self._log("create", "purchase_item", item.id, new_data=item.to_dict())
    
    def get_order_items(self, order_id: str) -> List[PurchaseItem]:
        """
        الحصول على بنود طلبية معينة
        Get items for a specific order
        """
        all_items = self.load_purchase_items()
        return [item for item in all_items if item.order_id == order_id]
    
    def get_supplier_purchase_items(self, supplier_id: str) -> List[PurchaseItem]:
        """
        الحصول على بنود شراء مورد معين
        Get purchase items for a specific supplier
        """
        all_items = self.load_purchase_items()
        return [item for item in all_items if item.supplier_id == supplier_id]
    
    # ============ إدارة دفعات الموردين - Supplier Payments Management ============
    
    def load_supplier_payments(self) -> List[SupplierPayment]:
        """
        تحميل جميع دفعات الموردين
        Load all supplier payments
        """
        data = read_jsonl(self.supplier_payments_file)
        return [SupplierPayment.from_dict(p) for p in data]
    
    def add_supplier_payment(self, payment: SupplierPayment) -> None:
        """
        إضافة دفعة مورد جديدة
        Add new supplier payment
        """
        atomic_append_jsonl(self.supplier_payments_file, payment.to_dict())
        self._log("create", "supplier_payment", payment.id, new_data=payment.to_dict())
    
    def get_supplier_payments(self, supplier_id: str) -> List[SupplierPayment]:
        """
        الحصول على دفعات مورد معين
        Get payments for a specific supplier
        """
        all_payments = self.load_supplier_payments()
        return [p for p in all_payments if p.supplier_id == supplier_id]
    
    # ============ إدارة ملخصات الموردين - Supplier Summaries ============
    
    def load_supplier_summaries(self) -> Dict[str, SupplierSummary]:
        """
        تحميل جميع ملخصات الموردين
        Load all supplier summaries
        """
        data = read_json(self.supplier_summaries_file, default={})
        return {
            supplier_id: SupplierSummary.from_dict(summary_data)
            for supplier_id, summary_data in data.items()
        }
    
    def save_supplier_summaries(self, summaries: Dict[str, SupplierSummary]) -> None:
        """
        حفظ جميع ملخصات الموردين
        Save all supplier summaries
        """
        data = {
            supplier_id: summary.to_dict()
            for supplier_id, summary in summaries.items()
        }
        atomic_write_json(self.supplier_summaries_file, data)
    
    def get_supplier_summary(self, supplier_id: str) -> SupplierSummary:
        """
        الحصول على ملخص مورد معين
        Get summary for specific supplier
        """
        summaries = self.load_supplier_summaries()
        return summaries.get(supplier_id, SupplierSummary.empty())
    
    # ============ إدارة الشيكات - Check Management ============
    
    def load_checks(self) -> List[Check]:
        """
        تحميل جميع الشيكات
        Load all checks
        """
        data = read_json(self.checks_file, default=[])
        return [Check.from_dict(c) for c in data]
    
    def save_checks(self, checks: List[Check]) -> None:
        """
        حفظ جميع الشيكات
        Save all checks
        """
        data = [c.to_dict() for c in checks]
        atomic_write_json(self.checks_file, data)
    
    def add_check(self, check: Check) -> None:
        """
        إضافة شيك جديد
        Add new check
        """
        check.validate()

        checks = self.load_checks()
        checks.append(check)
        self.save_checks(checks)
        self._log("create", "check", check.id, new_data=check.to_dict())
    
    def update_check_status(self, check_id: str, new_status: str) -> bool:
        """
        تحديث حالة شيك
        Update a check's status

        كانت هذه الدالة تكتب checks.json **بلا تسجيل في سجل التدقيق**،
        بخلاف كل عمليات التعديل الأخرى — فثغرة في التتبّع. صارت تسجّل.

        Returns:
            True إن وُجد الشيك وتغيّرت حالته

        Raises:
            ValueError: إذا كانت الحالة غير معروفة
        """
        if new_status not in ("pending", "cashed", "bounced"):
            raise ValueError(f"حالة شيك غير معروفة: {new_status}")

        checks = self.load_checks()
        for i, check in enumerate(checks):
            if check.id == check_id:
                old_data = check.to_dict()
                updated = replace(check, status=new_status)
                checks[i] = updated
                self.save_checks(checks)
                self._log("update", "check", check_id,
                          old_data=old_data, new_data=updated.to_dict())
                return True
        return False
    
    def get_check(self, check_id: str) -> Optional[Check]:
        """
        الحصول على شيك بواسطة المعرف
        Get check by ID
        """
        checks = self.load_checks()
        for c in checks:
            if c.id == check_id:
                return c
        return None

    # ============ CRUD الحركات - Entry CRUD ============

    def save_entries(self, entries: List[Entry]) -> None:
        """
        حفظ جميع الحركات (إعادة كتابة ذرّية للملف كاملاً)
        Save all entries — full atomic rewrite
        """
        atomic_write_jsonl(self.entries_file, [e.to_dict() for e in entries])

    def get_entry(self, entry_id: str) -> Optional[Entry]:
        """الحصول على حركة بواسطة المعرّف - Get entry by ID"""
        for entry in self.load_entries():
            if entry.id == entry_id:
                return entry
        return None

    def update_entry(self, entry: Entry) -> None:
        """
        تحديث حركة موجودة (البحث بالمعرّف)
        Update an existing entry, matched by ID

        Raises:
            KeyError: إذا لم توجد حركة بهذا المعرّف
            ValueError: إذا كانت البيانات غير صالحة
        """
        entry.validate()

        entries = self.load_entries()
        for i, existing in enumerate(entries):
            if existing.id == entry.id:
                old_data = existing.to_dict()
                entries[i] = entry
                self.save_entries(entries)
                self._log("update", "entry", entry.id,
                          old_data=old_data, new_data=entry.to_dict())
                return

        raise KeyError(f"Entry not found: {entry.id}")

    def delete_entry(self, entry_id: str) -> Entry:
        """
        حذف حركة (البحث بالمعرّف)
        Delete an entry, matched by ID

        Returns:
            الحركة المحذوفة

        Raises:
            KeyError: إذا لم توجد حركة بهذا المعرّف
        """
        entries = self.load_entries()
        for i, existing in enumerate(entries):
            if existing.id == entry_id:
                removed = entries.pop(i)
                self.save_entries(entries)
                self._log("delete", "entry", entry_id, old_data=removed.to_dict())
                return removed

        raise KeyError(f"Entry not found: {entry_id}")

    # ============ CRUD العملاء - Customer CRUD ============

    def update_customer(self, customer: Customer) -> None:
        """
        تحديث بيانات عميل موجود
        Update an existing customer

        Raises:
            KeyError: إذا لم يوجد عميل بهذا المعرّف
        """
        customers = self.load_customers()
        for i, existing in enumerate(customers):
            if existing.id == customer.id:
                old_data = existing.to_dict()
                customers[i] = customer
                self.save_customers(customers)
                self._log("update", "customer", customer.id,
                          old_data=old_data, new_data=customer.to_dict())
                return

        raise KeyError(f"Customer not found: {customer.id}")

    def delete_customer(self, customer_id: str) -> tuple[Customer, int, Path]:
        """
        حذف عميل مع جميع حركاته
        Delete a customer and all their entries

        تُنشأ نسخة احتياطية تلقائياً قبل أي حذف — الحذف لا رجعة فيه.
        بدون الحذف المتتالي تبقى الحركات يتيمة، وقد يرث عميل جديد بنفس
        المعرّف ديون القديم.

        Returns:
            (العميل المحذوف، عدد الحركات المحذوفة، مسار النسخة الاحتياطية)

        Raises:
            KeyError: إذا لم يوجد عميل بهذا المعرّف
        """
        customers = self.load_customers()
        customer = next((c for c in customers if c.id == customer_id), None)
        if customer is None:
            raise KeyError(f"Customer not found: {customer_id}")

        backup_path = create_backup(data_folder=self.data_folder, prefix="pre-delete")

        self.save_customers([c for c in customers if c.id != customer_id])

        entries = self.load_entries()
        remaining = [e for e in entries if e.customer_id != customer_id]
        deleted_count = len(entries) - len(remaining)
        self.save_entries(remaining)

        summaries = self.load_summaries()
        summaries.pop(customer_id, None)
        self.save_summaries(summaries)

        self._log("delete", "customer", customer_id, old_data=customer.to_dict())

        return customer, deleted_count, backup_path

    # ============ CRUD الموردين - Supplier CRUD ============

    def update_supplier(self, supplier: Supplier) -> None:
        """
        تحديث بيانات مورد موجود
        Update an existing supplier

        Raises:
            KeyError: إذا لم يوجد مورد بهذا المعرّف
        """
        suppliers = self.load_suppliers()
        for i, existing in enumerate(suppliers):
            if existing.id == supplier.id:
                old_data = existing.to_dict()
                suppliers[i] = supplier
                self.save_suppliers(suppliers)
                self._log("update", "supplier", supplier.id,
                          old_data=old_data, new_data=supplier.to_dict())
                return

        raise KeyError(f"Supplier not found: {supplier.id}")

    def delete_supplier(self, supplier_id: str) -> tuple[Supplier, Dict[str, int], Path]:
        """
        حذف مورد مع بنود شرائه ودفعاته وملخّصه
        Delete a supplier along with their purchase items, payments and summary

        تُنشأ نسخة احتياطية تلقائياً قبل الحذف.

        Returns:
            (المورد المحذوف، {"items": عدد، "payments": عدد}، مسار النسخة)

        Raises:
            KeyError: إذا لم يوجد مورد بهذا المعرّف
        """
        suppliers = self.load_suppliers()
        supplier = next((s for s in suppliers if s.id == supplier_id), None)
        if supplier is None:
            raise KeyError(f"Supplier not found: {supplier_id}")

        backup_path = create_backup(data_folder=self.data_folder, prefix="pre-delete")

        self.save_suppliers([s for s in suppliers if s.id != supplier_id])

        items = self.load_purchase_items()
        kept_items = [i for i in items if i.supplier_id != supplier_id]
        deleted_items = len(items) - len(kept_items)
        self.save_purchase_items(kept_items)

        payments = self.load_supplier_payments()
        kept_payments = [p for p in payments if p.supplier_id != supplier_id]
        deleted_payments = len(payments) - len(kept_payments)
        self.save_supplier_payments(kept_payments)

        summaries = self.load_supplier_summaries()
        summaries.pop(supplier_id, None)
        self.save_supplier_summaries(summaries)

        self._log("delete", "supplier", supplier_id, old_data=supplier.to_dict())

        return supplier, {"items": deleted_items, "payments": deleted_payments}, backup_path

    # ============ CRUD بنود الشراء - Purchase Item CRUD ============

    def save_purchase_items(self, items: List[PurchaseItem]) -> None:
        """حفظ جميع بنود الشراء (إعادة كتابة ذرّية)"""
        atomic_write_jsonl(self.purchase_items_file, [i.to_dict() for i in items])

    def get_purchase_item(self, item_id: str) -> Optional[PurchaseItem]:
        """الحصول على بند شراء بواسطة المعرّف"""
        for item in self.load_purchase_items():
            if item.id == item_id:
                return item
        return None

    def update_purchase_item(self, item: PurchaseItem) -> None:
        """
        تحديث بند شراء موجود (البحث بالمعرّف)

        Raises:
            KeyError: إذا لم يوجد بند بهذا المعرّف
        """
        items = self.load_purchase_items()
        for i, existing in enumerate(items):
            if existing.id == item.id:
                old_data = existing.to_dict()
                items[i] = item
                self.save_purchase_items(items)
                self._log("update", "purchase_item", item.id,
                          old_data=old_data, new_data=item.to_dict())
                return

        raise KeyError(f"Purchase item not found: {item.id}")

    def delete_purchase_item(self, item_id: str) -> PurchaseItem:
        """
        حذف بند شراء (البحث بالمعرّف)

        Returns:
            البند المحذوف

        Raises:
            KeyError: إذا لم يوجد بند بهذا المعرّف
        """
        items = self.load_purchase_items()
        for i, existing in enumerate(items):
            if existing.id == item_id:
                removed = items.pop(i)
                self.save_purchase_items(items)
                self._log("delete", "purchase_item", item_id, old_data=removed.to_dict())
                return removed

        raise KeyError(f"Purchase item not found: {item_id}")

    # ============ CRUD فواتير الشراء - Purchase Order CRUD ============

    def update_purchase_order(self, order: PurchaseOrder) -> None:
        """
        تحديث فاتورة شراء موجودة

        Raises:
            KeyError: إذا لم توجد فاتورة بهذا المعرّف
        """
        orders = self.load_purchase_orders()
        for i, existing in enumerate(orders):
            if existing.id == order.id:
                old_data = existing.to_dict()
                orders[i] = order
                self.save_purchase_orders(orders)
                self._log("update", "purchase_order", order.id,
                          old_data=old_data, new_data=order.to_dict())
                return

        raise KeyError(f"Purchase order not found: {order.id}")

    def delete_purchase_order(self, order_id: str) -> tuple[PurchaseOrder, int, Path]:
        """
        حذف فاتورة شراء مع كل بنودها
        Delete a purchase order along with all its items

        Returns:
            (الفاتورة المحذوفة، عدد البنود المحذوفة، مسار النسخة الاحتياطية)

        Raises:
            KeyError: إذا لم توجد فاتورة بهذا المعرّف
        """
        orders = self.load_purchase_orders()
        order = next((o for o in orders if o.id == order_id), None)
        if order is None:
            raise KeyError(f"Purchase order not found: {order_id}")

        backup_path = create_backup(data_folder=self.data_folder, prefix="pre-delete")

        self.save_purchase_orders([o for o in orders if o.id != order_id])

        items = self.load_purchase_items()
        kept = [i for i in items if i.order_id != order_id]
        deleted_count = len(items) - len(kept)
        self.save_purchase_items(kept)

        self._log("delete", "purchase_order", order_id, old_data=order.to_dict())

        return order, deleted_count, backup_path

    # ============ CRUD دفعات الموردين - Supplier Payment CRUD ============

    def save_supplier_payments(self, payments: List[SupplierPayment]) -> None:
        """حفظ جميع دفعات الموردين (إعادة كتابة ذرّية)"""
        atomic_write_jsonl(self.supplier_payments_file, [p.to_dict() for p in payments])

    def get_supplier_payment(self, payment_id: str) -> Optional[SupplierPayment]:
        """الحصول على دفعة مورد بواسطة المعرّف"""
        for payment in self.load_supplier_payments():
            if payment.id == payment_id:
                return payment
        return None

    def delete_supplier_payment(self, payment_id: str) -> SupplierPayment:
        """
        حذف دفعة مورد

        Returns:
            الدفعة المحذوفة

        Raises:
            KeyError: إذا لم توجد دفعة بهذا المعرّف
        """
        payments = self.load_supplier_payments()
        for i, existing in enumerate(payments):
            if existing.id == payment_id:
                removed = payments.pop(i)
                self.save_supplier_payments(payments)
                self._log("delete", "supplier_payment", payment_id,
                          old_data=removed.to_dict())
                return removed

        raise KeyError(f"Supplier payment not found: {payment_id}")

    # ============ CRUD الشيكات - Check CRUD ============

    def update_check(self, check: Check) -> None:
        """
        تحديث شيك موجود (كل الحقول، لا الحالة وحدها)

        Raises:
            KeyError: إذا لم يوجد شيك بهذا المعرّف
        """
        check.validate()

        checks = self.load_checks()
        for i, existing in enumerate(checks):
            if existing.id == check.id:
                old_data = existing.to_dict()
                checks[i] = check
                self.save_checks(checks)
                self._log("update", "check", check.id,
                          old_data=old_data, new_data=check.to_dict())
                return

        raise KeyError(f"Check not found: {check.id}")

    def delete_check(self, check_id: str) -> Check:
        """
        حذف شيك

        Returns:
            الشيك المحذوف

        Raises:
            KeyError: إذا لم يوجد شيك بهذا المعرّف
        """
        checks = self.load_checks()
        for i, existing in enumerate(checks):
            if existing.id == check_id:
                removed = checks.pop(i)
                self.save_checks(checks)
                self._log("delete", "check", check_id, old_data=removed.to_dict())
                return removed

        raise KeyError(f"Check not found: {check_id}")
