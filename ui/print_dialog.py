"""
نافذة خيارات الطباعة
Print options dialog

تكشف نوع ورق الطابعة تلقائياً، وتسمح بتجاوزه يدوياً إن كذب المُعرِّف.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.reports import PAPER_A4, PAPER_THERMAL_58, PAPER_THERMAL_80
from .printing import (
    PAPER_LABELS,
    available_printers,
    export_pdf,
    show_print_preview,
)

AUTO = "auto"


class PrintOptionsDialog(QDialog):
    """
    خيارات الطباعة: نوع الورق ثم معاينة أو حفظ PDF

    Args:
        build_html: دالة تأخذ نوع الورق وترجع HTML التقرير
        storage: مدير التخزين (لحفظ آخر مجلد تصدير)
        title: عنوان النافذة
        default_filename: اسم الملف المقترح عند حفظ PDF
    """

    def __init__(self, build_html, storage, title="طباعة",
                 default_filename="تقرير", parent=None):
        super().__init__(parent)
        self.build_html = build_html
        self.storage = storage
        self.default_filename = default_filename

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # نوع الورق — تلقائي افتراضاً
        self.paper_combo = QComboBox()
        self.paper_combo.addItem("🔎 تلقائي (حسب الطابعة المختارة)", AUTO)
        self.paper_combo.addItem(f"📄 {PAPER_LABELS[PAPER_A4]}", PAPER_A4)
        self.paper_combo.addItem(f"🧾 {PAPER_LABELS[PAPER_THERMAL_80]}",
                                 PAPER_THERMAL_80)
        self.paper_combo.addItem(f"🧾 {PAPER_LABELS[PAPER_THERMAL_58]}",
                                 PAPER_THERMAL_58)
        form.addRow("نوع الورق:", self.paper_combo)

        layout.addLayout(form)

        # ما الذي اكتُشف على هذا الجهاز
        detected = QLabel(self._detection_summary())
        detected.setWordWrap(True)
        detected.setStyleSheet("color: #64748b; font-size: 11px; padding: 6px 0;")
        layout.addWidget(detected)

        hint = QLabel(
            "النظام يتعرّف على نوع الطابعة لوحده، ويتحوّل التقرير بين جدول A4 "
            "وقصاصة إيصال عند تبديل الطابعة داخل نافذة المعاينة. "
            "غيّر «نوع الورق» يدوياً فقط إن أخطأ التعرّف."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(hint)

        buttons = QHBoxLayout()

        preview_btn = QPushButton("🖨️ معاينة وطباعة")
        preview_btn.setDefault(True)
        preview_btn.clicked.connect(self.preview_and_print)
        buttons.addWidget(preview_btn)

        pdf_btn = QPushButton("💾 حفظ PDF")
        pdf_btn.clicked.connect(self.save_pdf)
        buttons.addWidget(pdf_btn)

        buttons.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        layout.addLayout(buttons)

    def _detection_summary(self) -> str:
        """سطر يلخّص ما اكتُشف من الطابعات المتاحة"""
        printers = available_printers()
        if not printers:
            return "⚠️ لا توجد طابعات مركّبة على هذا الجهاز — يمكنك حفظ PDF."

        lines = []
        for name, paper, reason, is_default in printers:
            mark = " ★" if is_default else ""
            lines.append(f"• {name}{mark} → {PAPER_LABELS[paper]}")
        return "الطابعات المتاحة:\n" + "\n".join(lines)

    def selected_paper(self):
        """نوع الورق المختار، أو None للكشف التلقائي"""
        value = self.paper_combo.currentData()
        return None if value == AUTO else value

    def preview_and_print(self):
        """معاينة ثم طباعة — يعاد بناء التقرير مع كل تبديل طابعة"""
        try:
            show_print_preview(
                self.build_html,
                parent=self,
                title=self.windowTitle(),
                forced_paper=self.selected_paper(),
            )
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "خطأ في الطباعة",
                                f"تعذّرت الطباعة:\n\n{e}")

    def save_pdf(self):
        """حفظ التقرير ملفَّ PDF"""
        last_dir = self.storage.get_setting("last_export_dir", "")
        suggested = f"{last_dir}/{self.default_filename}.pdf" if last_dir \
            else f"{self.default_filename}.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ التقرير PDF", suggested, "PDF Files (*.pdf)")

        if not path:
            return

        paper = self.selected_paper() or PAPER_A4

        try:
            export_pdf(self.build_html(paper), path, paper=paper)
        except Exception as e:
            QMessageBox.warning(self, "خطأ في الحفظ",
                                f"تعذّر حفظ الملف:\n\n{e}")
            return

        from pathlib import Path
        self.storage.update_setting("last_export_dir", str(Path(path).parent))

        QMessageBox.information(self, "نجح", f"تم حفظ التقرير:\n{path}")
        self.accept()
