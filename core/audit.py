"""
نظام سجل التدقيق
Audit log system for tracking all changes
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Literal
from pathlib import Path
import json

# أنواع العمليات
ActionType = Literal["create", "update", "delete"]
EntityType = Literal[
    "customer", "entry",
    "supplier", "purchase_order", "purchase_item",
    "supplier_payment", "check",
]


@dataclass
class AuditEntry:
    """سجل تدقيق واحد - Single audit log entry"""
    timestamp: str
    action: ActionType
    entity_type: EntityType
    entity_id: str
    old_data: Optional[dict]
    new_data: Optional[dict]
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'AuditEntry':
        """إنشاء من قاموس"""
        return AuditEntry(
            timestamp=data['timestamp'],
            action=data['action'],
            entity_type=data['entity_type'],
            entity_id=data['entity_id'],
            old_data=data.get('old_data'),
            new_data=data.get('new_data')
        )


class AuditManager:
    """
    مدير سجل التدقيق
    Manages audit logging for all entity changes
    """
    
    def __init__(self, data_folder: Path):
        self.data_folder = data_folder
        self.audit_file = data_folder / "audit.jsonl"
        self._cache: List[AuditEntry] = []
        self._loaded = False
    
    def _ensure_loaded(self):
        """تحميل السجلات إذا لم تكن محملة"""
        if not self._loaded:
            self._cache = self._load_all()
            self._loaded = True
    
    def _load_all(self) -> List[AuditEntry]:
        """تحميل جميع سجلات التدقيق"""
        entries = []
        if self.audit_file.exists():
            # utf-8-sig للقراءة فقط — يتحمّل علامة BOM من محرّر خارجي
            with open(self.audit_file, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            entries.append(AuditEntry.from_dict(data))
                        except (json.JSONDecodeError, KeyError):
                            continue
        return entries
    
    def log_action(
        self,
        action: ActionType,
        entity_type: EntityType,
        entity_id: str,
        old_data: Optional[dict] = None,
        new_data: Optional[dict] = None
    ) -> AuditEntry:
        """
        تسجيل عملية في السجل
        Log an action to the audit trail
        """
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_data=old_data,
            new_data=new_data
        )
        
        # إضافة إلى الملف
        with open(self.audit_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')
        
        # تحديث الذاكرة المؤقتة
        if self._loaded:
            self._cache.append(entry)
        
        return entry
    
    def get_history(
        self,
        entity_type: Optional[EntityType] = None,
        entity_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """
        الحصول على سجل التغييرات
        Get change history, optionally filtered
        """
        self._ensure_loaded()
        
        results = self._cache.copy()
        
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        
        if entity_id:
            results = [e for e in results if e.entity_id == entity_id]
        
        # ترتيب من الأحدث إلى الأقدم
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        return results[:limit]
    
    def get_last_action(self) -> Optional[AuditEntry]:
        """الحصول على آخر عملية"""
        self._ensure_loaded()
        if self._cache:
            return max(self._cache, key=lambda x: x.timestamp)
        return None
    
    def can_undo(self) -> bool:
        """التحقق من إمكانية التراجع"""
        last = self.get_last_action()
        return last is not None and last.action in ["create", "update", "delete"]
    
    def get_undo_info(self) -> Optional[dict]:
        """
        الحصول على معلومات التراجع
        Returns info about what would be undone
        """
        last = self.get_last_action()
        if not last:
            return None
        
        action_names = {
            "create": "إنشاء",
            "update": "تعديل",
            "delete": "حذف"
        }
        entity_names = {
            "customer": "عميل",
            "entry": "حركة",
            "supplier": "مورد",
            "purchase_order": "فاتورة شراء",
            "purchase_item": "بند شراء",
            "supplier_payment": "دفعة مورد",
            "check": "شيك",
        }
        
        return {
            "action": last.action,
            "action_name": action_names.get(last.action, last.action),
            "entity_type": last.entity_type,
            "entity_name": entity_names.get(last.entity_type, last.entity_type),
            "entity_id": last.entity_id,
            "old_data": last.old_data,
            "new_data": last.new_data,
            "timestamp": last.timestamp
        }
