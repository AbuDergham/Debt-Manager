"""
نماذج البيانات للتطبيق
Data models for the debt management application
"""
import uuid
from dataclasses import dataclass, asdict, field
from decimal import Decimal
from datetime import datetime
from typing import Literal


def new_id() -> str:
    """
    توليد معرّف فريد لسجل جديد
    Generate a unique record ID

    يُستخدم للسجلات المخزّنة في ملفات JSONL (الحركات وبنود الشراء)، حيث
    لا يمكن تمييز سجلين متطابقين في كل حقولهما بدونه.
    """
    return uuid.uuid4().hex

# أنواع الإدخالات المسموحة
EntryType = Literal["purchase", "payment"]
PaymentMethod = Literal["cash", "transfer"]

# أنواع جديدة للموردين والشيكات
PackagingType = Literal["municipal", "plastic"]  # بلدية / بلاستيك
SupplierPaymentMethod = Literal["cash", "transfer", "check"]  # نقدي / تحويل / شيك
PurchasePaymentMethod = Literal["credit", "cash"]  # آجل / نقدي
CheckStatus = Literal["pending", "cashed", "bounced"]  # معلق / مصروف / مرتجع
CheckDirection = Literal["incoming", "outgoing"]  # وارد / صادر


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
    # المعرّف آخر الحقول لأن notes قبله له قيمة افتراضية (قيد dataclass).
    # كل استدعاءات Entry(...) في المشروع تستخدم keyword arguments.
    id: str = field(default_factory=new_id)

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
            'id': self.id,
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
            notes=data.get('notes', ''),
            id=data.get('id') or new_id()
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


@dataclass
class Supplier:
    """نموذج المورد - Supplier model"""
    id: str
    name: str
    phone: str = ""
    notes: str = ""
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'Supplier':
        """إنشاء من قاموس"""
        return Supplier(
            id=data['id'],
            name=data['name'],
            phone=data.get('phone', ''),
            notes=data.get('notes', '')
        )


@dataclass
class PurchaseOrder:
    """نموذج طلبية الشراء - Purchase order model"""
    id: str              # "PO_20260413_001"
    date: str            # ISO format date
    notes: str = ""
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'PurchaseOrder':
        """إنشاء من قاموس"""
        return PurchaseOrder(
            id=data['id'],
            date=data['date'],
            notes=data.get('notes', '')
        )
    
    @property
    def datetime(self) -> datetime:
        """الحصول على التاريخ كـ datetime"""
        return datetime.fromisoformat(self.date)


