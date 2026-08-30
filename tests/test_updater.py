"""
اختبارات التحديث التلقائي

لا شبكة حقيقية: استجابات GitHub من نصوص ثابتة، والتنزيل من خادم HTTP محلي.
"""
import hashlib
import http.server
import json
import os
import socket
import threading
import urllib.error
from datetime import datetime
from pathlib import Path

import pytest

from core.updater import (
    ReleaseInfo,
    check_for_update,
    cleanup_old_exe,
    download_asset,
    install_update,
    is_newer,
    parse_version,
    verify_download,
)


# ---------- مقارنة الإصدارات ----------

@pytest.mark.parametrize("text,expected", [
    ("2.1.0", (2, 1, 0)),
    ("v2.1.0", (2, 1, 0)),
    ("V2.1.0", (2, 1, 0)),
    ("2.1", (2, 1)),
    ("10.0.3", (10, 0, 3)),
    ("  2.1.0  ", (2, 1, 0)),
])
def test_parse_version(text, expected):
    assert parse_version(text) == expected


@pytest.mark.parametrize("candidate,current", [
    ("2.2.0", "2.1.0"),
    ("2.1.1", "2.1.0"),
    ("3.0.0", "2.9.9"),
    ("2.10.0", "2.9.0"),      # مقارنة رقمية لا نصّية: 10 > 9
    ("v2.2.0", "2.1.0"),
])
def test_is_newer_true(candidate, current):
    assert is_newer(candidate, current)


@pytest.mark.parametrize("candidate,current", [
    ("2.1.0", "2.1.0"),
    ("2.0.0", "2.1.0"),
    ("2.1.0", "2.2.0"),
    ("2.9.0", "2.10.0"),
])
def test_is_newer_false(candidate, current):
    assert not is_newer(candidate, current)


def test_is_newer_handles_garbage_version():
    """وسم إصدار غير قياسي لا يرمي استثناءً"""
    assert is_newer("nightly", "2.1.0") is False
    assert is_newer("2.2.0", "غير-صالح") is False


# ---------- تحليل استجابة GitHub ----------

def release_json(tag="v2.2.0", assets=None, body="ملاحظات الإصدار"):
    """استجابة بشكل واجهة GitHub الفعلي (فُحص على مستودع عام حقيقي)"""
    if assets is None:
        assets = [
            {"name": "Debt-Manager.exe", "size": 78770990,
             "browser_download_url": "https://example.test/Debt-Manager.exe"},
            {"name": "SHA256SUMS.txt", "size": 96,
             "browser_download_url": "https://example.test/SHA256SUMS.txt"},
        ]
    return json.dumps({
        "tag_name": tag,
        "name": tag,
        "body": body,
        "published_at": "2026-08-30T10:15:00Z",
        "assets": assets,
    }).encode("utf-8")


@pytest.fixture
def fake_api(monkeypatch):
    """يستبدل جلب الشبكة بردّ ثابت أو استثناء"""
    box = {}

    def fake_fetch(url, *, timeout, headers=None):
        if isinstance(box["response"], Exception):
            raise box["response"]
        return box["response"]

    monkeypatch.setattr("core.updater._http_get", fake_fetch)
    return box


def test_finds_newer_release(fake_api):
    fake_api["response"] = release_json("v2.2.0")

    info = check_for_update("2.1.0", owner="o", repo="r")

    assert info is not None
    assert info.version == "2.2.0"
    assert info.tag == "v2.2.0"
    assert info.size_bytes == 78770990
    assert info.download_url.endswith("Debt-Manager.exe")
    assert info.checksum_url.endswith("SHA256SUMS.txt")
    assert info.notes == "ملاحظات الإصدار"


def test_returns_none_when_same_version(fake_api):
    fake_api["response"] = release_json("v2.1.0")
    assert check_for_update("2.1.0", owner="o", repo="r") is None


