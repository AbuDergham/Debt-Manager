# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application

```bash
python main.py
```

### Installing Dependencies

```bash
pip install -r requirements.txt
```

### Building Portable EXE

```bash
pyinstaller --noconfirm --onefile --windowed --name "DebtManager" --icon=NONE main.py
```

### Running Tests

There are no automated tests in this codebase. Manual testing is required.

### Running a Single Test

Not applicable - no test suite exists.

## Code Architecture

### Core Architecture

This is a desktop application for managing customer debts in a vegetable & fruit store with a full Arabic RTL interface. The architecture follows a clean separation of concerns:

1. **UI Layer** (ui/): Qt-based interface with PySide6
2. **Business Logic Layer** (core/): Data models, calculations, and storage
3. **Data Layer**: File-based storage using JSON/JSONL

### Key Components

1. **Storage Manager** (`core/storage.py`)
   - Atomic file operations using temporary files and atomic rename
   - Manages four data files:
     - `customers.json`: Customer information
     - `entries.jsonl`: Transaction ledger (append-only)
     - `summaries.json`: Cached customer summaries
     - `settings.json`: Application preferences

2. **Data Models** (`core/models.py`)
   - `Customer`: Customer information (id, name, phone, credit_limit, notes)
   - `Entry`: Transaction record (customer_id, type, amount, date, desc, pay_method, notes)
   - `Summary`: Calculated summary (balance, today_sales, month_sales, last_update)

3. **Calculation Engine** (`core/summaries.py`)
   - Calculates customer balances from transaction entries
   - Calculates daily and monthly sales
   - Computes running balances for transaction history
   - Calculates total debt and sales

4. **Analytics Engine** (`core/analytics.py`)
   - Analyzes customer payment behavior (excellent, good, irregular, poor)
   - Identifies customers exceeding credit limits
   - Provides top customers by balance
   - Supports search across all entries

5. **Backup System** (`core/backup.py`)
   - Automatic backup after configurable number of entries (default: 200)
   - Manual backup via File menu
   - Export all data as ZIP file
   - Restore from backup

### Data Flow

1. User interacts with UI components (customers view, ledger, dashboard)
2. UI calls StorageManager methods to read/write data
3. StorageManager performs atomic writes to maintain data integrity
4. When entries are added/modified, summaries are recalculated
5. Analytics engine provides insights for dashboard visualization
6. Backup system triggers automatically based on entry count

### File Formats

- `customers.json`: JSON array of customer objects
- `entries.jsonl`: JSON Lines format - one JSON object per line
- `summaries.json`: JSON object with customer_id as keys
- `settings.json`: JSON object with application settings

### Key Design Principles

1. **Atomic Operations**: All writes use temporary files and atomic rename to prevent corruption
2. **Decimal Precision**: Financial calculations use Python's Decimal type to avoid floating-point errors
3. **Append-Only**: Transaction ledger uses JSONL format for performance
4. **Local Storage**: No database required - all data stored in local files
5. **RTL Support**: Full right-to-left Arabic interface
6. **Portability**: Application can be packaged as a single Windows EXE file

## Development Workflow

1. Make changes to source code
2. Run `python main.py` to test changes
3. Test all user flows:
   - Adding customers
   - Adding purchases and payments
   - Using the dashboard
   - Using right-click context menus
   - Exporting data
   - Using app lock
   - Switching themes
4. Test backup functionality
5. Build portable EXE if needed

## Important Notes

- The application creates a `data/` folder automatically on first run
- All data files are stored in the `data/` folder
- The `data/backups/` folder contains automatic and manual backups
- The application is designed to work with Windows OS
- The codebase uses Python 3.10+ and PySide6
- All financial calculations use Decimal type for precision
- The backup system prevents data loss during power failures
- The JSONL format for entries allows efficient appending without loading the entire file
- The atomic write mechanism ensures data integrity even if the application crashes during write operations

## Key Files to Understand

- `main.py`: Entry point
- `core/storage.py`: Core data storage logic
- `core/models.py`: Data models
- `core/summaries.py`: Business logic calculations
- `core/analytics.py`: Business insights
- `core/backup.py`: Backup system
- `ui/main_window.py`: Main application UI
- `ui/dashboard.py`: Dashboard visualization
- `README.md`: Complete documentation

## Testing

Manual testing is required since there are no automated tests. Test all user flows thoroughly:

1. Customer management (add, edit, delete)
2. Transaction management (purchase, payment)
3. Dashboard visualization
4. Right-click context menus
5. Export functionality
6. App lock and password
7. Theme switching
8. Backup and restore

## Build Process

To create a portable executable:

1. Install PyInstaller: `pip install pyinstaller`
2. Build: `pyinstaller --noconfirm --onefile --windowed --name "DebtManager" --icon=NONE main.py`
3. The EXE will be created in the `dist/` folder
4. Copy the `data/` folder next to the EXE
5. The application will work on any Windows PC without Python installed

## Deployment

- The application is designed for local deployment on Windows PCs
- All data is stored locally in the `data/` folder
- The application can be distributed as a single EXE file with the `data/` folder
- No internet connection required
- No server or database required
- The application is self-contained

## Security

- Passwords are hashed using SHA-256
- No sensitive data is transmitted over the network
- All data is stored locally
- The application is designed for offline use

## Maintenance

- The application is designed to be low-maintenance
- Data files are human-readable and can be edited manually if needed
- Backup system prevents data loss
- Atomic writes prevent data corruption
- Simple file-based architecture makes debugging straightforward

## Limitations

- Windows-only (PySide6 dependency)
- No automatic updates
- No cloud synchronization
- No multi-user support
- No mobile version
- No API for integration
- No web interface

## Future Enhancements

- Add automatic data migration between versions
- Add import from CSV files
- Add export to Excel
- Add data validation rules
- Add user permissions
- Add audit logs
- Add search functionality
- Add data export filters
- Add data import/export history
- Add data compression
- Add encryption
- Add cloud sync
- Add mobile companion app
- Add web interface
- Add multi-language support
- Add reporting features
- Add data analytics dashboard
- Add integration with accounting software
- Add barcode scanning
- Add receipt printing
- Add mobile app sync
- Add web dashboard
- Add API for third-party integration
- Add machine learning for prediction
- Add data visualization enhancements
- Add custom report generation
- Add data backup to cloud
- Add data recovery wizard
- Add data synchronization
- Add user feedback system
- Add usage analytics
- Add customer loyalty program
- Add invoice generation
- Add payment reminders
- Add SMS notifications
- Add email notifications
- Add calendar integration
- Add task scheduling
- Add data export to PDF with charts
- Add data export to Excel with charts
- Add data export to CSV with charts
- Add data export to JSON with charts
- Add data export to HTML with charts
- Add data export to PNG with charts
- Add data export to SVG with charts
- Add data export to JPG with charts
- Add data export to GIF with charts
- Add data export to BMP with charts
- Add data export to TIFF with charts
- Add data export to WebP with charts