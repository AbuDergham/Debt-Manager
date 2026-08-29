"""
نماذج البيانات للتطبيق
Data models for the debt management application
"""
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime
from typing import Literal

# أنواع الإدخالات المسموحة
EntryType = Literal["purchase", "payment"]
PaymentMethod = Literal["cash", "transfer"]


@dataclass
class Customer:
    """نموذج العميل - Customer model"""
    id: str
    name: str
    phone: str = ""  # رقم الهاتف للتواصل
    credit_limit: str = "0"  # الحد الأقصى للدين (0 = غير محدود)
    notes: str = ""  # ملاحظات داخلية
    
    @property
    def credit_limit_decimal(self) -> Decimal:
        """الحصول على حد الائتمان كـ Decimal"""
        return Decimal(self.credit_limit) if self.credit_limit else Decimal("0")
    
    def to_dict(self):
        """تحويل إلى قاموس - Convert to dictionary"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'Customer':
        """إنشاء من قاموس - Create from dictionary"""
        return Customer(
            id=data['id'],
            name=data['name'],
            phone=data.get('phone', ''),
            credit_limit=data.get('credit_limit', '0'),
            notes=data.get('notes', '')
        )


@dataclass
class Entry:
    """نموذج الإدخال (شراء أو دفع) - Entry model (purchase or payment)"""
    customer_id: str
    type: EntryType
    amount: str  # سيتم تخزينه كنص للحفاظ على الدقة - Stored as string to preserve precision
    date: str  # ISO format datetime string
    desc: str
    pay_method: PaymentMethod
    notes: str = ""  # ملاحظات داخلية لا تظهر للعميل
    
    @property
    def amount_decimal(self) -> Decimal:
        """الحصول على المبلغ كـ Decimal - Get amount as Decimal"""
        return Decimal(self.amount)
    
    @property
    def signed_amount(self) -> Decimal:
        """
        الحصول على المبلغ بإشارة حسب النوع
        Get signed amount based on type
        - purchase: positive (دين على العميل)
        - payment: negative (دفع من العميل)
        """
        amount = self.amount_decimal
        if self.type == "purchase":
            return amount
        elif self.type == "payment":
            return -amount
        else:
            raise ValueError(f"Invalid entry type: {self.type}")
    
    @property
    def datetime(self) -> datetime:
        """الحصول على التاريخ كـ datetime - Get date as datetime object"""
        return datetime.fromisoformat(self.date)
    
    def to_dict(self):
        """تحويل إلى قاموس - Convert to dictionary"""
        return {
            'customer_id': self.customer_id,
            'type': self.type,
            'amount': self.amount,
            'date': self.date,
            'desc': self.desc,
            'pay_method': self.pay_method,
            'notes': self.notes
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Entry':
        """إنشاء من قاموس - Create from dictionary"""
        return Entry(
            customer_id=data['customer_id'],
            type=data['type'],
            amount=data['amount'],
            date=data['date'],
            desc=data['desc'],
            pay_method=data['pay_method'],
            notes=data.get('notes', '')
        )
    
    def validate(self) -> bool:
        """
        التحقق من صحة البيانات
        Validate entry data
        """
        # التحقق من نوع الإدخال
        if self.type not in ["purchase", "payment"]:
            raise ValueError(f"Invalid entry type: {self.type}")
        
        # التحقق من طريقة الدفع
        if self.pay_method not in ["cash", "transfer"]:
            raise ValueError(f"Invalid payment method: {self.pay_method}")
        
        # التحقق من المبلغ (يجب أن يكون موجب)
        if self.amount_decimal <= 0:
            raise ValueError(f"Amount must be positive: {self.amount}")
        
        # التحقق من التاريخ
        try:
            self.datetime
        except ValueError as e:
            raise ValueError(f"Invalid date format: {self.date}") from e
        
        return True


@dataclass
class Summary:
    """
    ملخص حساب العميل
    Customer account summary
    """
    balance: str  # الرصيد الحالي - Current balance
    today_sales: str  # مبيعات اليوم - Today's sales
    month_sales: str  # مبيعات الشهر - Month's sales
    last_update: str  # آخر تحديث - Last update (ISO datetime)
    
    @property
    def balance_decimal(self) -> Decimal:
        """الحصول على الرصيد كـ Decimal"""
        return Decimal(self.balance)
    
    @property
    def today_sales_decimal(self) -> Decimal:
        """الحصول على مبيعات اليوم كـ Decimal"""
        return Decimal(self.today_sales)
    
    @property
    def month_sales_decimal(self) -> Decimal:
        """الحصول على مبيعات الشهر كـ Decimal"""
        return Decimal(self.month_sales)
    
    def to_dict(self):
        """تحويل إلى قاموس - Convert to dictionary"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'Summary':
        """إنشاء من قاموس - Create from dictionary"""
        return Summary(
            balance=data['balance'],
            today_sales=data['today_sales'],
            month_sales=data['month_sales'],
            last_update=data['last_update']
        )
    
    @staticmethod
    def empty() -> 'Summary':
        """
        إنشاء ملخص فارغ
        Create empty summary
        """
        return Summary(
            balance="0.00",
            today_sales="0.00",
            month_sales="0.00",
            last_update=datetime.now().isoformat()
        )