def test_returns_none_when_release_is_older(fake_api):
    fake_api["response"] = release_json("v2.0.0")
    assert check_for_update("2.1.0", owner="o", repo="r") is None


def test_returns_none_when_exe_asset_missing(fake_api):
    """إصدار بلا ملف exe لا ينفع للتحديث"""
    fake_api["response"] = release_json("v2.2.0", assets=[
        {"name": "source.zip", "size": 100,
         "browser_download_url": "https://example.test/source.zip"}])
    assert check_for_update("2.1.0", owner="o", repo="r") is None


def test_checksum_url_is_optional(fake_api):
    fake_api["response"] = release_json("v2.2.0", assets=[
        {"name": "Debt-Manager.exe", "size": 10,
         "browser_download_url": "https://example.test/Debt-Manager.exe"}])
    info = check_for_update("2.1.0", owner="o", repo="r")
    assert info is not None and info.checksum_url is None


# ---------- الفشل الصامت ----------

@pytest.mark.parametrize("failure", [
    urllib.error.URLError("لا إنترنت"),
    urllib.error.HTTPError("u", 403, "rate limit", {}, None),
    urllib.error.HTTPError("u", 404, "not found", {}, None),
    urllib.error.HTTPError("u", 500, "server error", {}, None),
    socket.timeout("انتهت المهلة"),
    TimeoutError("انتهت المهلة"),
    OSError("الشبكة غير متاحة"),
])
def test_network_failure_is_silent(fake_api, failure):
    """
    القاعدة: التطبيق يعمل بلا إنترنت. أي فشل شبكي يرجع None بلا استثناء.
    """
    fake_api["response"] = failure
    assert check_for_update("2.1.0", owner="o", repo="r") is None


@pytest.mark.parametrize("bad", [b"", b"not json", b"{}", b'{"tag_name": "v2.2.0"}',
                                 b'{"assets": []}', b"null"])
def test_malformed_response_is_silent(fake_api, bad):
    fake_api["response"] = bad
    assert check_for_update("2.1.0", owner="o", repo="r") is None


# ---------- خادم محلي للتنزيل ----------

class RangeHandler(http.server.SimpleHTTPRequestHandler):
    """خادم يدعم ترويسة Range — لاختبار الاستئناف"""

    payload = b""
    supports_range = True

    def log_message(self, *args):
        pass

    def do_GET(self):
        data = type(self).payload
        rng = self.headers.get("Range")

        if rng and type(self).supports_range:
            start = int(rng.split("=")[1].split("-")[0])
            chunk = data[start:]
            self.send_response(206)
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Content-Range",
                             f"bytes {start}-{len(data)-1}/{len(data)}")
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(data)


@pytest.fixture
def http_server():
    """
    خادم محلي يقدّم محتوى قابلاً للضبط

    الحمولة أكبر من عدة أضعاف CHUNK_SIZE عمداً، وإلا وصلت كلها في قطعة
    واحدة فلم تُختبر حلقة التقدّم ولا الإلغاء في منتصف التنزيل.
    """
    from core.updater import CHUNK_SIZE
    RangeHandler.payload = b"MZ" + os.urandom(CHUNK_SIZE * 5)
    RangeHandler.supports_range = True

    server = http.server.HTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{server.server_port}/payload.bin", RangeHandler

    server.shutdown()
    server.server_close()


# ---------- التنزيل ----------

def test_download_writes_complete_file(http_server, tmp_path):
    url, handler = http_server
    dest = tmp_path / "app.exe"

    download_asset(url, dest, expected_size=len(handler.payload))

    assert dest.read_bytes() == handler.payload


def test_download_reports_progress(http_server, tmp_path):
    url, handler = http_server
    seen = []

    download_asset(url, tmp_path / "app.exe", expected_size=len(handler.payload),
                   progress_cb=lambda done, total: seen.append((done, total)))

    assert seen, "لم تُستدعَ دالة التقدّم"
    assert seen[-1][0] == len(handler.payload)
    assert all(total == len(handler.payload) for _, total in seen)


