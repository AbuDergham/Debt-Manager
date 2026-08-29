"""
أدوات مساعدة للتطبيق
Utility functions for the application
"""
import sys
import hashlib
from pathlib import Path
from typing import Optional
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


# ملفات البيانات: الاسم المنطقي -> (اسم الملف، المحتوى الابتدائي)
# مصدر واحد للحقيقة — يستخدمه ensure_data_folder و create_backup معاً.
# إضافة ملف بيانات جديد = سطر واحد هنا.
DATA_FILES: dict[str, tuple[str, str]] = {
    "customers":          ("customers.json",           "[]"),
    "entries":            ("entries.jsonl",            ""),
    "summaries":          ("summaries.json",           "{}"),
    "settings":           ("settings.json",
                           '{"theme": "light", "auto_backup_interval": 200}'),
    "suppliers":          ("suppliers.json",           "[]"),
    "purchase_orders":    ("purchase_orders.json",     "[]"),
    "purchase_items":     ("purchase_items.jsonl",     ""),
    "supplier_payments":  ("supplier_payments.jsonl",  ""),
    "supplier_summaries": ("supplier_summaries.json",  "{}"),
    "checks":             ("checks.json",              "[]"),
}


def ensure_data_folder(folder: Optional[Path] = None) -> Path:
    """
    التأكد من وجود مجلد البيانات وملفاته الأساسية
    Ensure the data folder and its base files exist

    Args:
        folder: مجلد بيانات مخصص (للاختبارات). الافتراضي: مجلد الإنتاج.

    Returns:
        مسار مجلد البيانات
    """
    data_folder = Path(folder) if folder is not None else get_data_folder()
    data_folder.mkdir(parents=True, exist_ok=True)
    (data_folder / "backups").mkdir(exist_ok=True)

    for filename, initial_content in DATA_FILES.values():
        path = data_folder / filename
        if not path.exists():
            path.write_text(initial_content, encoding="utf-8")

    return data_folder


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
