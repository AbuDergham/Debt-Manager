"""
بناء ونشر إصدار جديد على GitHub
Build and publish a new release to GitHub

الاستعمال:
    .venv/Scripts/python.exe tools/release.py            # بناء ونشر
    .venv/Scripts/python.exe tools/release.py --dry-run  # بناء بلا نشر

الخطوات:
  1. التحقق من نظافة شجرة git
  2. تشغيل كل الاختبارات — يتوقّف عند أي فشل
  3. بناء الملف التنفيذي
  4. حساب SHA-256 وكتابة SHA256SUMS.txt
  5. النشر عبر gh release create

رقم الإصدار يُقرأ من core/version.py — مصدر واحد للحقيقة.
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.version import CHECKSUM_ASSET, EXE_NAME, __version__  # noqa: E402

PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
DIST = ROOT / "dist"


def run(command, **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in command)}")
    return subprocess.run(command, cwd=ROOT, **kwargs)


def fail(message: str):
    print(f"\n✗ {message}")
    sys.exit(1)


def check_clean_tree():
    print("\n[1/5] التحقق من شجرة git")
    result = run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout)
        fail("الشجرة غير نظيفة. التزم تغييراتك أولاً — الإصدار يجب أن يطابق"
             " ما في المستودع بالضبط.")
    print("  ✓ نظيفة")


def check_tag_is_free(tag: str):
    result = run(["git", "tag", "-l", tag], capture_output=True, text=True)
    if result.stdout.strip():
        fail(f"الوسم {tag} موجود مسبقاً. ارفع رقم الإصدار في core/version.py.")


def run_tests():
    print("\n[2/5] تشغيل الاختبارات")
    if run([PYTHON, "-m", "pytest", "-q"]).returncode != 0:
        fail("الاختبارات فشلت. لا يُنشر إصدار على اختبارات فاشلة.")
    print("  ✓ كلها تمر")


def build_exe() -> Path:
    print("\n[3/5] بناء الملف التنفيذي")
    if run([PYTHON, "-m", "PyInstaller", "--clean", "--noconfirm",
            "Debt-Manager.spec"]).returncode != 0:
        fail("فشل البناء.")

    exe = DIST / EXE_NAME
    if not exe.exists():
        fail(f"لم يُنتج {exe}")

    print(f"  ✓ {exe.name} — {exe.stat().st_size / 1024 / 1024:.1f} ميجابايت")
    return exe


def write_checksums(exe: Path) -> Path:
    print("\n[4/5] حساب البصمة")
    digest = hashlib.sha256()
    with open(exe, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    checksum_file = DIST / CHECKSUM_ASSET
    checksum_file.write_text(f"{digest.hexdigest()}  {exe.name}\n", encoding="utf-8")

    print(f"  ✓ {digest.hexdigest()}")
    return checksum_file


def publish(tag: str, exe: Path, checksums: Path, notes: str):
    print(f"\n[5/5] نشر {tag}")
    result = run(["gh", "release", "create", tag, str(exe), str(checksums),
                  "--title", f"الإصدار {__version__}", "--notes", notes])
    if result.returncode != 0:
        fail("فشل النشر. تحقّق من `gh auth status` ومن وجود المستودع البعيد.")
    print(f"  ✓ نُشر {tag}")


def main():
    parser = argparse.ArgumentParser(description="بناء ونشر إصدار")
    parser.add_argument("--dry-run", action="store_true",
                        help="بناء وحساب البصمة بلا نشر")
    parser.add_argument("--notes", default="",
                        help="ملاحظات الإصدار (تظهر للمستخدم في نافذة التحديث)")
    parser.add_argument("--skip-tests", action="store_true",
                        help="تخطّي الاختبارات (للتجريب فقط)")
    args = parser.parse_args()

    tag = f"v{__version__}"
    print(f"=== إصدار {__version__} ===")

    if not args.dry_run:
        check_clean_tree()
        check_tag_is_free(tag)

    if not args.skip_tests:
        run_tests()

    exe = build_exe()
    checksums = write_checksums(exe)

    if args.dry_run:
        print(f"\n✓ تجربة جافة — لم يُنشر شيء.\n  {exe}\n  {checksums}")
        return

    notes = args.notes or f"الإصدار {__version__}"
    publish(tag, exe, checksums, notes)

    print(f"\n✓ تم. المستخدمون على إصدارات أقدم سيرون التحديث عند فتح التطبيق.")


if __name__ == "__main__":
    main()
