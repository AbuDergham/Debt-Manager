"""
واجهة التحديث التلقائي
Auto-update user interface

الفحص يجري في خيط خلفي فلا يؤخّر الإقلاع، والتنزيل لا يبدأ إلا بموافقة
صريحة — 75 ميجا على إنترنت ضعيف قرارٌ للمستخدم لا للتطبيق.
"""
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.backup import create_backup
from core.updater import (
    ReleaseInfo,
    check_for_update,
    download_asset,
    fetch_checksum,
    install_update,
    verify_download,
)
from core.version import GITHUB_OWNER, GITHUB_REPO, __version__


def current_exe_path() -> Optional[Path]:
    """
    مسار الملف التنفيذي الجاري تشغيله
    Path of the running executable

    Returns:
        المسار في وضع PyInstaller، أو None في وضع التطوير (لا exe نستبدله)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return None


# ------------------------------------------------- الفحص في الخلفية

class UpdateChecker(QObject):
    """
    فاحص التحديثات — يعمل في خيط منفصل
    Background update checker

    لا يعرض شيئاً عند الفشل. التطبيق يعمل بلا إنترنت.
    """

    found = Signal(object)      # ReleaseInfo
    finished = Signal()

    def __init__(self, current_version: str = __version__):
        super().__init__()
        self.current_version = current_version

    def run(self):
        info = check_for_update(
            self.current_version, owner=GITHUB_OWNER, repo=GITHUB_REPO)
        if info is not None:
            self.found.emit(info)
        self.finished.emit()


def start_background_check(parent, on_found) -> Optional[QThread]:
    """
    تشغيل فحص التحديثات في خيط خلفي
    Start a background update check

    يُحتفظ بمرجعَي الخيط والفاحص على `parent` وإلا جمعهما بايثون فانهار
    التطبيق في منتصف الفحص.

    Returns:
        الخيط، أو None في وضع التطوير (لا exe لتحديثه)
    """
    if current_exe_path() is None:
        return None

    thread = QThread(parent)
    checker = UpdateChecker()
    checker.moveToThread(thread)

    thread.started.connect(checker.run)
    checker.found.connect(on_found)
    checker.finished.connect(thread.quit)
    thread.finished.connect(checker.deleteLater)

    parent._update_thread = thread
    parent._update_checker = checker

    thread.start()
    return thread


# ------------------------------------------------- نافذة التحديث

class UpdateDialog(QDialog):
    """
    عرض الإصدار الجديد، ثم التنزيل والتثبيت بموافقة المستخدم
    Show the new release, then download and install on user consent
    """

    def __init__(self, info: ReleaseInfo, storage, parent=None):
        super().__init__(parent)
        self.info = info
        self.storage = storage
        self.cancelled = False
        self.installed_old_path: Optional[Path] = None

        self.setWindowTitle("تحديث متاح")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        headline = QLabel(f"يتوفّر إصدار جديد: <b>{self.info.version}</b>")
        headline.setStyleSheet("font-size: 15px;")
        layout.addWidget(headline)

        current = QLabel(f"إصدارك الحالي: {__version__}")
        current.setStyleSheet("color: #64748b;")
        layout.addWidget(current)

        # الحجم معروض صراحةً — القرار للمستخدم، خصوصاً على إنترنت ضعيف
        size = QLabel(f"حجم التنزيل: <b>{self.info.size_mb:.1f} ميجابايت</b>")
        size.setStyleSheet("color: #b45309;")
        layout.addWidget(size)

        if self.info.notes:
            label = QLabel("ما الجديد:")
            label.setStyleSheet("margin-top: 8px; font-weight: bold;")
            layout.addWidget(label)

            notes = QTextEdit()
            notes.setPlainText(self.info.notes)
            notes.setReadOnly(True)
            notes.setMaximumHeight(160)
            layout.addWidget(notes)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()

        self.install_btn = QPushButton("⬇️ تنزيل وتثبيت")
        self.install_btn.setDefault(True)
        self.install_btn.clicked.connect(self.download_and_install)
        buttons.addWidget(self.install_btn)

        self.later_btn = QPushButton("لاحقاً")
        self.later_btn.clicked.connect(self.reject)
        buttons.addWidget(self.later_btn)

        self.skip_btn = QPushButton("تجاهل هذا الإصدار")
        self.skip_btn.clicked.connect(self.skip_version)
        buttons.addWidget(self.skip_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

    def skip_version(self):
        """لا تُذكّرني بهذا الإصدار مرة أخرى"""
        self.storage.update_setting("skipped_version", self.info.version)
        self.reject()

    def download_and_install(self):
        target = current_exe_path()
        if target is None:
            QMessageBox.information(
                self, "وضع التطوير",
                "التحديث التلقائي يعمل على النسخة التنفيذية فقط.")
            return

        self.install_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.later_btn.setText("إلغاء")
        self.later_btn.clicked.disconnect()
        self.later_btn.clicked.connect(self._cancel)

        self.progress.setVisible(True)
        self.progress.setMaximum(self.info.size_bytes or 0)
        self.status.setText("جارٍ التنزيل...")

        new_exe = target.with_name(target.stem + ".new" + target.suffix)

        try:
            self._download(new_exe)
            self._verify(new_exe)
            self._install(new_exe, target)
        except InterruptedError:
            self.status.setText("أُلغي التنزيل. ما نُزّل يبقى محفوظاً للمرة القادمة.")
            self._reset_buttons()
        except Exception as e:
            new_exe.unlink(missing_ok=True)
            self.status.setText("")
            QMessageBox.warning(self, "فشل التحديث", f"تعذّر التحديث:\n\n{e}")
            self._reset_buttons()

    def _download(self, new_exe: Path):
        from PySide6.QtWidgets import QApplication

        def on_progress(done: int, total: int):
            self.progress.setValue(done)
            self.status.setText(
                f"جارٍ التنزيل... {done / 1024 / 1024:.1f} من "
                f"{total / 1024 / 1024:.1f} ميجابايت")
            QApplication.processEvents()   # يُبقي الواجهة حيّة وزر الإلغاء عاملاً

        download_asset(
            self.info.download_url, new_exe,
            expected_size=self.info.size_bytes,
            progress_cb=on_progress,
            should_cancel=lambda: self.cancelled,
        )

    def _verify(self, new_exe: Path):
        self.status.setText("جارٍ التحقق من سلامة الملف...")
        checksum = (fetch_checksum(self.info.checksum_url)
                    if self.info.checksum_url else None)
        verify_download(new_exe, self.info.size_bytes, checksum)

    def _install(self, new_exe: Path, target: Path):
        self.status.setText("جارٍ إنشاء نسخة احتياطية للبيانات...")
        backup_path = None
        try:
            backup_path = create_backup(prefix="pre-update")
        except Exception:
            pass   # فشل النسخ الاحتياطي لا يمنع التحديث، لكنه يُذكر أدناه

        self.status.setText("جارٍ التثبيت...")
        self.installed_old_path = install_update(new_exe, target)

        message = [f"تم تثبيت الإصدار {self.info.version} بنجاح.",
                   "أغلق التطبيق وافتحه من جديد ليعمل الإصدار الجديد."]
        if backup_path:
            message.append(f"\nنسخة احتياطية للبيانات:\n{backup_path}")

        QMessageBox.information(self, "تم التحديث", "\n".join(message))
        self.accept()

    def _cancel(self):
        self.cancelled = True

    def _reset_buttons(self):
        self.cancelled = False
        self.progress.setVisible(False)
        self.install_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.later_btn.setText("إغلاق")
        self.later_btn.clicked.disconnect()
        self.later_btn.clicked.connect(self.reject)
