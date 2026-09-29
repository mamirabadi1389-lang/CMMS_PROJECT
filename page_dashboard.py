"""
CMMS Dashboard Page - Fixed
"""
import tkinter as tk
from datetime import date, timedelta
import threading

import database as db
from styles import COLORS, FONTS, OPERATOR_COLORS
from widgets import KPICard, SectionTitle, StyledTreeview, GaugeMeter


class DashboardPage(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = tk.Frame(self, bg=COLORS["bg_header"])
        header.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(header, text="داشبورد مدیریت نگهداری و تعمیرات",
                 font=FONTS["title"], bg=COLORS["bg_header"],
                 fg=COLORS["text_primary"]).pack(side="right", pady=12)
        self.date_lbl = tk.Label(header, text="", font=FONTS["body"],
                                 bg=COLORS["bg_header"], fg=COLORS["text_secondary"])
        self.date_lbl.pack(side="left", padx=10)

        canvas = tk.Canvas(self, bg=COLORS["bg_dark"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                                 bg=COLORS["bg_dark"], troughcolor=COLORS["bg_card"])
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        self.content = tk.Frame(canvas, bg=COLORS["bg_dark"])
        self._cwin = canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self._cwin, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # KPI row
        kpi_row = tk.Frame(self.content, bg=COLORS["bg_dark"])
        kpi_row.pack(fill="x", padx=20, pady=(16, 8))
        self.kpi_em   = KPICard(kpi_row, "توقفات اضطراری", "–", "۹۰ روز اخیر", COLORS["red"],    "🚨")
        self.kpi_pm   = KPICard(kpi_row, "دستورات PM",     "–", "۹۰ روز اخیر", COLORS["blue"],   "🔧")
        self.kpi_mttr = KPICard(kpi_row, "MTTR میانگین",   "–", "ساعت",    COLORS["yellow"], "⏱️")
        self.kpi_mtbf = KPICard(kpi_row, "MTBF میانگین",   "–", "ساعت",    COLORS["green"],  "📈")
        for kpi in [self.kpi_em, self.kpi_pm, self.kpi_mttr, self.kpi_mtbf]:
            kpi.pack(side="left", fill="x", expand=True, padx=4)

        # Middle row
        mid = tk.Frame(self.content, bg=COLORS["bg_dark"])
        mid.pack(fill="both", expand=True, padx=20, pady=8)
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=2)
        mid.rowconfigure(0, weight=1)

        gauge_card = tk.Frame(mid, bg=COLORS["bg_card"],
                              highlightbackground=COLORS["border"], highlightthickness=1)
        gauge_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        SectionTitle(gauge_card, "وضعیت اپراتورها", "👷").pack(fill="x", padx=16, pady=(12,0))
        self.gauge_frame = tk.Frame(gauge_card, bg=COLORS["bg_card"])
        self.gauge_frame.pack(fill="both", expand=True, padx=8, pady=8)

        wo_card = tk.Frame(mid, bg=COLORS["bg_card"],
                           highlightbackground=COLORS["border"], highlightthickness=1)
        wo_card.grid(row=0, column=1, sticky="nsew")
        hdr2 = tk.Frame(wo_card, bg=COLORS["bg_card"])
        hdr2.pack(fill="x", padx=16, pady=(12,0))
        SectionTitle(hdr2, "آخرین دستور کارها", "📋").pack(side="right")
        tk.Button(hdr2, text="مشاهده همه ›", font=FONTS["small"],
                  bg=COLORS["bg_card"], fg=COLORS["accent"], bd=0, cursor="hand2",
                  command=lambda: self.app.show_page("لیست دستور کارها")).pack(side="left")
        cols = ("شماره", "نوع", "تجهیز", "اپراتور", "تاریخ", "وضعیت")
        self.recent_tree = StyledTreeview(wo_card, columns=cols, row_height=30)
        self.recent_tree.pack(fill="both", expand=True, padx=8, pady=8)
        for col, w in zip(cols, [110, 60, 160, 80, 90, 90]):
            self.recent_tree.tree.column(col, width=w, minwidth=w)

        # Bottom row
        bot = tk.Frame(self.content, bg=COLORS["bg_dark"])
        bot.pack(fill="x", padx=20, pady=(0, 20))
        bot.columnconfigure(0, weight=1)
        bot.columnconfigure(1, weight=1)

        pm_card = tk.Frame(bot, bg=COLORS["bg_card"],
                           highlightbackground=COLORS["border"], highlightthickness=1)
        pm_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        SectionTitle(pm_card, "PM های سررسید شده", "📅").pack(fill="x", padx=16, pady=(12,0))
        self.pm_list = tk.Frame(pm_card, bg=COLORS["bg_card"])
        self.pm_list.pack(fill="x", padx=12, pady=8)

        stock_card = tk.Frame(bot, bg=COLORS["bg_card"],
                              highlightbackground=COLORS["border"], highlightthickness=1)
        stock_card.grid(row=0, column=1, sticky="nsew")
        SectionTitle(stock_card, "قطعات کم‌موجودی", "⚠️").pack(fill="x", padx=16, pady=(12,0))
        self.stock_list = tk.Frame(stock_card, bg=COLORS["bg_card"])
        self.stock_list.pack(fill="x", padx=12, pady=8)

    def refresh(self):
        today = date.today()
        self.date_lbl.configure(text="📅"+today.strftime("%Y-%m-%d"))
        # بازه‌ی غلتان ۹۰ روز اخیر (تقریباً یک فصل) - به‌جای «ماه تقویمی جاری».
        # ۳۰ روز برای خیلی از کارخونه‌ها که فاصله‌ی رخدادها بیشتره خیلی
        # تنگه و دستورکارهای واقعی رو هم گم می‌کنه؛ ۹۰ روز تصویر واقعی‌تری
        # از وضعیت اخیر میده و همچنان معنادار می‌مونه (نه کل تاریخچه).
        since = (today - timedelta(days=90)).isoformat()

        def load():
            summary   = db.get_dashboard_summary(days=90)
            recent    = db.fetch_all("""
                SELECT wo.order_number, wo.order_type, e.name as eq_name,
                       wo.operator, wo.work_date, wo.status
                FROM work_orders wo LEFT JOIN equipment e ON wo.equipment_id=e.id
                ORDER BY wo.id DESC LIMIT 10""")
            pm_due    = db.fetch_all("""
                SELECT ps.task_name, e.name as eq_name, ps.next_due, ps.operator
                FROM pm_schedules ps JOIN equipment e ON ps.equipment_id=e.id
                WHERE ps.next_due <= date('now','+7 days') AND ps.active=1
                ORDER BY ps.next_due LIMIT 5""")
            low_stock = db.fetch_all("""
                SELECT name, quantity, min_stock, unit FROM spare_parts
                WHERE quantity <= min_stock ORDER BY (quantity-min_stock) LIMIT 5""")
            op_stats  = db.fetch_all("""
                SELECT operator, COUNT(*) as total,
                       SUM(CASE WHEN order_type='EM' THEN 1 ELSE 0 END) as em,
                       SUM(downtime_minutes) as down
                FROM work_orders WHERE work_date >= ?
                GROUP BY operator""", (since,))
            self.after(0, lambda: self._update_ui(summary, recent, pm_due, low_stock, op_stats))

        threading.Thread(target=load, daemon=True).start()

    def _update_ui(self, summary, recent, pm_due, low_stock, op_stats):
        self.kpi_em.update_value(summary["em_count"])
        self.kpi_pm.update_value(summary["pm_count"])
        self.kpi_mttr.update_value(f"{summary['mttr']:.1f}")
        self.kpi_mtbf.update_value(f"{summary['mtbf']:.1f}")

        self.recent_tree.clear()
        for r in recent:
            tags = [f"op_{r['operator']}"] if r["operator"] in OPERATOR_COLORS else []
            self.recent_tree.insert(
                (r["order_number"],
                 "🔴 EM" if r["order_type"]=="EM" else "🔵 PM",
                 r["eq_name"] or "-", r["operator"],
                 r["work_date"], r["status"]),
                tags=tuple(tags))

        # Operator gauges - rebuild
        for w in self.gauge_frame.winfo_children():
            w.destroy()
        for op in ["مکانیک", "برق", "تاسیسات"]:
            stat  = next((s for s in op_stats if s["operator"]==op), None)
            total = stat["total"] if stat else 0
            em_c  = stat["em"]    if stat else 0
            down  = (stat["down"] or 0)//60 if stat else 0
            color = OPERATOR_COLORS.get(op, COLORS["accent"])

            col_fr = tk.Frame(self.gauge_frame, bg=COLORS["bg_card"])
            col_fr.pack(side="left", fill="x", expand=True, padx=6, pady=8)
            tk.Label(col_fr, text=op, font=FONTS["subhead"],
                     bg=COLORS["bg_card"], fg=color).pack()
            # KEY FIX: size=130, value and max passed explicitly
            GaugeMeter(col_fr, value=total, max_val=max(total+3, 15),
                       label=f"{down}h توقف", color=color, size=130).pack(pady=4)
            tk.Label(col_fr, text=f"EM: {em_c}  |  PM: {total-em_c}",
                     font=FONTS["small"], bg=COLORS["bg_card"],
                     fg=COLORS["text_muted"]).pack()

        # PM due
        for w in self.pm_list.winfo_children():
            w.destroy()
        if not pm_due:
            tk.Label(self.pm_list, text="✓  همه PM ها به روز هستند",
                     font=FONTS["body"], bg=COLORS["bg_card"],
                     fg=COLORS["green"]).pack(anchor="center", pady=8)
        for pm in pm_due:
            row = tk.Frame(self.pm_list, bg=COLORS["bg_card"])
            row.pack(fill="x", pady=3)
            overdue = pm["next_due"] < date.today().isoformat()
            tk.Label(row, text="🔴" if overdue else "🟡",
                     bg=COLORS["bg_card"]).pack(side="right")
            tk.Label(row, text=pm["task_name"], font=FONTS["body_bold"],
                     bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(side="right", padx=(0,6))
            tk.Label(row, text=f"{pm['eq_name']}  •  {pm['next_due']}",
                     font=FONTS["small"], bg=COLORS["bg_card"],
                     fg=COLORS["text_muted"]).pack(side="left")

        # Low stock
        for w in self.stock_list.winfo_children():
            w.destroy()
        if not low_stock:
            tk.Label(self.stock_list, text="✓  موجودی قطعات کافی است",
                     font=FONTS["body"], bg=COLORS["bg_card"],
                     fg=COLORS["green"]).pack(anchor="center", pady=8)
        for part in low_stock:
            row = tk.Frame(self.stock_list, bg=COLORS["bg_card"])
            row.pack(fill="x", pady=3)
            ratio = part["quantity"] / max(part["min_stock"], 1)
            clr = COLORS["red"] if ratio < 0.5 else COLORS["yellow"]
            tk.Label(row, text="⚠️", bg=COLORS["bg_card"]).pack(side="right")
            tk.Label(row, text=part["name"], font=FONTS["body_bold"],
                     bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(side="right", padx=(0,6))
            tk.Label(row, text=f"{part['quantity']} {part['unit']}  (حداقل: {part['min_stock']})",
                     font=FONTS["small"], bg=COLORS["bg_card"], fg=clr).pack(side="left")
