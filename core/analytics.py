"""
محرك التحليلات
Analytics engine for business insights
"""
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from .models import Entry, Customer
from .storage import StorageManager


class AnalyticsEngine:
    """
    محرك التحليلات للحصول على رؤى الأعمال
    Analytics engine for business insights
    """
    
    def __init__(self, storage: StorageManager):
        self.storage = storage
    
    def get_top_customers_by_balance(self, limit: int = 5) -> List[Tuple[Customer, Decimal]]:
        """
        الحصول على أعلى العملاء برصيد
        Get top customers by outstanding balance
        """
        customers = self.storage.load_customers()
        entries = self.storage.load_entries()
        
        # حساب الرصيد لكل عميل
        balances: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        
        for entry in entries:
            balances[entry.customer_id] += entry.signed_amount
        
        # إنشاء قائمة (عميل، رصيد)
        customer_balances = []
        customer_map = {c.id: c for c in customers}
        
        for customer_id, balance in balances.items():
            if customer_id in customer_map and balance > 0:
                customer_balances.append((customer_map[customer_id], balance))
        
        # ترتيب تنازلي حسب الرصيد
        customer_balances.sort(key=lambda x: x[1], reverse=True)
        
        return customer_balances[:limit]
    
    def get_customers_exceeding_credit_limit(self) -> List[Tuple[Customer, Decimal, Decimal]]:
        """
        الحصول على العملاء الذين تجاوزوا حد الائتمان
        Returns: [(customer, balance, credit_limit)]
        """
        customers = self.storage.load_customers()
        entries = self.storage.load_entries()
        
        # حساب الرصيد لكل عميل
        balances: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for entry in entries:
            balances[entry.customer_id] += entry.signed_amount
        
        results = []
        for customer in customers:
            credit_limit = customer.credit_limit_decimal
            if credit_limit > 0:  # 0 يعني غير محدود
                balance = balances.get(customer.id, Decimal("0"))
                if balance > credit_limit:
                    results.append((customer, balance, credit_limit))
        
        return results
    
    def get_total_stats(self) -> Dict[str, Decimal]:
        """
        الحصول على إحصائيات إجمالية
        Get overall statistics
        """
        customers = self.storage.load_customers()
        entries = self.storage.load_entries()
        
        total_sales = Decimal("0")
        total_payments = Decimal("0")
        today_sales = Decimal("0")
        today_payments = Decimal("0")
        
        today = datetime.now().date()
        
        for entry in entries:
            if entry.type == "purchase":
                total_sales += entry.amount_decimal
                if entry.datetime.date() == today:
                    today_sales += entry.amount_decimal
            else:
                total_payments += entry.amount_decimal
                if entry.datetime.date() == today:
                    today_payments += entry.amount_decimal
        
        return {
            "total_customers": Decimal(str(len(customers))),
            "total_sales": total_sales,
            "total_payments": total_payments,
            "total_outstanding": total_sales - total_payments,
            "today_sales": today_sales,
            "today_payments": today_payments
        }
    
    def analyze_payment_behavior(self, customer_id: str) -> str:
        """
        تحليل سلوك الدفع للعميل
        Analyze customer payment behavior
        
        Returns: "excellent", "good", "irregular", "poor"
        """
        entries = [e for e in self.storage.load_entries() if e.customer_id == customer_id]
        
        if not entries:
            return "no_data"
        
        purchases = [e for e in entries if e.type == "purchase"]
        payments = [e for e in entries if e.type == "payment"]
        
        if not purchases:
            return "no_purchases"
        
        if not payments:
            return "poor"
        
        # حساب نسبة السداد
        total_purchased = sum(e.amount_decimal for e in purchases)
        total_paid = sum(e.amount_decimal for e in payments)
        
        if total_purchased == 0:
            return "no_data"
        
        payment_ratio = total_paid / total_purchased
        
        if payment_ratio >= Decimal("0.9"):
            return "excellent"
        elif payment_ratio >= Decimal("0.7"):
            return "good"  
        elif payment_ratio >= Decimal("0.5"):
            return "irregular"
        else:
            return "poor"
    
    def get_payment_behavior_label(self, behavior: str) -> str:
        """ترجمة سلوك الدفع إلى نص عربي"""
        labels = {
            "excellent": "ممتاز ✅",
            "good": "جيد 👍",
            "irregular": "غير منتظم ⚠️",
            "poor": "ضعيف ❌",
            "no_data": "لا توجد بيانات",
            "no_purchases": "لا توجد مشتريات"
        }
        return labels.get(behavior, behavior)
    
    def search_entries(
        self,
        query: str = "",
        customer_id: Optional[str] = None,
        entry_type: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Tuple[Entry, Customer]]:
        """
        البحث في جميع الإدخالات
        Search across all entries
        """
        entries = self.storage.load_entries()
        customers = self.storage.load_customers()
        customer_map = {c.id: c for c in customers}
        
        results = []
        
        for entry in entries:
            # فلترة حسب العميل
            if customer_id and entry.customer_id != customer_id:
                continue
            
            # فلترة حسب النوع
            if entry_type and entry.type != entry_type:
                continue
            
            # فلترة حسب المبلغ
            if min_amount and entry.amount_decimal < min_amount:
                continue
            if max_amount and entry.amount_decimal > max_amount:
                continue
            
            # فلترة حسب التاريخ
            if start_date and entry.datetime < start_date:
                continue
            if end_date and entry.datetime > end_date:
                continue
            
            # البحث النصي
            if query:
                query_lower = query.lower()
                customer = customer_map.get(entry.customer_id)
                customer_name = customer.name if customer else ""
                
                if not (
                    query_lower in entry.desc.lower() or
                    query_lower in customer_name.lower() or
                    query_lower in str(entry.amount) or
                    query_lower in entry.notes.lower()
                ):
                    continue
            
            customer = customer_map.get(entry.customer_id)
            if customer:
                results.append((entry, customer))
        
        # ترتيب من الأحدث
        results.sort(key=lambda x: x[0].datetime, reverse=True)
        
        return results