@dataclass
class PurchaseItem:
    """نموذج بند شراء - Purchase item model"""
    order_id: str           # معرف الطلبية
    supplier_id: str        # معرف المورد
    item_name: str          # الصنف (بندورة، خيار، إلخ)
    quantity: str           # العدد (0 إذا لا ينطبق)
    weight: str             # الوزن (0 إذا لا ينطبق)
    price: str              # السعر
    packaging: PackagingType  # بلدية / بلاستيك
    payment_method: PurchasePaymentMethod  # آجل / نقدي
    total: str              # المجموع
    notes: str = ""
    id: str = field(default_factory=new_id)  # معرّف فريد للبند
    
    @property
    def quantity_decimal(self) -> Decimal:
        """الحصول على العدد كـ Decimal"""
        return Decimal(self.quantity) if self.quantity else Decimal("0")
    
    @property
    def weight_decimal(self) -> Decimal:
        """الحصول على الوزن كـ Decimal"""
        return Decimal(self.weight) if self.weight else Decimal("0")
    
    @property
    def price_decimal(self) -> Decimal:
        """الحصول على السعر كـ Decimal"""
        return Decimal(self.price) if self.price else Decimal("0")
    
    @property
    def total_decimal(self) -> Decimal:
        """الحصول على المجموع كـ Decimal"""
        return Decimal(self.total) if self.total else Decimal("0")
    
    @staticmethod
    def calculate_total(quantity: str, weight: str, price: str) -> Decimal:
        """
        حساب المجموع التلقائي
        Auto-calculate total based on available fields
        """
        q = Decimal(quantity) if quantity and Decimal(quantity) > 0 else Decimal("0")
        w = Decimal(weight) if weight and Decimal(weight) > 0 else Decimal("0")
        p = Decimal(price) if price and Decimal(price) > 0 else Decimal("0")
        
        if q > 0 and w > 0 and p > 0:
            return q * w * p        # عدد × وزن × سعر
        elif q > 0 and p > 0:
            return q * p            # عدد × سعر
        elif w > 0 and p > 0:
            return w * p            # وزن × سعر
        else:
            return Decimal("0")
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'supplier_id': self.supplier_id,
            'item_name': self.item_name,
            'quantity': self.quantity,
            'weight': self.weight,
            'price': self.price,
            'packaging': self.packaging,
            'payment_method': self.payment_method,
            'total': self.total,
            'notes': self.notes
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'PurchaseItem':
        """إنشاء من قاموس"""
        return PurchaseItem(
            order_id=data['order_id'],
            supplier_id=data['supplier_id'],
            item_name=data['item_name'],
            quantity=data.get('quantity', '0'),
            weight=data.get('weight', '0'),
            price=data.get('price', '0'),
            packaging=data.get('packaging', 'municipal'),
            payment_method=data.get('payment_method', 'credit'),
            total=data.get('total', '0'),
            notes=data.get('notes', ''),
            id=data.get('id') or new_id()
        )


@dataclass
class SupplierPayment:
    """نموذج دفعة مورد - Supplier payment model"""
    id: str
    supplier_id: str
    amount: str
    date: str
    payment_method: SupplierPaymentMethod  # نقدي / تحويل / شيك
    check_id: str = ""      # معرف الشيك إذا كان الدفع بشيك
    notes: str = ""
    
    @property
    def amount_decimal(self) -> Decimal:
        """الحصول على المبلغ كـ Decimal"""
        return Decimal(self.amount)
    
    @property
    def datetime(self) -> datetime:
        """الحصول على التاريخ كـ datetime"""
        return datetime.fromisoformat(self.date)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'supplier_id': self.supplier_id,
            'amount': self.amount,
            'date': self.date,
            'payment_method': self.payment_method,
            'check_id': self.check_id,
            'notes': self.notes
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'SupplierPayment':
        """إنشاء من قاموس"""
        return SupplierPayment(
            id=data['id'],
            supplier_id=data['supplier_id'],
            amount=data['amount'],
            date=data['date'],
            payment_method=data.get('payment_method', 'cash'),
            check_id=data.get('check_id', ''),
            notes=data.get('notes', '')
        )


@dataclass
class SupplierSummary:
    """
    ملخص حساب المورد
    Supplier account summary
    """
    balance: str         # الرصيد الحالي (اللي عليك)
    total_purchases: str # إجمالي المشتريات الآجلة
    total_payments: str  # إجمالي الدفعات
    last_update: str     # آخر تحديث
    
    @property
    def balance_decimal(self) -> Decimal:
        """الحصول على الرصيد كـ Decimal"""
        return Decimal(self.balance)
    
    @property
    def total_purchases_decimal(self) -> Decimal:
        """الحصول على إجمالي المشتريات كـ Decimal"""
        return Decimal(self.total_purchases)
    
    @property
    def total_payments_decimal(self) -> Decimal:
        """الحصول على إجمالي الدفعات كـ Decimal"""
        return Decimal(self.total_payments)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'SupplierSummary':
        """إنشاء من قاموس"""
        return SupplierSummary(
            balance=data['balance'],
            total_purchases=data['total_purchases'],
            total_payments=data['total_payments'],
            last_update=data['last_update']
        )
    
    @staticmethod
    def empty() -> 'SupplierSummary':
        """إنشاء ملخص فارغ"""
        return SupplierSummary(
            balance="0.00",
            total_purchases="0.00",
            total_payments="0.00",
            last_update=datetime.now().isoformat()
        )


