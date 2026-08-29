"""
طبقة التخزين مع الكتابة الذرية
Storage layer with atomic file operations
"""
import json
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from .models import (
    Customer, Entry, Summary,
    Supplier, PurchaseOrder, PurchaseItem,
    SupplierPayment, SupplierSummary, Check
)
from .utils import ensure_data_folder


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
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """
    قراءة جميع السجلات من ملف JSONL
    Read all records from JSONL file
    """
    path = Path(path)
    
    if not path.exists():
        return []
    
    records = []
    with open(path, 'r', encoding='utf-8') as f:
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
        checks = self.load_checks()
        checks.append(check)
        self.save_checks(checks)
    
    def update_check_status(self, check_id: str, new_status: str) -> bool:
        """
        تحديث حالة شيك
        Update check status
        Returns True if found and updated
        """
        checks = self.load_checks()
        for i, check in enumerate(checks):
            if check.id == check_id:
                checks[i] = Check(
                    id=check.id,
                    check_number=check.check_number,
                    bank_name=check.bank_name,
                    amount=check.amount,
                    issue_date=check.issue_date,
                    due_date=check.due_date,
                    status=new_status,
                    direction=check.direction,
                    party_type=check.party_type,
                    party_id=check.party_id,
                    party_name=check.party_name,
                    notes=check.notes
                )
                self.save_checks(checks)
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
