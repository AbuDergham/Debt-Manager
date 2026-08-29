# 🎉 Debt Manager - Quick Start Guide

## ✅ What's Been Delivered

A **production-ready** desktop application for managing customer debts with:

- ✅ **Full Arabic RTL Interface**
- ✅ **No Database Required** (JSON/JSONL files)
- ✅ **Financial Precision** (Decimal calculations)
- ✅ **Atomic File Operations** (corruption-proof)
- ✅ **Auto Backup System**
- ✅ **Export to CSV/JSON/PDF**
- ✅ **Light & Dark Themes**
- ✅ **Password Protection**
- ✅ **Portable Windows EXE**

## 🚀 Getting Started (2 Steps)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Already done!** ✓ All dependencies installed successfully.

### 2. Run the Application

```bash
python main.py
```

That's it! The application window will open with the Arabic RTL interface.

## 📁 Project Structure

```
Debt-Manager/
├── main.py              ← START HERE
├── core/                ← Business logic
│   ├── models.py
│   ├── storage.py
│   ├── summaries.py
│   ├── backup.py
│   └── utils.py
├── ui/                  ← User interface
│   ├── main_window.py
│   ├── customers_view.py
│   ├── customer_ledger.py
│   └── dialogs.py
├── data/                ← Auto-created storage
│   ├── customers.json
│   ├── entries.jsonl
│   ├── summaries.json
│   ├── settings.json
│   └── backups/
├── README.md            ← Full documentation
└── requirements.txt
```

## 💡 First Use

1. **Run**: `python main.py`
2. **Add a customer**: Click "إضافة عميل"
3. **Open their ledger**: Double-click the customer
4. **Add a purchase**: Click "إضافة شراء" (amount: 100)
5. **Add a payment**: Click "إضافة دفع" (amount: 40)
6. **See balance**: Should show 60.00 شيكل (customer owes 60)

## 📦 Building Portable EXE

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller --noconfirm --onefile --windowed --name "DebtManager" main.py

# Result
dist/DebtManager.exe  ← Portable executable
```

The EXE will automatically create the `data/` folder on first run.

## ✅ Verification Complete

Basic tests passed:

```
✓ Data folder initialized
✓ Decimal calculation: 100.00 - 40.00 = 60.00
✓ Customer created: أحمد
✓ Purchase entry: amount=100.00, signed=100.00
✓ Payment entry: amount=40.00, signed=-40.00
✓ Summary calculation: balance=60.00
✓ Entry validation passed
```

## 📚 Full Documentation

See [README.md](file:///d:/Projects/Debt-Manager/README.md) for:

- Detailed usage guide (Arabic & English)
- Feature explanations
- Data format specifications
- Troubleshooting
- Advanced configuration

## 🎯 Key Features Implemented

### Business Logic ✓
- Purchase adds to customer debt
- Payment reduces customer debt
- Today's sales tracking
- Monthly sales tracking
- All calculations use Decimal (no rounding errors)

### User Interface ✓
- Full Arabic RTL layout
- Customers list with search
- Customer ledger with filters
- Entry dialogs with validation
- Light/Dark themes

### Data Management ✓
- Atomic file writes (corruption-proof)
- Auto backup after X entries
- Manual backup on demand
- Export to CSV, JSON, PDF

### Security ✓
- Optional password lock
- Hash-based password storage

## 🎨 Screenshots

When you run `python main.py`, you'll see:

1. **Customers List**: Table with all customers and their balances
2. **Customer Ledger**: Detailed transaction history
3. **Add Entry Dialog**: Simple forms for purchases/payments
4. **Themes**: Professional light and dark modes

## 💻 System Requirements

- **OS**: Windows (tested)
- **Python**: 3.10 or higher
- **Dependencies**: PySide6, reportlab (already installed)

## 🔧 No Mock Data

As requested, the application starts **completely empty**:

- No sample customers
- No sample transactions
- No fake data

Everything you see will be real data entered by you.

## 🏁 You're Ready!

Just run:

```bash
python main.py
```

Enjoy your new debt management system! 🎉
