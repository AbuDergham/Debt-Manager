"""
التحديث التلقائي عبر إصدارات GitHub
Auto-update via GitHub Releases

منطق صرف — **لا يستورد Qt**، فيُختبر وحده. الواجهة في ui/update_dialog.py.

المبدأ الحاكم
-------------
الفحص تلقائي ورخيص (بضعة كيلوبايت). التنزيل صريح وبموافقة المستخدم
(75 ميجا). مع إنترنت متقطّع، تنزيل هذا الحجم بلا استئذان تصرّف عدائي.

قاعدة غير قابلة للتفاوض
-----------------------
التطبيق يعمل بلا إنترنت. **أي فشل شبكي في الفحص يُبتلع بصمت** ويرجع None.
لا رسالة خطأ ولا تعطيل — صاحب المحل يسجّل ديونه، لا يهمّه أن GitHub بعيد.

استبدال التطبيق لنفسه على ويندوز
--------------------------------
ويندوز يرفض الكتابة فوق exe شغّال، لكنه **يسمح بإعادة تسميته** (مُتحقَّق
منه عملياً). فالتسلسل: أعد تسمية الحالي -> ضع الجديد مكان الاسم الأصلي ->
احذف القديم عند الإقلاع التالي. لا حاجة لبرنامج تحديث منفصل.
"""
import hashlib
import json
import os
import re
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .version import CHECKSUM_ASSET, EXE_NAME

# مهلة قصيرة: الفحص يجب ألا يؤخّر الإقلاع
DEFAULT_TIMEOUT = 5.0

# حجم القطعة عند التنزيل — يوازن بين تحديث التقدّم وكلفة الاستدعاءات
CHUNK_SIZE = 64 * 1024

_USER_AGENT = "Debt-Manager-Updater"

# الأخطاء المتوقّعة من الشبكة: كلها تعني «لا تحديث الآن»، لا «عطل»
_NETWORK_ERRORS = (urllib.error.URLError, urllib.error.HTTPError,
                   TimeoutError, OSError, ValueError)


@dataclass
class ReleaseInfo:
    """معلومات إصدار متاح - Available release info"""
    version: str                    # "2.2.0" بلا بادئة v
    tag: str                        # "v2.2.0"
    notes: str                      # ملاحظات الإصدار
    download_url: str
    size_bytes: int
    checksum_url: Optional[str]
    published_at: Optional[datetime]

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


# ------------------------------------------------- مقارنة الإصدارات

def parse_version(text: str) -> tuple:
    """
    تحويل نص إصدار إلى أرقام للمقارنة
    Parse a version string into comparable integers

    المقارنة رقمية لا نصّية: «2.10.0» أحدث من «2.9.0» رغم أن '1' < '9'.

    Returns:
        صف من الأرقام، أو صف فارغ إن كان النص غير صالح
    """
    cleaned = (text or "").strip().lstrip("vV")
    parts = re.findall(r"\d+", cleaned)
    if not parts or not re.match(r"^\d+(\.\d+)*$", cleaned):
        return ()
    return tuple(int(p) for p in parts)


def is_newer(candidate: str, current: str) -> bool:
    """
    هل الإصدار المرشَّح أحدث من الحالي؟
    Is the candidate version newer than the current one?

    وسم غير قياسي (مثل "nightly") يرجع False — لا نحدّث إلى ما لا نفهمه.
    """
    a, b = parse_version(candidate), parse_version(current)
    if not a or not b:
        return False
    return a > b


# ------------------------------------------------- الشبكة

