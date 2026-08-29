"""
نظام النسخ الاحتياطي
Backup system
"""
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional
from .utils import get_data_folder


def create_backup(backup_folder: Optional[Path] = None) -> Path:
    """
    إنشاء نسخة احتياطية من ملفات البيانات
    Create backup of data files
    
    Args:
        backup_folder: مجلد النسخة الاحتياطية (افتراضياً: data/backups/)
    
    Returns:
        مسار ملف ZIP الناتج
    """
    data_folder = get_data_folder()
    
    if backup_folder is None:
        backup_folder = data_folder / "backups"
    
    # التأكد من وجود مجلد النسخ الاحتياطية
    backup_folder = Path(backup_folder)
    backup_folder.mkdir(parents=True, exist_ok=True)
    
    # اسم الملف بالتاريخ والوقت
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.zip"
    backup_path = backup_folder / backup_filename
    
    # الملفات التي سيتم نسخها
    files_to_backup = [
        "customers.json",
        "entries.jsonl",
        "summaries.json",
        "settings.json"
    ]
    
    # إنشاء ملف ZIP
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filename in files_to_backup:
            file_path = data_folder / filename
            if file_path.exists():
                # إضافة الملف إلى ZIP (بدون مسار المجلد)
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
    
    # الحصول على جميع ملفات ZIP وترتيبها حسب التاريخ (الأحدث أولاً)
    backups = sorted(
        backup_folder.glob("backup_*.zip"),
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
        files_to_export = [
            "customers.json",
            "entries.jsonl",
            "summaries.json",
            "settings.json"
        ]
        
        import shutil
        for filename in files_to_export:
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