def test_download_resumes_from_partial_file(http_server, tmp_path):
    """
    مع إنترنت ضعيف، انقطاع عند 90% يجب ألا يعني إعادة الـ75 ميجا من الصفر.
    """
    url, handler = http_server
    dest = tmp_path / "app.exe"
    part = dest.with_suffix(dest.suffix + ".part")

    # حاكِ تنزيلاً سابقاً توقّف بعد 30 ألف بايت
    part.write_bytes(handler.payload[:30_000])

    downloaded = []
    download_asset(url, dest, expected_size=len(handler.payload),
                   progress_cb=lambda done, total: downloaded.append(done))

    assert dest.read_bytes() == handler.payload
    # أول تقرير تقدّم يبدأ من حيث توقّف، لا من الصفر
    assert downloaded[0] >= 30_000


def test_download_restarts_when_server_ignores_range(http_server, tmp_path):
    """خادم لا يدعم Range: نبدأ من جديد بدل أن نُنتج ملفاً تالفاً"""
    url, handler = http_server
    handler.supports_range = False

    dest = tmp_path / "app.exe"
    dest.with_suffix(dest.suffix + ".part").write_bytes(b"XXXX" * 100)

    download_asset(url, dest, expected_size=len(handler.payload))

    assert dest.read_bytes() == handler.payload


def test_download_can_be_cancelled(http_server, tmp_path):
    url, handler = http_server
    dest = tmp_path / "app.exe"

    with pytest.raises(InterruptedError):
        download_asset(url, dest, expected_size=len(handler.payload),
                       should_cancel=lambda: True)

    assert not dest.exists()


def test_cancelled_download_keeps_partial_for_resume(http_server, tmp_path):
    """الإلغاء لا يرمي ما نُزّل — يبقى للاستئناف لاحقاً"""
    url, handler = http_server
    dest = tmp_path / "app.exe"
    calls = {"n": 0}

    def cancel_after_first_chunk():
        calls["n"] += 1
        return calls["n"] > 2

    with pytest.raises(InterruptedError):
        download_asset(url, dest, expected_size=len(handler.payload),
                       should_cancel=cancel_after_first_chunk)

    assert dest.with_suffix(dest.suffix + ".part").exists()


def test_download_rejects_wrong_size(http_server, tmp_path):
    url, handler = http_server
    with pytest.raises(ValueError, match="الحجم"):
        download_asset(url, tmp_path / "app.exe", expected_size=999_999)


# ---------- التحقق ----------

def test_verify_accepts_correct_checksum(tmp_path):
    path = tmp_path / "app.exe"
    data = b"hello world"
    path.write_bytes(data)

    verify_download(path, expected_size=len(data),
                    expected_sha256=hashlib.sha256(data).hexdigest())


def test_verify_rejects_wrong_checksum(tmp_path):
    path = tmp_path / "app.exe"
    path.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="البصمة"):
        verify_download(path, expected_size=9, expected_sha256="0" * 64)


def test_verify_rejects_wrong_size(tmp_path):
    path = tmp_path / "app.exe"
    path.write_bytes(b"short")
    with pytest.raises(ValueError, match="الحجم"):
        verify_download(path, expected_size=9999, expected_sha256=None)


def test_verify_is_case_insensitive_on_checksum(tmp_path):
    path = tmp_path / "app.exe"
    data = b"hello"
    path.write_bytes(data)
    verify_download(path, expected_size=len(data),
                    expected_sha256=hashlib.sha256(data).hexdigest().upper())


def test_verify_skips_checksum_when_unavailable(tmp_path):
    """إصدار بلا ملف بصمات: نتحقق من الحجم فقط"""
    path = tmp_path / "app.exe"
    path.write_bytes(b"12345")
    verify_download(path, expected_size=5, expected_sha256=None)


# ---------- التثبيت والتراجع ----------