@dataclass
class Check:
    """نموذج شيك - Check model"""
    id: str                 # معرف فريد
    check_number: str       # رقم الشيك
    bank_name: str          # اسم البنك
    amount: str             # المبلغ
    issue_date: str         # تاريخ الإصدار
    due_date: str           # تاريخ الاستحقاق
    status: CheckStatus     # معلق / مصروف / مرتجع
    direction: CheckDirection  # وارد / صادر
    party_type: str         # "supplier" / "other"
    party_id: str           # معرف الجهة
    party_name: str         # اسم الجهة
    notes: str = ""
    
    @property
    def amount_decimal(self) -> Decimal:
        """الحصول على المبلغ كـ Decimal"""
        return Decimal(self.amount)
    
    @property
    def issue_datetime(self) -> datetime:
        """الحصول على تاريخ الإصدار كـ datetime"""
        return datetime.fromisoformat(self.issue_date)

    def validate(self) -> bool:
        """
        التحقق من صحة بيانات الشيك
        Validate check data

        وُجد في بيانات محل حقيقي شيك تاريخ استحقاقه **قبل** تاريخ إصداره،
        فلم يكن هناك ما يمنع إدخاله — ولا ما يصلحه من داخل البرنامج.

        Raises:
            ValueError: إذا كانت البيانات غير صالحة
        """
        if not self.check_number.strip():
            raise ValueError("رقم الشيك مطلوب")

        if self.status not in ("pending", "cashed", "bounced"):
            raise ValueError(f"حالة شيك غير معروفة: {self.status}")

        if self.direction not in ("incoming", "outgoing"):
            raise ValueError(f"اتجاه شيك غير معروف: {self.direction}")

        try:
            amount = self.amount_decimal
        except Exception as e:
            raise ValueError(f"المبلغ غير صالح: {self.amount}") from e

        if amount <= 0:
            raise ValueError(f"المبلغ يجب أن يكون أكبر من صفر: {self.amount}")

        try:
            issued, due = self.issue_datetime, self.due_datetime
        except ValueError as e:
            raise ValueError("تاريخ غير صالح في الشيك") from e

        if due < issued:
            raise ValueError(
                "تاريخ الاستحقاق لا يصح أن يسبق تاريخ الإصدار "
                f"({due.date()} قبل {issued.date()})"
            )

        return True
    
    @property
    def due_datetime(self) -> datetime:
        """الحصول على تاريخ الاستحقاق كـ datetime"""
        return datetime.fromisoformat(self.due_date)
    
    @property
    def is_pending(self) -> bool:
        """هل الشيك معلق"""
        return self.status == "pending"
    
    @property
    def is_cashed(self) -> bool:
        """هل الشيك مصروف"""
        return self.status == "cashed"
    
    @property
    def is_bounced(self) -> bool:
        """هل الشيك مرتجع"""
        return self.status == "bounced"
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'check_number': self.check_number,
            'bank_name': self.bank_name,
            'amount': self.amount,
            'issue_date': self.issue_date,
            'due_date': self.due_date,
            'status': self.status,
            'direction': self.direction,
            'party_type': self.party_type,
            'party_id': self.party_id,
            'party_name': self.party_name,
            'notes': self.notes
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Check':
        """إنشاء من قاموس"""
        return Check(
            id=data['id'],
            check_number=data['check_number'],
            bank_name=data['bank_name'],
            amount=data['amount'],
            issue_date=data['issue_date'],
            due_date=data['due_date'],
            status=data.get('status', 'pending'),
            direction=data.get('direction', 'outgoing'),
            party_type=data.get('party_type', 'supplier'),
            party_id=data.get('party_id', ''),
            party_name=data.get('party_name', ''),
            notes=data.get('notes', '')
        )