def _http_get(url: str, *, timeout: float, headers: Optional[dict] = None) -> bytes:
    """جلب محتوى عنوان. دالة منفصلة ليسهل استبدالها في الاختبارات."""
    request = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def check_for_update(
    current_version: str,
    *,
    owner: str,
    repo: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[ReleaseInfo]:
    """
    فحص وجود إصدار أحدث
    Check whether a newer release exists

    **لا يرمي استثناءً أبداً.** أي فشل — لا إنترنت، مهلة، تجاوز حدّ
    الطلبات، استجابة تالفة — يرجع None بصمت.

    Returns:
        معلومات الإصدار الأحدث، أو None
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    try:
        raw = _http_get(url, timeout=timeout,
                        headers={"Accept": "application/vnd.github+json"})
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None

        tag = data.get("tag_name") or ""
        version = tag.lstrip("vV")
        if not is_newer(version, current_version):
            return None

        assets = data.get("assets") or []
        exe = next((a for a in assets if a.get("name") == EXE_NAME), None)
        if not exe or not exe.get("browser_download_url"):
            return None  # إصدار بلا ملف تنفيذي لا ينفع للتحديث

        checksum = next((a for a in assets if a.get("name") == CHECKSUM_ASSET), None)

        return ReleaseInfo(
            version=version,
            tag=tag,
            notes=(data.get("body") or "").strip(),
            download_url=exe["browser_download_url"],
            size_bytes=int(exe.get("size") or 0),
            checksum_url=checksum.get("browser_download_url") if checksum else None,
            published_at=_parse_iso(data.get("published_at")),
        )

    except _NETWORK_ERRORS:
        return None
    except Exception:
        # حتى الأخطاء غير المتوقّعة: الفحص ميزة كمالية، لا تُسقط التطبيق
        return None


def _parse_iso(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_checksum(checksum_url: str, *, timeout: float = 15.0) -> Optional[str]:
    """
    جلب بصمة الملف التنفيذي من ملف البصمات المنشور مع الإصدار

    Returns:
        البصمة، أو None إن تعذّر الجلب — عندها نكتفي بالتحقق من الحجم
    """
    try:
        text = _http_get(checksum_url, timeout=timeout).decode("utf-8")
        return parse_checksums(text, EXE_NAME)
    except Exception:
        return None


def parse_checksums(text: str, filename: str) -> Optional[str]:
    """
    استخراج بصمة ملف من مخرَج sha256sum
    Extract one file's hash from sha256sum output

    الصيغة: «<البصمة>  <الاسم>» — وقد يسبق الاسمَ نجمةٌ في الوضع الثنائي.
    """
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == filename:
            return parts[0]
    return None


# ------------------------------------------------- التنزيل

def download_asset(
    url: str,
    dest: Path,
    *,
    expected_size: int,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    timeout: float = 30.0,
) -> Path:
    """
    تنزيل ملف مع استئناف وتقدّم وإلغاء
    Download a file with resume, progress, and cancellation

    ينزّل إلى «<dest>.part» ثم يعيد تسميته عند الاكتمال، فلا يُخلَط ملف
    ناقص بملف تام. إن وُجد ملف جزئي من محاولة سابقة، يُكمَّل عبر ترويسة
    Range — مع إنترنت ضعيف، انقطاع عند 90% يجب ألا يعني إعادة 75 ميجا.

    Args:
        expected_size: الحجم المعلن من الواجهة — يُتحقَّق منه بعد التنزيل
        progress_cb: تُستدعى بـ (المنزَّل، الإجمالي)
        should_cancel: تُستدعى دورياً؛ إن أرجعت True رُفع InterruptedError

    Raises:
        InterruptedError: ألغى المستخدم. الملف الجزئي يبقى للاستئناف.
        ValueError: الحجم النهائي لا يطابق المتوقّع
    """
    dest = Path(dest)
    part = dest.with_suffix(dest.suffix + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)

    resume_from = part.stat().st_size if part.exists() else 0
    if resume_from >= expected_size > 0:
        resume_from = 0  # جزئي أكبر من المتوقّع = تالف، ابدأ من جديد

    headers = {"User-Agent": _USER_AGENT}
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        # خادم تجاهل Range ورد بالمحتوى كاملاً: ابدأ من الصفر بدل أن
        # نُنتج ملفاً تالفاً بلصق المحتوى على الجزء القديم
        if resume_from and response.status != 206:
            resume_from = 0

        mode = "ab" if resume_from else "wb"
        downloaded = resume_from

        with open(part, mode) as handle:
            while True:
                if should_cancel and should_cancel():
                    raise InterruptedError("أُلغي التنزيل")

                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break

                handle.write(chunk)
                downloaded += len(chunk)

                if progress_cb:
                    progress_cb(downloaded, expected_size or downloaded)

    actual = part.stat().st_size
    if expected_size and actual != expected_size:
        part.unlink(missing_ok=True)
        raise ValueError(
            f"الحجم لا يطابق المتوقّع: {actual:,} بدل {expected_size:,} بايت")

    os.replace(part, dest)
    return dest


# ------------------------------------------------- التحقق

def verify_download(path: Path, expected_size: int,
                    expected_sha256: Optional[str]) -> None:
    """
    التحقق من سلامة الملف المنزَّل
    Verify the downloaded file

    يحمي من **التنزيل الناقص أو التالف** — وهو الخطر الحقيقي مع إنترنت
    ضعيف. لا يحمي من اختراق حساب GitHub، لأن البصمة منشورة بجانب الملف
    نفسه؛ الحماية من ذلك تحتاج توقيعاً رقمياً بشهادة.

    Raises:
        ValueError: الحجم أو البصمة لا تطابق
    """
    path = Path(path)
    actual_size = path.stat().st_size

    if expected_size and actual_size != expected_size:
        raise ValueError(
            f"الحجم لا يطابق: {actual_size:,} بدل {expected_size:,} بايت")

    if not expected_sha256:
        return

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    if digest.hexdigest().lower() != expected_sha256.strip().lower():
        raise ValueError("البصمة لا تطابق — الملف تالف أو غير مكتمل")


# ------------------------------------------------- التثبيت

def old_exe_path(target_exe: Path) -> Path:
    """مسار النسخة القديمة المحفوظة للرجوع"""
    target_exe = Path(target_exe)
    return target_exe.with_name(target_exe.stem + ".old" + target_exe.suffix)


def install_update(new_exe: Path, target_exe: Path) -> Path:
    """
    تثبيت الإصدار الجديد مكان الحالي
    Install the new version over the current one

    ويندوز يرفض الكتابة فوق exe شغّال لكنه يسمح بإعادة تسميته، فنعيد تسمية
    الحالي ثم نضع الجديد مكان الاسم الأصلي.

    **عند فشل وضع الجديد يُرجَع الاسم الأصلي فوراً** — وإلا بقي المستخدم
    بلا تطبيق يعمل.

    Returns:
        مسار النسخة القديمة (تبقى للرجوع حتى الإقلاع التالي)

    Raises:
        OSError: فشل الاستبدال (بعد التراجع)
    """
    new_exe, target_exe = Path(new_exe), Path(target_exe)
    old_exe = old_exe_path(target_exe)

    # بقايا من تحديث سابق قد تمنع إعادة التسمية
    if old_exe.exists():
        try:
            os.remove(old_exe)
        except OSError:
            pass

    os.replace(target_exe, old_exe)

    try:
        os.replace(new_exe, target_exe)
    except OSError:
        os.replace(old_exe, target_exe)   # تراجع
        raise

    return old_exe


def cleanup_old_exe(target_exe: Path) -> bool:
    """
    حذف نسخة الإصدار السابق بعد إقلاع الجديد بنجاح
    Remove the previous version after the new one has started

    نجاح الحذف دليلٌ ضمنيّ على أن الإصدار الجديد يعمل. الفشل (ملف مقفول)
    لا يُسقط شيئاً — تُعاد المحاولة في الإقلاع التالي.

    Returns:
        True إن حُذف فعلاً
    """
    old_exe = old_exe_path(Path(target_exe))
    if not old_exe.exists():
        return False

    try:
        os.remove(old_exe)
        return True
    except OSError:
        return False
