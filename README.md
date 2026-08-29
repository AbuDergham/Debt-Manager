# إدارة ديون العملاء - Debt Manager

<div dir="rtl">

نظام إدارة ديون العملاء لمحل الخضار والفواكه. تطبيق سطح مكتب محلي بالكامل مع واجهة عربية كاملة.

</div>

## Features / المميزات

- ✅ Full Arabic RTL interface / واجهة عربية كاملة من اليمين إلى اليسار
- ✅ Right-click context menu / قائمة النقر بالزر الأيمن
- ✅ File-based storage (JSON/JSONL) / تخزين ملفي بدون قاعدة بيانات
- ✅ Atomic file operations / عمليات كتابة ذرية آمنة
- ✅ Decimal-based calculations / حسابات دقيقة باستخدام Decimal
- ✅ Auto backup system / نظام نسخ احتياطي تلقائي
- ✅ Export to CSV, JSON, PDF / تصدير إلى CSV و JSON و PDF
- ✅ Light/Dark theme / وضع فاتح وداكن
- ✅ App lock with password / قفل التطبيق بكلمة مرور
- ✅ Portable Windows EXE / ملف تنفيذي محمول لنظام Windows

## Requirements / المتطلبات

- Python 3.10 or higher
- Windows OS
- PySide6
- reportlab (for PDF export)

## Installation / التثبيت

### 1. Clone or Download the Project

```bash
git clone <repository-url>
cd Debt-Manager
```

### 2. Install Dependencies / تثبيت المكتبات

```bash
pip install -r requirements.txt
```

## Running the Application / تشغيل التطبيق

### Development Mode / وضع التطوير

```bash
python main.py
```

The application will automatically create a `data/` folder with the following structure:

```
data/
├── customers.json        # List of customers
├── entries.jsonl         # Ledger entries (append-only)
├── summaries.json        # Cached summaries
├── settings.json         # Application settings
└── backups/              # Automatic backups
```

## Building Portable EXE / بناء ملف تنفيذي محمول

### Install PyInstaller

```bash
pip install pyinstaller
```

### Build the EXE

```bash
pyinstaller --noconfirm --onefile --windowed --name "DebtManager" --icon=NONE main.py
```

The EXE will be created in the `dist/` folder.

**Important Notes:**
- The EXE is portable and can run on any Windows PC without Python installed
- The `data/` folder will be created automatically next to the EXE on first run
- Keep the EXE and `data/` folder together when moving the application
- All backups are stored in `data/backups/`

## Usage Guide / دليل الاستخدام

### Adding a Customer / إضافة عميل

1. Click "إضافة عميل" (Add Customer) button
2. Enter customer name in Arabic
3. Customer ID will be generated automatically
4. Click "حفظ" (Save)

### Adding a Purchase / إضافة شراء

1. Double-click on a customer to open their ledger
2. Click "إضافة شراء" (Add Purchase)
3. Enter amount and description
4. Choose payment method (cash/transfer)
5. Click "حفظ" (Save)

The customer's balance will increase (they owe you money).

### Adding a Payment / إضافة دفع

1. Open customer ledger
2. Click "إضافة دفع" (Add Payment)
3. Enter payment amount
4. Choose payment method
5. Click "حفظ" (Save)

The customer's balance will decrease (they paid you).

### Right-Click Context Menu / قائمة النقر بالزر الأيمن

Right-click on any customer in the customers list to access quick actions:

1. **📖 Open Ledger** - Opens the customer's detailed transaction history
2. **🛒 Add Purchase** - Quickly add a purchase without opening the ledger
3. **💰 Add Payment** - Quickly add a payment without opening the ledger
4. **✏️ Edit Name** - Change the customer's name
5. **🗑️ Delete Customer** - Remove the customer (with confirmation)

This makes it much faster to manage customers and transactions!

### Exporting Data / تصدير البيانات

#### Export Customer Ledger
1. Open customer ledger
2. Click "تصدير" (Export)
3. Choose format (CSV, JSON, or PDF)
4. Select save location

#### Export All Data
1. Go to menu: ملف → تصدير جميع البيانات (File → Export All Data)
2. Choose save location
3. All data will be exported as a ZIP file

### Backup / النسخ الاحتياطي

#### Automatic Backup
- The application automatically prompts for backup after every X entries (default: 200)
- You can configure this in: الإعدادات → إعدادات النسخ الاحتياطي (Settings → Backup Settings)

