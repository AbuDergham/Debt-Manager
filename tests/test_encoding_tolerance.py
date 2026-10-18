"""
تحمّل علامة BOM عند القراءة

حادثة حقيقية (١٨ أكتوبر ٢٠٢٦): فُتح `checks.json` بمحرّر نصوص خارجي فأضاف
علامة BOM، فرفضها `read_json` ومات التطبيق عند الإقلاع برسالة إنجليزية.
المحتوى كان JSON صالحاً تماماً — ثلاث بايتات غير مرئية أوقفت المحل.
"""
import json

import pytest

from conftest import make_customer, make_entry
from core.storage import atomic_write_json, atomic_write_jsonl, read_json, read_jsonl

BOM = b"\xef\xbb\xbf"


def test_read_json_accepts_bom(tmp_path):
    """الملف الذي كسر التطبيق في المحل"""
    path = tmp_path / "checks.json"
    path.write_bytes(BOM + b'[{"id": "CHK_1", "bank_name": "\xd9\x81\xd9\x84\xd8\xb3\xd8\xb7\xd9\x8a\xd9\x86"}]')

    data = read_json(path)

    assert data[0]["id"] == "CHK_1"
    assert data[0]["bank_name"] == "فلسطين"


def test_read_json_accepts_bom_with_leading_space(tmp_path):
    """الملف الفعلي كان <BOM><مسافة>[ — المحرّر ترك مسافة"""
    path = tmp_path / "checks.json"
    path.write_bytes(BOM + b' [{"id": "CHK_1"}]')

    assert read_json(path)[0]["id"] == "CHK_1"


def test_read_json_still_reads_plain_files(tmp_path):
    """الملفات السليمة تُقرأ كما كانت — لا تغيير في السلوك"""
    path = tmp_path / "customers.json"
    path.write_bytes(b'[{"id": "c1", "name": "\xd8\xae\xd9\x84\xd9\x8a\xd9\x84"}]')

    assert read_json(path)[0]["name"] == "خليل"


def test_read_json_still_rejects_real_corruption(tmp_path):
    """تحمّل الـBOM لا يعني تحمّل JSON تالف فعلاً"""
    path = tmp_path / "broken.json"
    path.write_bytes(BOM + b"{ this is not json")

    with pytest.raises(ValueError, match="Invalid JSON"):
        read_json(path)


def test_read_jsonl_accepts_bom(tmp_path):
    """entries.jsonl لو أُصيب بنفس الشيء"""
    path = tmp_path / "entries.jsonl"
    path.write_bytes(BOM + b'{"a": 1}\n{"a": 2}\n')

    records = read_jsonl(path)

    assert [r["a"] for r in records] == [1, 2]


def test_read_jsonl_bom_does_not_corrupt_first_record(tmp_path):
    """البايتات الثلاث تُزال، لا تُلحق بأول مفتاح"""
    path = tmp_path / "entries.jsonl"
    path.write_bytes(BOM + b'{"customer_id": "c1", "amount": "100.00"}\n')

    record = read_jsonl(path)[0]

    assert "customer_id" in record          # لا "﻿customer_id"
    assert list(record)[0] == "customer_id"


def test_audit_log_accepts_bom(tmp_path):
    """سجل التدقيق يقرأ بنفس الطريقة"""
    from core.audit import AuditManager

    (tmp_path / "audit.jsonl").write_bytes(
        BOM + b'{"timestamp": "2026-10-18T14:00:00", "action": "create", '
              b'"entity_type": "customer", "entity_id": "c1", '
              b'"old_data": null, "new_data": null}\n')

    history = AuditManager(tmp_path).get_history()

    assert len(history) == 1
    assert history[0].entity_id == "c1"


# ---------- الكتابة يجب ألا تتغيّر ----------

def test_atomic_write_json_never_adds_bom(tmp_path):
    """
    حرج: لو استُعمل utf-8-sig في الكتابة لأضاف BOM لكل ملفات المحل،
    فصار الإصلاح هو المشكلة.
    """
    path = tmp_path / "out.json"
    atomic_write_json(path, [{"name": "خليل"}])

    raw = path.read_bytes()
    assert not raw.startswith(BOM)
    assert raw.startswith(b"[")


def test_atomic_write_jsonl_never_adds_bom(tmp_path):
    path = tmp_path / "out.jsonl"
    atomic_write_jsonl(path, [{"name": "خليل"}])

    assert not path.read_bytes().startswith(BOM)


def test_audit_write_never_adds_bom(tmp_path):
    from core.audit import AuditManager

    AuditManager(tmp_path).log_action("create", "customer", "c1")

    assert not (tmp_path / "audit.jsonl").read_bytes().startswith(BOM)


def test_round_trip_through_bom_file_stays_clean(tmp_path, storage):
    """قراءة ملف فيه BOM ثم الكتابة تُنتج ملفاً نظيفاً"""
    storage.add_customer(make_customer())

    # محاكاة تحرير خارجي أضاف BOM
    raw = storage.customers_file.read_bytes()
    storage.customers_file.write_bytes(BOM + raw)

    customers = storage.load_customers()          # يُقرأ رغم الـBOM
    storage.save_customers(customers)             # يُكتب نظيفاً

    assert not storage.customers_file.read_bytes().startswith(BOM)
    assert len(storage.load_customers()) == 1


def test_app_survives_the_exact_shop_file(tmp_path, storage):
    """
    إعادة إنتاج الحادثة بالضبط: checks.json بـ BOM ومسافة بادئة.
    """
    from core.models import Check

    shop_bytes = (
        BOM + b' [\r\n  {\r\n    "id": "CHK_20261010_195638_b693b4",\r\n'
              b'    "check_number": "1",\r\n'
              b'    "bank_name": "\xd9\x81\xd9\x84\xd8\xb3\xd8\xb7\xd9\x8a\xd9\x86",\r\n'
              b'    "amount": "1000.00",\r\n'
              b'    "issue_date": "2027-10-10T00:00:00",\r\n'
              b'    "due_date": "2027-02-25T00:00:00",\r\n'
              b'    "status": "pending",\r\n'
              b'    "direction": "incoming",\r\n'
              b'    "party_type": "supplier",\r\n'
              b'    "party_id": "SUP_x",\r\n'
              b'    "party_name": "x",\r\n'
              b'    "notes": ""\r\n  }\r\n]\r\n'
    )
    storage.checks_file.write_bytes(shop_bytes)

    checks = storage.load_checks()

    assert len(checks) == 1
    assert checks[0].check_number == "1"
    assert checks[0].bank_name == "فلسطين"
