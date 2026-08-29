"""
أدوات مساعدة للتطبيق
Utility functions for the application
"""
import sys
import hashlib
from pathlib import Path
from decimal import Decimal
from datetime import datetime


def get_base_path() -> Path:
    """
    الحصول على المسار الأساسي للتطبيق
    Get base path for the application
    
    يعمل في كل من وضع التطوير ووضع PyInstaller
    Works in both development and PyInstaller mode
    """
    if getattr(sys, 'frozen', False):
        # التطبيق مُجمّع بواسطة PyInstaller
        # Application is bundled by PyInstaller
        return Path(sys.executable).parent
    else:
        # وضع التطوير
        # Development mode
        return Path(__file__).parent.parent


def get_data_folder() -> Path:
    """
    الحصول على مجلد البيانات
    Get data folder path
    """
    return get_base_path() / "data"


def ensure_data_folder() -> None:
    """
    التأكد من وجود مجلد البيانات وإنشائه إذا لم يكن موجوداً
    Ensure data folder exists, create if it doesn't
    """
    data_folder = get_data_folder()
    data_folder.mkdir(exist_ok=True)
    
    # إنشاء مجلد النسخ الاحتياطية
    # Create backups folder
    backups_folder = data_folder / "backups"
    backups_folder.mkdir(exist_ok=True)
    
    # إنشاء الملفات الأساسية إذا لم تكن موجودة
    # Create base files if they don't exist
    customers_file = data_folder / "customers.json"
    if not customers_file.exists():
        customers_file.write_text("[]", encoding="utf-8")
    
    entries_file = data_folder / "entries.jsonl"
    if not entries_file.exists():
        entries_file.write_text("", encoding="utf-8")
    
    summaries_file = data_folder / "summaries.json"
    if not summaries_file.exists():
        summaries_file.write_text("{}", encoding="utf-8")
    
    # إنشاء ملف الإعدادات
    # Create settings file
    settings_file = data_folder / "settings.json"
    if not settings_file.exists():
        settings_file.write_text('{"theme": "light", "auto_backup_interval": 200}', encoding="utf-8")
    
    # === ملفات نظام الموردين الجديدة ===
    # === New supplier system files ===
    suppliers_file = data_folder / "suppliers.json"
    if not suppliers_file.exists():
        suppliers_file.write_text("[]", encoding="utf-8")
    
    purchase_orders_file = data_folder / "purchase_orders.json"
    if not purchase_orders_file.exists():
        purchase_orders_file.write_text("[]", encoding="utf-8")
    
    purchase_items_file = data_folder / "purchase_items.jsonl"
    if not purchase_items_file.exists():
        purchase_items_file.write_text("", encoding="utf-8")
    
    supplier_payments_file = data_folder / "supplier_payments.jsonl"
    if not supplier_payments_file.exists():
        supplier_payments_file.write_text("", encoding="utf-8")
    
    checks_file = data_folder / "checks.json"
    if not checks_file.exists():
        checks_file.write_text("[]", encoding="utf-8")
    
    supplier_summaries_file = data_folder / "supplier_summaries.json"
    if not supplier_summaries_file.exists():
        supplier_summaries_file.write_text("{}", encoding="utf-8")


def decimal_to_str(value: Decimal) -> str:
    """
    تحويل Decimal إلى نص بصيغة قياسية
    Convert Decimal to string with standard format
    """
    return f"{value:.2f}"


def str_to_decimal(value: str) -> Decimal:
    """
    تحويل نص إلى Decimal
    Convert string to Decimal
    """
    return Decimal(value)


def format_currency(amount: Decimal, currency: str = "شيكل") -> str:
    """
    تنسيق المبلغ كعملة
    Format amount as currency
    
    Args:
        amount: المبلغ كـ Decimal
        currency: رمز العملة (افتراضي: شيكل)
    """
    formatted = f"{amount:,.2f}"
    return f"{formatted} {currency}"


def format_datetime_arabic(dt: datetime) -> str:
    """
    تنسيق التاريخ والوقت بصيغة عربية
    Format datetime in Arabic-friendly format
    """
    # 12-hour format with AM/PM after time
    return dt.strftime("%Y/%m/%d %I:%M %p")


def hash_password(password: str) -> str:
    """
    تشفير كلمة المرور باستخدام SHA-256
    Hash password using SHA-256
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """
    التحقق من كلمة المرور
    Verify password against hash
    """
    return hash_password(password) == hashed


def is_same_day(dt1: datetime, dt2: datetime) -> bool:
    """
    التحقق من أن تاريخين في نفس اليوم
    Check if two datetimes are on the same day
    """
    return (dt1.year == dt2.year and 
            dt1.month == dt2.month and 
            dt1.day == dt2.day)


def is_same_month(dt1: datetime, dt2: datetime) -> bool:
    """
    التحقق من أن تاريخين في نفس الشهر
    Check if two datetimes are in the same month
    """
    return dt1.year == dt2.year and dt1.month == dt2.month


def get_current_datetime_iso() -> str:
    """
    الحصول على التاريخ والوقت الحالي بصيغة ISO
    Get current datetime in ISO format
    """
    return datetime.now().isoformat()


def validate_customer_id(customer_id: str) -> bool:
    """
    التحقق من صحة معرف العميل
    Validate customer ID
    
    يجب أن يكون معرف العميل:
    - غير فارغ
    - يحتوي على حروف وأرقام فقط
    - لا يحتوي على مسافات
    """
    if not customer_id:
        return False
    
    # يجب أن يحتوي على حروف أو أرقام فقط (بدون مسافات أو رموز)
    return customer_id.replace("_", "").replace("-", "").isalnum()


def generate_order_id() -> str:
    """
    توليد معرف فريد لطلبية الشراء
    Generate unique purchase order ID
    Format: PO_YYYYMMDD_HHMMSS
    """
    now = datetime.now()
    return f"PO_{now.strftime('%Y%m%d_%H%M%S')}"


def generate_check_id() -> str:
    """
    توليد معرف فريد للشيك
    Generate unique check ID
    Format: CHK_YYYYMMDD_HHMMSS
    """
    now = datetime.now()
    return f"CHK_{now.strftime('%Y%m%d_%H%M%S')}"


def generate_payment_id() -> str:
    """
    توليد معرف فريد لدفعة مورد
    Generate unique supplier payment ID
    Format: SP_YYYYMMDD_HHMMSS
    """
    now = datetime.now()
    return f"SP_{now.strftime('%Y%m%d_%H%M%S')}"
