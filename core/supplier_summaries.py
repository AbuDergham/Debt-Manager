"""
حساب ملخصات أرصدة الموردين
Supplier summaries calculation engine
"""
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional

from .models import (
    Supplier, PurchaseItem, SupplierPayment,
    SupplierSummary, Check
)
from .storage import StorageManager


class SupplierSummaryEngine:
    """
    محرك حساب ملخصات الموردين
    Engine for calculating supplier account summaries
    """
    
    def __init__(self, storage: StorageManager):
        self.storage = storage
    
    def calculate_supplier_summary(self, supplier_id: str) -> SupplierSummary:
        """
        حساب ملخص مورد واحد
        رصيد المورد = مجموع المشتريات الآجلة - مجموع الدفعات

        Calculate summary for a single supplier
        Balance = total credit purchases - total payments
        """
        # المشتريات الآجلة فقط
        items = self.storage.get_supplier_purchase_items(supplier_id)
        total_purchases = sum(
            item.total_decimal for item in items
            if item.payment_method == "credit"
        )
        
        # الدفعات
        payments = self.storage.get_supplier_payments(supplier_id)
        total_payments = sum(p.amount_decimal for p in payments)
        
        # الشيكات المصروفة الصادرة لهذا المورد
        checks = self.storage.load_checks()
        cashed_checks_total = sum(
            c.amount_decimal for c in checks
            if c.party_id == supplier_id
            and c.party_type == "supplier"
            and c.direction == "outgoing"
            and c.status == "cashed"
        )
        
        # إجمالي المدفوع = الدفعات المباشرة + الشيكات المصروفة
        effective_payments = total_payments + cashed_checks_total
        
        # الرصيد = المشتريات الآجلة - المدفوع
        balance = total_purchases - effective_payments
        
        return SupplierSummary(
            balance=f"{balance:.2f}",
            total_purchases=f"{total_purchases:.2f}",
            total_payments=f"{effective_payments:.2f}",
            last_update=datetime.now().isoformat()
        )
    
    def recalculate_all_summaries(self) -> Dict[str, SupplierSummary]:
        """
        إعادة حساب جميع ملخصات الموردين
        Recalculate all supplier summaries
        """
        suppliers = self.storage.load_suppliers()
        summaries = {}
        
        for supplier in suppliers:
            summaries[supplier.id] = self.calculate_supplier_summary(supplier.id)
        
        # حفظ الملخصات
        self.storage.save_supplier_summaries(summaries)
        
        return summaries
    
    def get_total_supplier_balance(self) -> Decimal:
        """
        الحصول على إجمالي أرصدة جميع الموردين
        Get total balance across all suppliers
        """
        summaries = self.storage.load_supplier_summaries()
        return sum(
            s.balance_decimal for s in summaries.values()
        )
    
    def get_supplier_running_balance(self, supplier_id: str) -> list:
        """
        حساب الرصيد التراكمي للمورد
        Calculate running balance for a supplier ledger
        
        Returns list of (type, date, description, amount, running_balance) tuples
        """
        items = self.storage.get_supplier_purchase_items(supplier_id)
        payments = self.storage.get_supplier_payments(supplier_id)
        orders = {o.id: o for o in self.storage.load_purchase_orders()}
        
        # دمج المشتريات والدفعات في قائمة واحدة مع ترتيب بالتاريخ
        entries = []
        
        for item in items:
            if item.payment_method == "credit":  # فقط الآجل
                order = orders.get(item.order_id)
                order_date = order.date if order else datetime.now().isoformat()
                entries.append({
                    'type': 'purchase',
                    'date': order_date,
                    'description': f"{item.item_name} ({item.quantity} عدد, {item.weight} كغ)",
                    'amount': item.total_decimal,
                    'order_id': item.order_id
                })
        
        for payment in payments:
            method_ar = {
                'cash': 'نقدي',
                'transfer': 'تحويل',
                'check': 'شيك'
            }.get(payment.payment_method, payment.payment_method)
            
            entries.append({
                'type': 'payment',
                'date': payment.date,
                'description': f"دفعة ({method_ar})",
                'amount': payment.amount_decimal,
                'payment_id': payment.id
            })
        
        # ترتيب بالتاريخ
        entries.sort(key=lambda e: e['date'])
        
        # حساب الرصيد التراكمي
        running_balance = Decimal("0")
        result = []
        
        for entry in entries:
            if entry['type'] == 'purchase':
                running_balance += entry['amount']
            else:  # payment
                running_balance -= entry['amount']
            
            result.append({
                'type': entry['type'],
                'date': entry['date'],
                'description': entry['description'],
                'amount': entry['amount'],
                'running_balance': running_balance
            })
        
        return result
