"""
نظام النسخ الاحتياطي
Backup system
"""
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional
from .utils import get_data_folder, DATA_FILES


def create_backup(
    backup_folder: Optional[Path] = None,
    data_folder: Optional[Path] = None,
    prefix: str = "backup",
) -> Path:
    """
    إنشاء نسخة احتياطية من ملفات البيانات
    Create backup of data files

    Args:
        backup_folder: مجلد النسخة الاحتياطية (افتراضياً: <data>/backups/)
        data_folder: مجلد البيانات المصدر (للاختبارات)
        prefix: بادئة اسم الملف (مثلاً "pre-migration-v2")

    Returns:
        مسار ملف ZIP الناتج
    """
    source_folder = Path(data_folder) if data_folder is not None else get_data_folder()

    if backup_folder is None:
        backup_folder = source_folder / "backups"

    backup_folder = Path(backup_folder)
    backup_folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_folder / f"{prefix}_{timestamp}.zip"

    # قائمة الملفات من DATA_FILES — مصدر واحد للحقيقة، فلا تُنسى
    # ملفات جديدة عند إضافتها
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filename, _ in DATA_FILES.values():
            file_path = source_folder / filename
            if file_path.exists():
                zipf.write(file_path, arcname=filename)

    return backup_path


def restore_backup(backup_path: Path) -> None:
    """
    استعادة نسخة احتياطية
    Restore from backup
    
    Args:
        backup_path: مسار ملف ZIP الاحتياطي
    """
    data_folder = get_data_folder()
    backup_path = Path(backup_path)
    
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")
    
    # استخراج الملفات
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        zipf.extractall(data_folder)


def list_backups(backup_folder: Optional[Path] = None) -> list[Path]:
    """
    الحصول على قائمة بجميع النسخ الاحتياطية
    Get list of all backup files
    
    Args:
        backup_folder: مجلد النسخ الاحتياطية (افتراضياً: data/backups/)
    
    Returns:
        قائمة بمسارات ملفات ZIP
    """
    data_folder = get_data_folder()
    
    if backup_folder is None:
        backup_folder = data_folder / "backups"
    
    backup_folder = Path(backup_folder)
    
    if not backup_folder.exists():
        return []
    
    # كل ملفات ZIP، لا "backup_*" فقط — النسخ التلقائية تأخذ بادئات أخرى
    # مثل "pre-migration-v2_" و "pre-delete_"
    backups = sorted(
        backup_folder.glob("*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    return backups


def get_backup_info(backup_path: Path) -> dict:
    """
    الحصول على معلومات عن نسخة احتياطية
    Get information about a backup
    
    Args:
        backup_path: مسار ملف ZIP الاحتياطي
    
    Returns:
        قاموس بمعلومات النسخة الاحتياطية
    """
    backup_path = Path(backup_path)
    
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")
    
    stat = backup_path.stat()
    
    # الحصول على محتويات ZIP
    with zipfile.ZipFile(backup_path, 'r') as zipf:
        files = zipf.namelist()
        total_size = sum(info.file_size for info in zipf.infolist())
    
    return {
        'name': backup_path.name,
        'path': str(backup_path),
        'size': stat.st_size,
        'uncompressed_size': total_size,
        'created': datetime.fromtimestamp(stat.st_mtime),
        'files': files
    }


def export_all_data(export_path: Path) -> Path:
    """
    تصدير جميع البيانات إلى مجلد أو ملف ZIP
    Export all data to a folder or ZIP file
    
    Args:
        export_path: مسار التصدير (مجلد أو ملف .zip)
    
    Returns:
        مسار التصدير الفعلي
    """
    export_path = Path(export_path)
    
    # إذا كان المسار ينتهي بـ .zip، إنشاء نسخة احتياطية
    if export_path.suffix.lower() == '.zip':
        # إنشاء النسخة الاحتياطية في موقع مخصص
        parent_folder = export_path.parent
        parent_folder.mkdir(parents=True, exist_ok=True)
        
        # إنشاء النسخة الاحتياطية مؤقتاً ثم نقلها
        temp_backup = create_backup()
        
        # نقل الملف إلى الموقع المطلوب
        import shutil
        shutil.move(str(temp_backup), str(export_path))
        
        return export_path
    else:
        # إنشاء مجلد ونسخ الملفات
        export_path.mkdir(parents=True, exist_ok=True)
        
        data_folder = get_data_folder()

        import shutil
        for filename, _ in DATA_FILES.values():
            src = data_folder / filename
            if src.exists():
                dst = export_path / filename
                shutil.copy2(src, dst)
        
        return export_path


class AutoBackupManager:
    """
    مدير النسخ الاحتياطي التلقائي
    Automatic backup manager
    """
    
    def __init__(self, interval: int = 200):
        """
        تهيئة مدير النسخ الاحتياطي التلقائي
        Initialize auto backup manager
        
        Args:
            interval: عدد الإدخالات بين كل نسخة احتياطية
        """
        self.interval = interval
        self.last_backup_count = 0
    
    def should_backup(self, current_count: int) -> bool:
        """
        التحقق من ضرورة إنشاء نسخة احتياطية
        Check if backup should be created
        
        Args:
            current_count: العدد الحالي للإدخالات
        
        Returns:
            True إذا كان يجب إنشاء نسخة احتياطية
        """
        entries_since_last = current_count - self.last_backup_count
        return entries_since_last >= self.interval
    
    def perform_backup(self) -> Optional[Path]:
        """
        تنفيذ النسخة الاحتياطية
        Perform backup
        
        Returns:
            مسار ملف النسخة الاحتياطية أو None إذا فشل
        """
        try:
            backup_path = create_backup()
            return backup_path
        except Exception as e:
            print(f"Backup failed: {e}")
            return None
    
    def update_last_backup_count(self, count: int) -> None:
        """
        تحديث عداد آخر نسخة احتياطية
        Update last backup count
        """
        self.last_backup_count = count
