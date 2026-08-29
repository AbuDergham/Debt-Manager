    
    def show_entry_context_menu(self, position):
        """
        عرض قائمة السياق للإدخال
        Show context menu for entry
        """
        # الحصول على الصف المحدد
        row = self.table.rowAt(position.y())
        if row < 0:
            return
        
        # الحصول على الإدخال من القائمة المصفاة
        now = datetime.now()
        if self.current_filter == "today":
            filtered_entries = [e for e in self.entries if e.datetime.date() == now.date()]
        elif self.current_filter == "month":
            filtered_entries = [e for e in self.entries if e.datetime.year == now.year and e.datetime.month == now.month]
        else:
            filtered_entries = self.entries
        
        if row >= len(filtered_entries):
            return
        
        entry = filtered_entries[row]
        
        # إنشاء القائمة
        menu = QMenu(self)
        
        # تعديل الإدخال
        edit_action = QAction("✏️ تعديل", self)
        edit_action.triggered.connect(lambda: self.edit_entry(entry, row))
        menu.addAction(edit_action)
        
        # عرض القائمة
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def edit_entry(self, entry: Entry, row: int):
        """
        تعديل إدخال موجود
        Edit existing entry
        """
        from .dialogs import EditEntryDialog
        
        dialog = EditEntryDialog(entry, self.customer.name, self)
        
        if dialog.exec():
            try:
                # نحتاج لإعادة كتابة ملف entries.jsonl بالكامل
                # لأن JSONL هو append-only format
                
                # تحميل جميع الإدخالات
                all_entries = self.storage.load_entries()
                
                # البحث عن الإدخال القديم وتحديثه
                found = False
                for i, e in enumerate(all_entries):
                    if (e.customer_id == entry.customer_id and
                        e.date == entry.date and
                        e.amount == entry.amount and
                        e.desc == entry.desc):
                        all_entries[i] = dialog.updated_entry
                        found = True
                        break
                
                if not found:
                    QMessageBox.warning(self, "خطأ", "لم يتم العثور على الإدخال")
                    return
                
                # إعادة كتابة ملف entries.jsonl
                import tempfile
                entries_file = self.storage.data_folder / "entries.jsonl"
                
                # كتابة إلى ملف مؤقت
                fd, temp_path = tempfile.mkstemp(
                    dir=entries_file.parent,
                    suffix='.tmp',
                    text=True
                )
                
                try:
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        for e in all_entries:
                            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + '\n')
                    
                    # نقل الملف المؤقت ليحل محل الأصلي
                    import os
                    os.replace(temp_path, entries_file)
                except Exception as e:
                    # حذف الملف المؤقت في حالة حدوث خطأ
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    raise e
                
                # إعادة تحميل البيانات
                self.load_data()
                
                QMessageBox.information(
                    self, "نجح",
                    "تم تعديل الإدخال بنجاح"
                )
            except Exception as e:
                QMessageBox.warning(self, "خطأ", f"فشل في تعديل الإدخال: {str(e)}")
