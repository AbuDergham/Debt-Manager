"""
نافذة استعادة نسخة احتياطية
Restore-from-backup dialog

البرنامج ينشئ نسخة احتياطية تلقائياً قبل كل حذف عميل وقبل كل ترحيل
لصيغة البيانات — لكن لم تكن هناك أي طريقة لاستعادتها من داخل البرنامج.
فلمّا تلف ملف في المحل، لم يكن أمام صاحبه زر يضغطه.
"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.backup import create_backup, get_backup_info, list_backups, restore_backup
from core.utils import format_datetime_arabic

# وصف عربي لبادئات أسماء النسخ، ليعرف المستخدم سببها
_PREFIX_LABELS = {
    "pre-delete": "قبل حذف عميل أو مورد",
    "pre-migration-v2": "قبل تحديث صيغة البيانات",
    "pre-update": "قبل تحديث البرنامج",
    "pre-restore": "قبل استعادة سابقة",
    "backup": "نسخة يدوية أو دورية",
}


def describe_prefix(filename: str) -> str:
    """سبب إنشاء النسخة، مستخرجاً من اسم الملف"""
    for prefix, label in _PREFIX_LABELS.items():
        if filename.startswith(prefix + "_"):
            return label
    return "نسخة احتياطية"


class RestoreBackupDialog(QDialog):
    """
    اختيار نسخة احتياطية واستعادتها
    Pick a backup and restore it
    """

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.backups = list_backups(backup_folder=storage.data_folder / "backups")

        self.setWindowTitle("استعادة نسخة احتياطية")
        self.setModal(True)
        self.setMinimumSize(760, 460)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("اختر النسخة التي تريد الرجوع إليها")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        warning = QLabel(
            "⚠️ الاستعادة تكتب فوق البيانات الحالية. سيحفظ البرنامج نسخة من "
            "وضعك الحالي قبل أن يفعل ذلك، فيمكنك التراجع."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #b45309; padding: 6px 0;")
        layout.addWidget(warning)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["التاريخ والوقت", "السبب", "الحجم", "الملفات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self._fill_table()

        buttons = QHBoxLayout()

        self.restore_btn = QPushButton("♻️ استعادة النسخة المختارة")
        self.restore_btn.clicked.connect(self.restore_selected)
        self.restore_btn.setEnabled(bool(self.backups))
        buttons.addWidget(self.restore_btn)

        buttons.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        layout.addLayout(buttons)

    def _fill_table(self):
        if not self.backups:
            self.table.setRowCount(1)
            self.table.setSpan(0, 0, 1, 4)
            empty = QTableWidgetItem("لا توجد نسخ احتياطية في مجلد data/backups")
            empty.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 0, empty)
            return

        self.table.setRowCount(len(self.backups))
        for row, path in enumerate(self.backups):
            try:
                info = get_backup_info(path)
                when = format_datetime_arabic(info["created"])
                size = f"{info['size'] / 1024:,.0f} كيلوبايت"
                files = str(len(info["files"]))
            except Exception:
                when, size, files = "—", "—", "—"

            item = QTableWidgetItem(when)
            item.setData(Qt.UserRole, str(path))
            self.table.setItem(row, 0, item)
            self.table.setItem(row, 1, QTableWidgetItem(describe_prefix(path.name)))
            self.table.setItem(row, 2, QTableWidgetItem(size))
            self.table.setItem(row, 3, QTableWidgetItem(files))

        self.table.selectRow(0)

    def selected_backup(self):
        """مسار النسخة المختارة، أو None"""
        row = self.table.currentRow()
        if row < 0 or not self.backups:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return Path(data) if data else None

    def restore_selected(self):
        path = self.selected_backup()
        if path is None:
            QMessageBox.warning(self, "لم تختر شيئاً", "اختر نسخة من القائمة أولاً.")
            return

        row = self.table.currentRow()
        when = self.table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "تأكيد الاستعادة",
            f"ستُستعاد بيانات {when}.\n\n"
            "كل ما أُدخل بعد ذلك التاريخ سيختفي.\n"
            "سيحفظ البرنامج نسخة من وضعك الحالي أولاً.\n\n"
            "هل تريد المتابعة؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            safety = create_backup(data_folder=self.storage.data_folder,
                                   prefix="pre-restore")
            restored = restore_backup(path, data_folder=self.storage.data_folder)
        except Exception as e:
            QMessageBox.warning(self, "فشلت الاستعادة",
                                f"تعذّرت الاستعادة:\n\n{e}")
            return

        QMessageBox.information(
            self, "تمت الاستعادة",
            f"استُعيد {len(restored)} ملف.\n\n"
            f"نسخة وضعك السابق محفوظة في:\n{safety.name}\n\n"
            "أغلق البرنامج وافتحه من جديد."
        )
        self.accept()
