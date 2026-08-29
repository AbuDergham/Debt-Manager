"""
محرك حساب الملخصات
Summaries calculation engine
"""
from decimal import Decimal
from datetime import datetime
from typing import List, Dict
from .models import Entry, Summary, Customer
from .utils import decimal_to_str, is_same_day, is_same_month, get_current_datetime_iso


def calculate_customer_summary(customer_id: str, entries: List[Entry]) -> Summary:
    """
    حساب ملخص عميل معين
    Calculate summary for a specific customer
    
    Args:
        customer_id: معرف العميل
        entries: جميع الإدخالات (سيتم تصفية إدخالات هذا العميل فقط)
    
    Returns:
        Summary object with balance, today_sales, month_sales
    """
    # تصفية إدخالات هذا العميل فقط
    customer_entries = [e for e in entries if e.customer_id == customer_id]
    
    if not customer_entries:
        return Summary.empty()
    
    # التاريخ والوقت الحالي
    now = datetime.now()
    
    # المتغيرات للحسابات
    balance = Decimal("0.00")
    today_sales = Decimal("0.00")
    month_sales = Decimal("0.00")
    
    for entry in customer_entries:
        entry_date = entry.datetime
        
        # حساب الرصيد الكلي (الشراء موجب، الدفع سالب)
        balance += entry.signed_amount
        
        # حساب مبيعات اليوم (الشراء فقط)
        if entry.type == "purchase" and is_same_day(entry_date, now):
            today_sales += entry.amount_decimal
        
        # حساب مبيعات الشهر (الشراء فقط)
        if entry.type == "purchase" and is_same_month(entry_date, now):
            month_sales += entry.amount_decimal
    
    return Summary(
        balance=decimal_to_str(balance),
        today_sales=decimal_to_str(today_sales),
        month_sales=decimal_to_str(month_sales),
        last_update=get_current_datetime_iso()
    )


def recalculate_all_summaries(customers: List[Customer], entries: List[Entry]) -> Dict[str, Summary]:
    """
    إعادة حساب جميع الملخصات من البداية
    Recalculate all summaries from scratch
    
    هذه الدالة تُستخدم لإعادة بناء summaries.json بالكامل
    This function is used to rebuild summaries.json from scratch
    
    Args:
        customers: قائمة جميع العملاء
        entries: قائمة جميع الإدخالات
    
    Returns:
        قاموس {customer_id: Summary}
    """
    summaries = {}
    
    for customer in customers:
        summaries[customer.id] = calculate_customer_summary(customer.id, entries)
    
    return summaries


def calculate_running_balances(entries: List[Entry]) -> List[Decimal]:
    """
    حساب الرصيد التراكمي بعد كل إدخال
    Calculate running balance after each entry
    
    هذه الدالة تُستخدم لعرض الرصيد في جدول الإدخالات
    This function is used to display balance in the entries table
    
    Args:
        entries: قائمة الإدخالات (يجب أن تكون مرتبة حسب التاريخ)
    
    Returns:
        قائمة من الأرصدة التراكمية
    """
    running_balances = []
    current_balance = Decimal("0.00")
    
    for entry in entries:
        current_balance += entry.signed_amount
        running_balances.append(current_balance)
    
    return running_balances
