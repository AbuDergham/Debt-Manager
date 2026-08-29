"""
تركيبات pytest مشتركة
Shared pytest fixtures

كل اختبار يعمل على مجلد مؤقت معزول. ممنوع منعاً باتاً أن يلمس أي اختبار
مجلد data/ الحقيقي — التطبيق يعمل على بيانات محل فعلية.
"""
from datetime import datetime

import pytest

from core.models import Customer, Entry, Supplier
from core.storage import StorageManager


@pytest.fixture
def data_folder(tmp_path):
    """مجلد بيانات معزول لكل اختبار"""
    return tmp_path / "data"


@pytest.fixture
def storage(data_folder):
    """مدير تخزين يعمل على المجلد المعزول"""
    return StorageManager(data_folder=data_folder)


# ---------- بنّاؤون مساعدون ----------

def make_customer(cid="ahmad_1234", name="أحمد", **overrides) -> Customer:
    """عميل صالح للاختبار"""
    fields = dict(id=cid, name=name)
    fields.update(overrides)
    return Customer(**fields)


def make_entry(customer_id="ahmad_1234", **overrides) -> Entry:
    """حركة صالحة للاختبار، مع إمكانية تجاوز أي حقل"""
    fields = dict(
        customer_id=customer_id,
        type="purchase",
        amount="100.00",
        date=datetime(2026, 1, 15, 10, 30).isoformat(),
        desc="أغراض",
        pay_method="cash",
    )
    fields.update(overrides)
    return Entry(**fields)


def make_supplier(sid="murad_1", name="مراد", **overrides) -> Supplier:
    """مورد صالح للاختبار"""
    fields = dict(id=sid, name=name)
    fields.update(overrides)
    return Supplier(**fields)