#### Manual Backup
1. Go to menu: ملف → إنشاء نسخة احتياطية (File → Create Backup)
2. Backup ZIP will be saved in `data/backups/`

### App Lock / قفل التطبيق

#### Enable App Lock
1. Go to: الإعدادات → تفعيل قفل التطبيق (Settings → Enable App Lock)
2. Enter password twice
3. Next time you open the app, you'll need to enter the password

#### Disable App Lock
1. Go to: الإعدادات → إلغاء قفل التطبيق (Settings → Disable App Lock)
2. Enter current password
3. App lock will be removed

### Theme / المظهر

Toggle between light and dark mode:
- الإعدادات → تبديل الوضع (فاتح/داكن)
- Settings → Toggle Theme (Light/Dark)

## File Structure / هيكل المشروع

```
Debt-Manager/
├── main.py                   # Entry point
├── core/
│   ├── __init__.py
│   ├── models.py            # Data models
│   ├── storage.py           # Storage layer with atomic writes
│   ├── summaries.py         # Calculations engine
│   ├── backup.py            # Backup system
│   └── utils.py             # Utility functions
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # Main window
│   ├── customers_view.py    # Customers list
│   ├── customer_ledger.py   # Customer ledger
│   └── dialogs.py           # Dialog windows
├── data/                    # Auto-created on first run
│   ├── customers.json
│   ├── entries.jsonl
│   ├── summaries.json
│   ├── settings.json
│   └── backups/
├── requirements.txt
└── README.md
```

## Data Format / صيغة البيانات

### customers.json

```json
[
  {
    "id": "ahmad_1234",
    "name": "أحمد"
  }
]
```

### entries.jsonl

Each line is a separate JSON record:

```json
{"customer_id": "ahmad_1234", "type": "purchase", "amount": "100.00", "date": "2025-12-11T10:30:00", "desc": "أغراض", "pay_method": "cash"}
{"customer_id": "ahmad_1234", "type": "payment", "amount": "40.00", "date": "2025-12-11T11:00:00", "desc": "دفعة", "pay_method": "cash"}
```

### summaries.json

```json
{
  "ahmad_1234": {
    "balance": "60.00",
    "today_sales": "100.00",
    "month_sales": "100.00",
    "last_update": "2025-12-11T11:00:00"
  }
}
```

## Business Logic / المنطق التجاري

### Balance Calculation

```
For each entry:
  - If type = "purchase": signed_amount = +amount (customer owes you)
  - If type = "payment":  signed_amount = -amount (customer paid you)

Customer balance = Sum of all signed_amounts
```

### Sales Calculation

```
Today sales  = Sum of purchase amounts for today
Month sales  = Sum of purchase amounts for current month
```

### Example Scenario

```
1. Add customer: "Ahmad"
2. Add purchase: 100.00
3. Add payment:  40.00

Result: Balance = 60.00 (Ahmad owes you 60)
```

## Troubleshooting / حل المشاكل

### Application doesn't start

1. Make sure Python 3.10+ is installed
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python main.py`

### Data corruption

1. Check `data/backups/` for recent backups
2. Restore from backup (extract ZIP to `data/` folder)

### PyInstaller build issues

```bash
# Clean previous builds
rmdir /s /q build dist

# Rebuild
pyinstaller --noconfirm --onefile --windowed --name "DebtManager" main.py
```

### PDF export not working

PDF export requires `reportlab`. If not installed:

```bash
pip install reportlab
```

For PyInstaller builds, reportlab should be included automatically.

## Technical Details / التفاصيل التقنية

### Atomic File Writing

All writes use atomic operations to prevent data corruption:

```python
1. Write to temporary file
2. Atomic rename (os.replace) to overwrite original
```

This ensures data integrity even during power failure.

### Decimal Precision

All financial calculations use Python's `Decimal` type to avoid floating-point errors:

```python
from decimal import Decimal

amount = Decimal("100.00")  # Exact representation
result = amount * Decimal("1.5")  # No rounding errors
```

### JSONL Format

Entries are stored in JSONL (JSON Lines) format:
- Each line is a complete JSON object
- Append-only for performance
- Easy to parse and backup

## License / الترخيص

This is a custom application for a fruits & vegetables store. Free to use and modify.

## Support / الدعم

<div dir="rtl">

للدعم والمساعدة، يرجى الرجوع إلى هذا الملف أو التواصل مع المطور.

</div>

---

**Version:** 2.0.0  
**Last Updated:** 2025-12-11
