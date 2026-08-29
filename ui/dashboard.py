"""
لوحة المعلومات
Dashboard view with charts and statistics
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QPushButton, QComboBox,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from decimal import Decimal
from datetime import datetime, timedelta
import warnings

# إخفاء تحذيرات matplotlib
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from core.storage import StorageManager
from core.analytics import AnalyticsEngine
from core.utils import format_currency


class DashboardView(QWidget):
    """
    لوحة المعلومات مع الرسوم البيانية
    Dashboard view with charts and statistics
    """
    
    back_requested = Signal()
    customer_selected = Signal(str)
    
    def __init__(self, storage: StorageManager, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.analytics = AnalyticsEngine(storage)
        self.setup_ui()
        self.refresh()
    
    def setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # عنوان
        header = QHBoxLayout()
        
        title = QLabel("📊 لوحة المعلومات")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        header.addWidget(title)
        
        header.addStretch()
        
        # اختيار الفترة الزمنية
        self.period_combo = QComboBox()
        self.period_combo.addItem("📅 اليوم", "today")
        self.period_combo.addItem("📆 هذا الشهر", "month")
        self.period_combo.addItem("📊 هذه السنة", "year")
        self.period_combo.addItem("🗓️ الكل", "all")
        self.period_combo.setCurrentIndex(0)  # اليوم هو الافتراضي
        self.period_combo.currentIndexChanged.connect(self.refresh)
        header.addWidget(QLabel("الفترة:"))
        header.addWidget(self.period_combo)
        
        # زر تحديث
        refresh_btn = QPushButton("🔄 تحديث")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        
        # زر رجوع
        back_btn = QPushButton("← رجوع")
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)
        
        layout.addLayout(header)
        
        # منطقة التمرير
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
        # بطاقات الإحصائيات السريعة
        self.stats_layout = QHBoxLayout()
        content_layout.addLayout(self.stats_layout)
        
        # الرسوم البيانية
        charts_layout = QHBoxLayout()
        
        # رسم المبيعات الشهرية
        self.sales_chart = self.create_chart_widget("📈 المبيعات الشهرية")
        charts_layout.addWidget(self.sales_chart)
        
        # رسم المدفوعات الشهرية
        self.payments_chart = self.create_chart_widget("💰 المدفوعات الشهرية")
        charts_layout.addWidget(self.payments_chart)
        
        content_layout.addLayout(charts_layout)
        
        # أعلى العملاء والموردين
        top_lists_layout = QHBoxLayout()
        
        self.top_customers_widget = self.create_top_customers_widget()
        top_lists_layout.addWidget(self.top_customers_widget)
        
        self.top_suppliers_widget = self.create_top_suppliers_widget()
        top_lists_layout.addWidget(self.top_suppliers_widget)
        
        content_layout.addLayout(top_lists_layout)
        
        # تنبيهات (ائتمان وشيكات)
        alerts_layout_main = QHBoxLayout()
        
        self.alerts_widget = self.create_alerts_widget()
        alerts_layout_main.addWidget(self.alerts_widget)
        
        self.check_alerts_widget = self.create_check_alerts_widget()
        alerts_layout_main.addWidget(self.check_alerts_widget)
        
        content_layout.addLayout(alerts_layout_main)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def create_chart_widget(self, title: str) -> QGroupBox:
        """إنشاء ويدجت للرسم البياني"""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        
        # إنشاء figure للرسم
        fig = Figure(figsize=(5, 3), dpi=100)
        fig.patch.set_facecolor('#f8f9fa')
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)
        
        # تخزين المرجع
        group.figure = fig
        group.canvas = canvas
        
        return group
    
    def create_top_customers_widget(self) -> QGroupBox:
        """إنشاء ويدجت أعلى العملاء"""
        group = QGroupBox("🏆 أعلى 5 عملاء برصيد")
        self.top_customers_layout = QVBoxLayout(group)
        return group
    
    def create_top_suppliers_widget(self) -> QGroupBox:
        """إنشاء ويدجت أعلى الموردين"""
        group = QGroupBox("🏭 أعلى 5 موردين نَدين لهم")
        self.top_suppliers_layout = QVBoxLayout(group)
        return group
    
    def create_alerts_widget(self) -> QGroupBox:
        """إنشاء ويدجت التنبيهات"""
        group = QGroupBox("⚠️ تنبيهات حد الائتمان")
        self.alerts_layout = QVBoxLayout(group)
        return group
        
    def create_check_alerts_widget(self) -> QGroupBox:
        """إنشاء ويدجت تنبيهات الشيكات"""
        group = QGroupBox("💳 شيكات قريبة الاستحقاق")
        self.check_alerts_layout = QVBoxLayout(group)
        return group
    
    def create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """إنشاء بطاقة إحصائية"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 10px;
                padding: 15px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 11))
        title_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setFont(QFont("Arial", 16, QFont.Bold))
        value_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(value_label)
        
        return card
    
    def refresh(self):
        """تحديث البيانات والرسوم"""
        period = self.period_combo.currentData()
        
        # تحديث الإحصائيات
        self.update_stats(period)
        
        # تحديث الرسوم البيانية
        self.update_sales_chart(period)
        self.update_payments_chart(period)
        
        # تحديث أعلى العملاء والموردين
        self.update_top_customers()
        self.update_top_suppliers()
        
        # تحديث التنبيهات
        self.update_alerts()
        self.update_check_alerts()
    
    def update_stats(self, period: str):
        """تحديث بطاقات الإحصائيات"""
        # مسح البطاقات القديمة
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # الحصول على الإحصائيات الإجمالية
        stats = self.analytics.get_total_stats()
        
        # تصفية البيانات حسب الفترة إذا لم تكن "الكل"
        if period != "all":
            entries = self.storage.load_entries()
            now = datetime.now()
            
            if period == "today":
                filtered_entries = [e for e in entries if e.datetime.date() == now.date()]
                period_label = "اليوم"
            elif period == "month":
                filtered_entries = [e for e in entries if e.datetime.year == now.year and e.datetime.month == now.month]
                period_label = "هذا الشهر"
            else:  # year
                filtered_entries = [e for e in entries if e.datetime.year == now.year]
                period_label = "هذه السنة"
            
            # حساب الإحصائيات للفترة المحددة
            period_sales = sum(e.amount_decimal for e in filtered_entries if e.type == "purchase")
            period_payments = sum(e.amount_decimal for e in filtered_entries if e.type == "payment")
        else:
            # الحصول على الإحصائيات الشاملة من التحليلات
            dash_summary = self.analytics.get_dashboard_summary()
            
            # بطاقات الإحصائيات (تعديل لعرض معلومات الموردين والشيكات)
            cards = [
                ("👥 أرصدة العملاء (لنا)", format_currency(dash_summary["customer_balance"]), "#10b981"),
                ("🏭 أرصدة الموردين (علينا)", format_currency(dash_summary["supplier_balance"]), "#ef4444"),
                (f"💵 مبيعات {period_label}", format_currency(period_sales), "#3b82f6"),
                (f"🛒 مشتريات (اليوم)", format_currency(dash_summary["today_purchases"]), "#f59e0b"),
                ("⏳ شيكات معلقة", str(dash_summary["checks_pending_count"]), "#6366f1"),
            ]
            
            for title, value, color in cards:
                card = self.create_stat_card(title, value, color)
                self.stats_layout.addWidget(card)
    
    def update_sales_chart(self, period: str):
        """تحديث رسم المبيعات"""
        fig = self.sales_chart.figure
        fig.clear()
        
        ax = fig.add_subplot(111)
        
        entries = self.storage.load_entries()
        sales_entries = [e for e in entries if e.type == "purchase"]
        now = datetime.now()
        
        if period == "today":
            # عرض حسب الساعات لليوم الحالي
            today_sales = [e for e in sales_entries if e.datetime.date() == now.date()]
            hourly_data = {}
            for e in today_sales:
                hour = e.datetime.hour
                hourly_data[hour] = hourly_data.get(hour, Decimal("0")) + e.amount_decimal
            
            hours = list(range(24))
            values = [float(hourly_data.get(h, Decimal("0"))) for h in hours]
            
            ax.bar(hours, values, color='#3b82f6', edgecolor='white')
            ax.set_xlabel('الساعة', fontsize=10)
            ax.set_ylabel('المبيعات (شيكل)', fontsize=10)
            ax.set_title('مبيعات اليوم', fontsize=11)
            
        elif period == "month":
            # عرض حسب الأيام للشهر الحالي
            month_sales = [e for e in sales_entries if e.datetime.year == now.year and e.datetime.month == now.month]
            daily_data = {}
            for e in month_sales:
                day = e.datetime.day
                daily_data[day] = daily_data.get(day, Decimal("0")) + e.amount_decimal
            
            # عدد أيام الشهر
            import calendar
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            days = list(range(1, days_in_month + 1))
            values = [float(daily_data.get(d, Decimal("0"))) for d in days]
            
            ax.bar(days, values, color='#3b82f6', edgecolor='white')
            ax.set_xlabel('اليوم', fontsize=10)
            ax.set_ylabel('المبيعات (شيكل)', fontsize=10)
            ax.set_title('مبيعات هذا الشهر', fontsize=11)
            
        else:  # year or all
            # عرض حسب الأشهر
            if period == "year":
                year_sales = [e for e in sales_entries if e.datetime.year == now.year]
                chart_title = f'مبيعات {now.year}'
            else:
                year_sales = sales_entries
                chart_title = 'إجمالي المبيعات (حسب الأشهر)'
            
            monthly_data = {}
            for e in year_sales:
                month_key = (e.datetime.year, e.datetime.month) if period == "all" else e.datetime.month
                monthly_data[month_key] = monthly_data.get(month_key, Decimal("0")) + e.amount_decimal
            
            if period == "year":
                months = list(range(1, 13))
                values = [float(monthly_data.get(m, Decimal("0"))) for m in months]
                x_labels = [str(m) for m in months]
            else:
                # للكل: عرض آخر 12 شهر
                sorted_months = sorted(monthly_data.keys(), reverse=True)[:12]
                sorted_months.reverse()
                values = [float(monthly_data[m]) for m in sorted_months]
                x_labels = [f"{m[0]}/{m[1]}" for m in sorted_months]
            
            ax.bar(range(len(values)), values, color='#3b82f6', edgecolor='white')
            ax.set_xlabel('الشهر', fontsize=10)
            ax.set_ylabel('المبيعات (شيكل)', fontsize=10)
            ax.set_title(chart_title, fontsize=11)
            if period == "all":
                ax.set_xticks(range(len(x_labels)))
                ax.set_xticklabels(x_labels, rotation=45, fontsize=8)
        
        ax.set_facecolor('#f8f9fa')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fig.tight_layout()
        self.sales_chart.canvas.draw()
    
    def update_payments_chart(self, period: str):
        """تحديث رسم المدفوعات"""
        fig = self.payments_chart.figure
        fig.clear()
        
        ax = fig.add_subplot(111)
        
        entries = self.storage.load_entries()
        payment_entries = [e for e in entries if e.type == "payment"]
        now = datetime.now()
        
        if period == "today":
            # عرض حسب الساعات
            today_payments = [e for e in payment_entries if e.datetime.date() == now.date()]
            hourly_data = {}
            for e in today_payments:
                hour = e.datetime.hour
                hourly_data[hour] = hourly_data.get(hour, Decimal("0")) + e.amount_decimal
            
            hours = list(range(24))
            values = [float(hourly_data.get(h, Decimal("0"))) for h in hours]
            
            ax.bar(hours, values, color='#10b981', edgecolor='white')
            ax.set_xlabel('الساعة', fontsize=10)
            ax.set_ylabel('المدفوعات (شيكل)', fontsize=10)
            ax.set_title('مدفوعات اليوم', fontsize=11)
            
        elif period == "month":
            # عرض حسب الأيام
            month_payments = [e for e in payment_entries if e.datetime.year == now.year and e.datetime.month == now.month]
            daily_data = {}
            for e in month_payments:
                day = e.datetime.day
                daily_data[day] = daily_data.get(day, Decimal("0")) + e.amount_decimal
            
            import calendar
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            days = list(range(1, days_in_month + 1))
            values = [float(daily_data.get(d, Decimal("0"))) for d in days]
            
            ax.bar(days, values, color='#10b981', edgecolor='white')
            ax.set_xlabel('اليوم', fontsize=10)
            ax.set_ylabel('المدفوعات (شيكل)', fontsize=10)
            ax.set_title('مدفوعات هذا الشهر', fontsize=11)
            
        else:  # year or all
            if period == "year":
                year_payments = [e for e in payment_entries if e.datetime.year == now.year]
                chart_title = f'مدفوعات {now.year}'
            else:
                year_payments = payment_entries
                chart_title = 'إجمالي المدفوعات (حسب الأشهر)'
            
            monthly_data = {}
            for e in year_payments:
                month_key = (e.datetime.year, e.datetime.month) if period == "all" else e.datetime.month
                monthly_data[month_key] = monthly_data.get(month_key, Decimal("0")) + e.amount_decimal
            
            if period == "year":
                months = list(range(1, 13))
                values = [float(monthly_data.get(m, Decimal("0"))) for m in months]
                x_labels = [str(m) for m in months]
            else:
                sorted_months = sorted(monthly_data.keys(), reverse=True)[:12]
                sorted_months.reverse()
                values = [float(monthly_data[m]) for m in sorted_months]
                x_labels = [f"{m[0]}/{m[1]}" for m in sorted_months]
            
            ax.bar(range(len(values)), values, color='#10b981', edgecolor='white')
            ax.set_xlabel('الشهر', fontsize=10)
            ax.set_ylabel('المدفوعات (شيكل)', fontsize=10)
            ax.set_title(chart_title, fontsize=11)
            if period == "all":
                ax.set_xticks(range(len(x_labels)))
                ax.set_xticklabels(x_labels, rotation=45, fontsize=8)
        
        ax.set_facecolor('#f8f9fa')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fig.tight_layout()
        self.payments_chart.canvas.draw()
    
    def update_top_customers(self):
        """تحديث قائمة أعلى العملاء"""
        # مسح العناصر القديمة
        while self.top_customers_layout.count():
            item = self.top_customers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        top_customers = self.analytics.get_top_customers_by_balance(5)
        
        if not top_customers:
            label = QLabel("لا توجد بيانات")
            label.setStyleSheet("color: #6b7280; padding: 10px;")
            self.top_customers_layout.addWidget(label)
            return
        
        for i, (customer, balance) in enumerate(top_customers, 1):
            row = QHBoxLayout()
            
            # الترتيب
            rank_label = QLabel(f"#{i}")
            rank_label.setFont(QFont("Arial", 12, QFont.Bold))
            rank_label.setStyleSheet("color: #3b82f6;")
            rank_label.setFixedWidth(30)
            row.addWidget(rank_label)
            
            # اسم العميل
            name_btn = QPushButton(customer.name)
            name_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    text-align: right;
                    color: #1f2937;
                    font-size: 14px;
                }
                QPushButton:hover {
                    color: #3b82f6;
                    text-decoration: underline;
                }
            """)
            name_btn.clicked.connect(lambda checked, cid=customer.id: self.customer_selected.emit(cid))
            row.addWidget(name_btn)
            
            row.addStretch()
            
            # سلوك الدفع
            behavior = self.analytics.analyze_payment_behavior(customer.id)
            behavior_label = QLabel(self.analytics.get_payment_behavior_label(behavior))
            behavior_label.setStyleSheet("padding: 5px;")
            row.addWidget(behavior_label)
            
            # الرصيد
            balance_label = QLabel(format_currency(balance))
            balance_label.setFont(QFont("Arial", 12, QFont.Bold))
            balance_label.setStyleSheet("color: #ef4444;")
            row.addWidget(balance_label)
            
            container = QWidget()
            container.setLayout(row)
            self.top_customers_layout.addWidget(container)
    
    def update_alerts(self):
        """تحديث التنبيهات"""
        # مسح العناصر القديمة
        while self.alerts_layout.count():
            item = self.alerts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        exceeding = self.analytics.get_customers_exceeding_credit_limit()
        
        if not exceeding:
            label = QLabel("✅ جميع العملاء ضمن حد الائتمان")
            label.setStyleSheet("color: #10b981; padding: 10px;")
            self.alerts_layout.addWidget(label)
            return
        
        for customer, balance, limit in exceeding:
            row = QHBoxLayout()
            
            # الأيقونة
            icon = QLabel("⚠️")
            icon.setFixedWidth(25)
            row.addWidget(icon)
            
            # اسم العميل
            name_btn = QPushButton(customer.name)
            name_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    text-align: right;
                    color: #1f2937;
                }
                QPushButton:hover {
                    color: #3b82f6;
                }
            """)
            name_btn.clicked.connect(lambda checked, cid=customer.id: self.customer_selected.emit(cid))
            row.addWidget(name_btn)
            
            row.addStretch()
            
            # الحد
            limit_label = QLabel(f"الحد: {format_currency(limit)}")
            limit_label.setStyleSheet("color: #6b7280;")
            row.addWidget(limit_label)
            
            # الرصيد الحالي
            balance_label = QLabel(f"الرصيد: {format_currency(balance)}")
            balance_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            row.addWidget(balance_label)
            
            # نسبة التجاوز
            excess = balance - limit
            excess_pct = (excess / limit * 100) if limit > 0 else 0
            excess_label = QLabel(f"+{float(excess_pct):.0f}%")
            excess_label.setStyleSheet("""
                background-color: #fee2e2;
                color: #dc2626;
                padding: 3px 8px;
                border-radius: 3px;
            """)
            row.addWidget(excess_label)
            
            container = QWidget()
            container.setLayout(row)
            self.alerts_layout.addWidget(container)
    
    def update_top_suppliers(self):
        """تحديث قائمة أعلى الموردين"""
        while self.top_suppliers_layout.count():
            item = self.top_suppliers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        top_suppliers = self.analytics.get_top_suppliers_by_balance(5)
        
        if not top_suppliers:
            label = QLabel("لا توجد بيانات (لا توجد ذمم موردين)")
            label.setStyleSheet("color: #6b7280; padding: 10px;")
            self.top_suppliers_layout.addWidget(label)
            return
        
        for i, (supplier, balance) in enumerate(top_suppliers, 1):
            row = QHBoxLayout()
            
            rank_label = QLabel(f"#{i}")
            rank_label.setFont(QFont("Arial", 12, QFont.Bold))
            rank_label.setStyleSheet("color: #ef4444;")
            rank_label.setFixedWidth(30)
            row.addWidget(rank_label)
            
            name_btn = QPushButton(supplier.name)
            name_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    text-align: right;
                    color: #1f2937;
                    font-size: 14px;
                }
            """)
            # يمكن ربطه بحساب المورد لاحقاً
            row.addWidget(name_btn)
            
            row.addStretch()
            
            balance_label = QLabel(format_currency(balance))
            balance_label.setFont(QFont("Arial", 12, QFont.Bold))
            balance_label.setStyleSheet("color: #ef4444;")
            row.addWidget(balance_label)
            
            container = QWidget()
            container.setLayout(row)
            self.top_suppliers_layout.addWidget(container)
    
    def update_check_alerts(self):
        """تحديث تنبيهات الشيكات"""
        while self.check_alerts_layout.count():
            item = self.check_alerts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        checks = self.storage.load_checks()
        pending_checks = [c for c in checks if c.status == "pending"]
        
        now = datetime.now()
        week_later = now + timedelta(days=7)
        upcoming_checks = [
            c for c in pending_checks
            if c.due_datetime <= week_later
        ]
        
        if not upcoming_checks:
            label = QLabel("✅ لا يوجد شيكات تستحق هذا الأسبوع")
            label.setStyleSheet("color: #10b981; padding: 10px;")
            self.check_alerts_layout.addWidget(label)
            return
        
        # الترتيب حسب تاريخ الاستحقاق (الأقرب أولاً)
        upcoming_checks.sort(key=lambda c: c.due_datetime)
        
        for check in upcoming_checks[:5]:
            row = QHBoxLayout()
            
            icon = QLabel("💳")
            icon.setFixedWidth(25)
            row.addWidget(icon)
            
            info = f"شيك #{check.check_number} ({check.party_name})"
            info_label = QLabel(info)
            row.addWidget(info_label)
            
            row.addStretch()
            
            days_left = (check.due_datetime - now).days
            if days_left < 0:
                days_text = "استحق منذ أيام"
                color = "#dc2626"  # احمر غامق
            elif days_left == 0:
                days_text = "يستحق اليوم!"
                color = "#dc2626"
            elif days_left == 1:
                days_text = "غداً"
                color = "#ea580c"
            else:
                days_text = f"بعد {days_left} أيام"
                color = "#ea580c"  # برتقالي
                
            days_label = QLabel(days_text)
            days_label.setStyleSheet(f"color: {color};")
            row.addWidget(days_label)
            
            amount_label = QLabel(format_currency(check.amount_decimal))
            amount_label.setFont(QFont("Arial", 11, QFont.Bold))
            amount_label.setStyleSheet(f"color: {color}; margin-right: 10px;")
            row.addWidget(amount_label)
            
            container = QWidget()
            container.setLayout(row)
            self.check_alerts_layout.addWidget(container)