def test_install_swaps_files(tmp_path):
    target = tmp_path / "Debt-Manager.exe"
    target.write_bytes(b"OLD VERSION")
    new = tmp_path / "Debt-Manager.new.exe"
    new.write_bytes(b"NEW VERSION")

    old_path = install_update(new, target)

    assert target.read_bytes() == b"NEW VERSION"
    assert old_path.read_bytes() == b"OLD VERSION"
    assert not new.exists()


def test_install_rolls_back_when_move_fails(tmp_path, monkeypatch):
    """
    إن فشل وضع الملف الجديد، يجب أن يعود الاسم الأصلي للنسخة القديمة —
    وإلا بقي المستخدم بلا تطبيق يعمل.
    """
    target = tmp_path / "Debt-Manager.exe"
    target.write_bytes(b"OLD VERSION")
    new = tmp_path / "Debt-Manager.new.exe"
    new.write_bytes(b"NEW VERSION")

    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:                 # الاستبدال الثاني هو وضع الجديد
            raise OSError("القرص ممتلئ")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)

    with pytest.raises(OSError):
        install_update(new, target)

    assert target.exists(), "التطبيق اختفى — التراجع فشل"
    assert target.read_bytes() == b"OLD VERSION"


def test_install_removes_stale_old_file_first(tmp_path):
    """بقايا .old.exe من تحديث سابق لا تمنع تحديثاً جديداً"""
    target = tmp_path / "Debt-Manager.exe"
    target.write_bytes(b"CURRENT")
    (tmp_path / "Debt-Manager.old.exe").write_bytes(b"ANCIENT")
    new = tmp_path / "Debt-Manager.new.exe"
    new.write_bytes(b"NEW")

    old_path = install_update(new, target)

    assert target.read_bytes() == b"NEW"
    assert old_path.read_bytes() == b"CURRENT"


# ---------- تنظيف الإصدار القديم ----------

def test_cleanup_removes_old_exe(tmp_path):
    target = tmp_path / "Debt-Manager.exe"
    target.write_bytes(b"NEW")
    old = tmp_path / "Debt-Manager.old.exe"
    old.write_bytes(b"OLD")

    assert cleanup_old_exe(target) is True
    assert not old.exists()


def test_cleanup_is_noop_when_nothing_to_clean(tmp_path):
    target = tmp_path / "Debt-Manager.exe"
    target.write_bytes(b"NEW")
    assert cleanup_old_exe(target) is False


def test_cleanup_survives_locked_file(tmp_path, monkeypatch):
    """ملف مقفول لا يُسقط التطبيق — يُحاول مرة أخرى في الإقلاع التالي"""
    target = tmp_path / "Debt-Manager.exe"
    target.write_bytes(b"NEW")
    (tmp_path / "Debt-Manager.old.exe").write_bytes(b"OLD")

    def locked(path):
        raise PermissionError("الملف مستخدم")

    monkeypatch.setattr(os, "remove", locked)
    assert cleanup_old_exe(target) is False


# ---------- تحليل ملف البصمات ----------

def test_parse_checksums_finds_our_file():
    from core.updater import parse_checksums

    text = ("d2f4c1  SHA256SUMS.txt\n"
            "abc123def456  Debt-Manager.exe\n")
    assert parse_checksums(text, "Debt-Manager.exe") == "abc123def456"


def test_parse_checksums_handles_star_prefix():
    """صيغة sha256sum الثنائية تسبق الاسم بنجمة"""
    from core.updater import parse_checksums
    assert parse_checksums("abc  *Debt-Manager.exe\n", "Debt-Manager.exe") == "abc"


def test_parse_checksums_returns_none_when_absent():
    from core.updater import parse_checksums
    assert parse_checksums("abc  other.exe\n", "Debt-Manager.exe") is None


def test_parse_checksums_handles_empty_input():
    from core.updater import parse_checksums
    assert parse_checksums("", "Debt-Manager.exe") is None
