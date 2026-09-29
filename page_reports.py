"""
CMMS Reports & Analytics Page — Fixed Charts
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
import threading
import os
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.patches as mpatches
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

import database as db
from styles import COLORS, FONTS, OPERATOR_COLORS
from widgets import KPICard, SectionTitle, IconButton, StyledTreeview


class ReportsPage(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self._charts = []          # keep figure references
        self._chart_widgets = []   # keep tk widget references for safe cleanup
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=COLORS["bg_header"])
        hdr.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(hdr, text="گزارشات و آمار", font=FONTS["title"],
                 bg=COLORS["bg_header"], fg=COLORS["text_primary"]).pack(side="right", pady=12)

        # Month selector
        ctrl = tk.Frame(hdr, bg=COLORS["bg_header"])
        ctrl.pack(side="left", pady=12)
        tk.Label(ctrl, text="ماه:", font=FONTS["body"],
                 bg=COLORS["bg_header"], fg=COLORS["text_secondary"]).pack(side="right", padx=4)
        self.month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        months = []
        d = date.today()
        for _ in range(12):
            months.append(d.strftime("%Y-%m"))
            d = (d.replace(day=1) - timedelta(days=1))
        self.month_cb = ttk.Combobox(ctrl, textvariable=self.month_var,
                                     values=months, width=10, state="readonly",
                                     font=FONTS["body"])
        self.month_cb.pack(side="right", padx=4)
        self.month_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        IconButton(ctrl, "بروزرسانی", "🔄", self.refresh,
                   color=COLORS["accent"]).pack(side="left", padx=8)
        IconButton(ctrl, "خروجی اکسل", "📥", self._export_report,
                   color=COLORS["bg_card"]).pack(side="left", padx=4)

        # ── Tab bar ────────────────────────────────────────────────────────
        self.tab_var = tk.StringVar(value="کلی")
        tab_fr = tk.Frame(self, bg=COLORS["bg_dark"])
        tab_fr.pack(fill="x", padx=20, pady=4)
        self._tab_btns = {}
        for tab in ["کلی", "توقفات (EM)", "نگهداری (PM)", "اپراتورها", "تجهیزات"]:
            btn = tk.Label(tab_fr, text=tab, font=FONTS["body_bold"],
                           padx=16, pady=8, cursor="hand2")
            btn.pack(side="right", padx=2)
            self._tab_btns[tab] = btn
            btn.bind("<Button-1>", lambda e, t=tab: self._switch_tab(t))
        self._switch_tab("کلی")

        # ── Content area ───────────────────────────────────────────────────
        self.content_area = tk.Frame(self, bg=COLORS["bg_dark"])
        self.content_area.pack(fill="both", expand=True, padx=20, pady=8)

    def _switch_tab(self, tab):
        self.tab_var.set(tab)
        for t, btn in self._tab_btns.items():
            if t == tab:
                btn.configure(bg=COLORS["accent"], fg=COLORS["bg_dark"])
            else:
                btn.configure(bg=COLORS["bg_card"], fg=COLORS["text_secondary"])
        self.refresh()

    def refresh(self):
        month = self.month_var.get()
        tab = self.tab_var.get()

        def load():
            summary = db.get_monthly_summary(month)
            rows_em = db.fetch_all("""
                SELECT wo.order_number, e.name as eq_name, wo.operator,
                       wo.work_date, wo.downtime_minutes, wo.status, wo.priority,
                       wo.root_cause, wo.action_taken
                FROM work_orders wo LEFT JOIN equipment e ON wo.equipment_id=e.id
                WHERE wo.order_type='EM' AND strftime('%Y-%m', wo.work_date)=?
                ORDER BY wo.downtime_minutes DESC
            """, (month,))
            rows_pm = db.fetch_all("""
                SELECT wo.order_number, e.name as eq_name, wo.operator,
                       wo.work_date, wo.status, wo.technician_name
                FROM work_orders wo LEFT JOIN equipment e ON wo.equipment_id=e.id
                WHERE wo.order_type='PM' AND strftime('%Y-%m', wo.work_date)=?
                ORDER BY wo.work_date
            """, (month,))
            eq_stats = db.fetch_all("""
                SELECT e.name, COUNT(*) as total,
                       SUM(wo.downtime_minutes) as down,
                       SUM(CASE WHEN wo.order_type='EM' THEN 1 ELSE 0 END) as em
                FROM work_orders wo JOIN equipment e ON wo.equipment_id=e.id
                WHERE strftime('%Y-%m', wo.work_date)=?
                GROUP BY e.id ORDER BY down DESC LIMIT 10
            """, (month,))
            self.after(0, lambda: self._render(tab, summary, rows_em, rows_pm, eq_stats))

        threading.Thread(target=load, daemon=True).start()

    def _render(self, tab, summary, rows_em, rows_pm, eq_stats):
        # ── FIX #1: close matplotlib figures BEFORE destroying Tk widgets ──
        for c in self._charts:
            try:
                plt.close(c)
            except Exception:
                pass
        self._charts.clear()
        self._chart_widgets.clear()

        for w in self.content_area.winfo_children():
            w.destroy()

        if tab == "کلی":
            self._render_overview(summary)
        elif tab == "توقفات (EM)":
            self._render_em(rows_em, summary)
        elif tab == "نگهداری (PM)":
            self._render_pm(rows_pm)
        elif tab == "اپراتورها":
            self._render_operators(summary)
        elif tab == "تجهیزات":
            self._render_equipment(eq_stats)

    # ─────────────────────────────────────────────────────────────────────
    def _render_overview(self, summary):
        # KPI row
        kpi_row = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        kpi_row.pack(fill="x", pady=(0, 12))

        KPICard(kpi_row, "EM این ماه", summary["em_count"], "",
                COLORS["red"], "🚨").pack(side="left", fill="x", expand=True, padx=(0, 6))
        KPICard(kpi_row, "PM این ماه", summary["pm_count"], "",
                COLORS["blue"], "🔧").pack(side="left", fill="x", expand=True, padx=6)
        total_down_h = summary["total_downtime_min"] // 60
        total_down_m = summary["total_downtime_min"] % 60
        KPICard(kpi_row, "مجموع توقف",
                f"{total_down_h}:{total_down_m:02d}", "ساعت",
                COLORS["yellow"], "⏰").pack(side="left", fill="x", expand=True, padx=6)
        KPICard(kpi_row, "MTTR", f"{summary['mttr']:.1f}", "ساعت",
                COLORS["purple"], "⏱️").pack(side="left", fill="x", expand=True, padx=6)
        KPICard(kpi_row, "MTBF", f"{summary['mtbf']:.1f}", "ساعت",
                COLORS["cyan"], "📈").pack(side="left", fill="x", expand=True, padx=(6, 0))

        if not MATPLOTLIB_OK:
            tk.Label(self.content_area, text="نمودارها نیاز به matplotlib دارند",
                     font=FONTS["body"], bg=COLORS["bg_dark"],
                     fg=COLORS["text_muted"]).pack(pady=20)
            return

        # Charts row — 3 equal columns
        chart_row = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        chart_row.pack(fill="both", expand=True)
        chart_row.columnconfigure(0, weight=1)
        chart_row.columnconfigure(1, weight=1)
        chart_row.columnconfigure(2, weight=1)
        chart_row.rowconfigure(0, weight=1)

        # Pie: EM vs PM
        pie_card = tk.Frame(chart_row, bg=COLORS["bg_card"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
        pie_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        SectionTitle(pie_card, "نسبت EM / PM", "📊").pack(fill="x", padx=12, pady=(8, 0))
        pie_container = tk.Frame(pie_card, bg=COLORS["bg_card"])
        pie_container.pack(fill="both", expand=True, padx=8, pady=8)
        self._pie_chart(pie_container, summary["em_count"], summary["pm_count"])

        # Bar: downtime per operator
        bar_card = tk.Frame(chart_row, bg=COLORS["bg_card"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
        bar_card.grid(row=0, column=1, sticky="nsew", padx=6)
        SectionTitle(bar_card, "توقف به تفکیک اپراتور", "👷").pack(fill="x", padx=12, pady=(8, 0))
        bar_container = tk.Frame(bar_card, bg=COLORS["bg_card"])
        bar_container.pack(fill="both", expand=True, padx=8, pady=8)
        ops_data = summary["per_operator"]
        self._bar_chart_operators(bar_container, ops_data)

        # Operator table
        tbl_card = tk.Frame(chart_row, bg=COLORS["bg_card"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
        tbl_card.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        SectionTitle(tbl_card, "جدول اپراتورها", "📋").pack(fill="x", padx=12, pady=(8, 0))
        cols = ("اپراتور", "کل", "EM", "توقف (دق)")
        tree = StyledTreeview(tbl_card, cols)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for op in ops_data:
            tree.insert((op["operator"], op["cnt"],
                         op["cnt"] - (op["down"] or 0) // 60,
                         op["down"] or 0))

    # ─────────────────────────────────────────────────────────────────────
    def _render_em(self, rows, summary):
        info_row = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        info_row.pack(fill="x", pady=(0, 8))

        total_down = sum(r["downtime_minutes"] or 0 for r in rows)
        for val, lbl, color in [
            (len(rows), "تعداد EM", COLORS["red"]),
            (f"{total_down // 60}:{total_down % 60:02d}", "مجموع توقف (h:m)", COLORS["yellow"]),
            (f"{summary['mttr']:.2f}", "MTTR (ساعت)", COLORS["purple"]),
            (f"{summary['mtbf']:.2f}", "MTBF (ساعت)", COLORS["cyan"]),
        ]:
            kf = KPICard(info_row, lbl, val, "", color, "")
            kf.pack(side="left", fill="x", expand=True, padx=4)

        SectionTitle(self.content_area, "جزئیات توقفات اضطراری", "🚨").pack(fill="x", pady=4)
        cols = ("شماره", "تجهیز", "اپراتور", "تاریخ", "توقف(دق)", "اولویت", "وضعیت")
        tree = StyledTreeview(self.content_area, cols)
        tree.pack(fill="both", expand=True)
        widths = [120, 180, 80, 90, 80, 70, 80]
        for col, w in zip(cols, widths):
            tree.tree.column(col, width=w)
        for r in rows:
            tree.insert((r["order_number"], r["eq_name"] or "-",
                         r["operator"], r["work_date"],
                         r["downtime_minutes"], r["priority"], r["status"]))

    # ─────────────────────────────────────────────────────────────────────
    def _render_pm(self, rows):
        info_row = tk.Frame(self.content_area, bg=COLORS["bg_dark"])
        info_row.pack(fill="x", pady=(0, 8))
        closed = sum(1 for r in rows if r["status"] == "بسته")
        KPICard(info_row, "کل PM", len(rows), "", COLORS["blue"], "🔧").pack(
            side="left", fill="x", expand=True, padx=4)
        KPICard(info_row, "انجام شده", closed, "", COLORS["green"], "✅").pack(
            side="left", fill="x", expand=True, padx=4)
        pct = int(closed / len(rows) * 100) if rows else 0
        KPICard(info_row, "درصد تکمیل", f"{pct}%", "", COLORS["cyan"], "📈").pack(
            side="left", fill="x", expand=True, padx=4)

        SectionTitle(self.content_area, "جزئیات PM ها", "🔧").pack(fill="x", pady=4)
        cols = ("شماره", "تجهیز", "اپراتور", "تکنسین", "تاریخ", "وضعیت")
        tree = StyledTreeview(self.content_area, cols)
        tree.pack(fill="both", expand=True)
        for r in rows:
            tree.insert((r["order_number"], r["eq_name"] or "-",
                         r["operator"], r["technician_name"] or "-",
                         r["work_date"], r["status"]))

    # ─────────────────────────────────────────────────────────────────────
    def _render_operators(self, summary):
        ops = summary["per_operator"]
        if not ops:
            tk.Label(self.content_area, text="داده‌ای برای این ماه ثبت نشده است",
                     font=FONTS["body"], bg=COLORS["bg_dark"],
                     fg=COLORS["text_muted"]).pack(pady=40)
            return

        for op_data in ops:
            op = op_data["operator"]
            color = OPERATOR_COLORS.get(op, COLORS["accent"])
            card = tk.Frame(self.content_area, bg=COLORS["bg_card"],
                            highlightbackground=color, highlightthickness=1)
            card.pack(fill="x", pady=6)
            inner = tk.Frame(card, bg=COLORS["bg_card"])
            inner.pack(fill="x", padx=16, pady=12)

            tk.Label(inner, text=op, font=FONTS["heading"],
                     bg=COLORS["bg_card"], fg=color).pack(side="right")
            stats = tk.Frame(inner, bg=COLORS["bg_card"])
            stats.pack(side="left")
            down = op_data["down"] or 0
            for val, lbl in [
                (op_data["cnt"], "کل دستور کار"),
                (f"{down // 60}h {down % 60}m", "مجموع توقف"),
                (db.calc_mttr(operator=op), "MTTR (ساعت)"),
            ]:
                sf = tk.Frame(stats, bg=COLORS["bg_card"])
                sf.pack(side="left", padx=20)
                tk.Label(sf, text=str(val), font=FONTS["heading"],
                         bg=COLORS["bg_card"], fg=color).pack()
                tk.Label(sf, text=lbl, font=FONTS["small"],
                         bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack()

    # ─────────────────────────────────────────────────────────────────────
    def _render_equipment(self, eq_stats):
        if not eq_stats:
            tk.Label(self.content_area, text="داده‌ای برای این ماه ثبت نشده است",
                     font=FONTS["body"], bg=COLORS["bg_dark"],
                     fg=COLORS["text_muted"]).pack(pady=40)
            return

        SectionTitle(self.content_area, "تجهیزات با بیشترین توقف", "⚠️").pack(fill="x", pady=4)

        for i, eq in enumerate(eq_stats):
            card = tk.Frame(self.content_area, bg=COLORS["bg_card"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(fill="x", pady=3)
            inner = tk.Frame(card, bg=COLORS["bg_card"])
            inner.pack(fill="x", padx=12, pady=8)

            rank_color = [COLORS["red"], COLORS["yellow"], COLORS["blue"]]
            rc = rank_color[i] if i < 3 else COLORS["text_muted"]
            tk.Label(inner, text=f"#{i+1}", font=FONTS["subhead"],
                     bg=COLORS["bg_card"], fg=rc, width=3).pack(side="right")
            tk.Label(inner, text=eq["name"], font=FONTS["body_bold"],
                     bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(side="right", padx=8)

            down = eq["down"] or 0
            tk.Label(inner, text=f"توقف: {down // 60}h {down % 60}m",
                     font=FONTS["small"], bg=COLORS["bg_card"],
                     fg=COLORS["yellow"]).pack(side="left", padx=8)
            tk.Label(inner, text=f"EM: {eq['em']}",
                     font=FONTS["small"], bg=COLORS["bg_card"],
                     fg=COLORS["red"]).pack(side="left", padx=8)
            tk.Label(inner, text=f"کل: {eq['total']}",
                     font=FONTS["small"], bg=COLORS["bg_card"],
                     fg=COLORS["text_muted"]).pack(side="left", padx=8)

            # Progress bar
            max_down = eq_stats[0]["down"] or 1
            pct = (down / max_down) if max_down else 0
            bar_bg = tk.Frame(inner, bg=COLORS["border"], height=6, width=200)
            bar_bg.pack(side="left", padx=8)
            bar_fg = tk.Frame(bar_bg, bg=rc, height=6, width=int(200 * pct))
            bar_fg.place(x=0, y=0)

    # ─────────────────────────────────────────────────────────────────────
    #  CHART HELPERS  (Fixed sizing + safe cleanup)
    # ─────────────────────────────────────────────────────────────────────
    def _pie_chart(self, parent, em, pm):
        if not MATPLOTLIB_OK:
            return
        total = em + pm
        if total == 0:
            tk.Label(parent, text="داده‌ای موجود نیست", font=FONTS["small"],
                     bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=20)
            return

        # FIX #2: smaller figsize + lower DPI so it fits inside the card
        fig, ax = plt.subplots(figsize=(2.6, 1.8), dpi=80)
        fig.patch.set_facecolor(COLORS["bg_card"])
        ax.set_facecolor(COLORS["bg_card"])
        colors_pie = [COLORS["red"], COLORS["blue"]]
        wedges, texts, autotexts = ax.pie(
            [em, pm], labels=["EM", "PM"], autopct="%1.0f%%",
            colors=colors_pie, startangle=90,
            textprops={"color": COLORS["text_primary"], "fontsize": 9},
            wedgeprops={"edgecolor": COLORS["bg_card"], "linewidth": 2}
        )
        for at in autotexts:
            at.set_color(COLORS["bg_dark"])
            at.set_fontweight("bold")

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(fill="both", expand=True)
        self._charts.append(fig)
        self._chart_widgets.append(widget)

    def _bar_chart_operators(self, parent, ops_data):
        if not MATPLOTLIB_OK or not ops_data:
            return
        # FIX #2: smaller figsize + lower DPI
        fig, ax = plt.subplots(figsize=(2.6, 1.8), dpi=80)
        fig.patch.set_facecolor(COLORS["bg_card"])
        ax.set_facecolor(COLORS["bg_card"])

        names = [o["operator"] for o in ops_data]
        downs = [(o["down"] or 0) // 60 for o in ops_data]
        bar_colors = [OPERATOR_COLORS.get(n, COLORS["accent"]) for n in names]

        bars = ax.bar(names, downs, color=bar_colors, edgecolor=COLORS["bg_card"], linewidth=1.5)
        for bar, val in zip(bars, downs):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.1,
                        f"{val}h", ha="center", va="bottom",
                        color=COLORS["text_primary"], fontsize=8)

        ax.tick_params(colors=COLORS["text_secondary"], labelsize=8)
        ax.spines["bottom"].set_color(COLORS["border"])
        ax.spines["left"].set_color(COLORS["border"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_ylabel("ساعت توقف", color=COLORS["text_secondary"], fontsize=8)
        ax.yaxis.label.set_color(COLORS["text_secondary"])
        for label in ax.get_xticklabels():
            label.set_color(COLORS["text_primary"])
            label.set_fontfamily("Tahoma")

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(fill="both", expand=True)
        self._charts.append(fig)
        self._chart_widgets.append(widget)

    # ─────────────────────────────────────────────────────────────────────
    
    def _export_report(self):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from tkinter import filedialog

            month = self.month_var.get()
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile=f"cmms_report_{month}.xlsx"
            )
            if not path:
                return

            wb = openpyxl.Workbook()
            summary = db.get_monthly_summary(month)

            # Summary sheet
            ws = wb.active
            ws.title = "خلاصه ماهانه"
            orange_fill = PatternFill("solid", fgColor="F97316")
            title_font = Font(bold=True, size=14)
            ws["A1"] = f"گزارش نگهداری و تعمیرات — {month}"
            ws["A1"].font = title_font
            ws.merge_cells("A1:D1")

            headers = ["شاخص", "مقدار", "واحد", "توضیح"]
            ws.append(headers)
            for cell in ws[2]:
                cell.fill = orange_fill
                cell.font = Font(bold=True, color="000000")

            data = [
                ["تعداد توقف اضطراری (EM)", summary["em_count"], "عدد", ""],
                ["تعداد دستور کار PM", summary["pm_count"], "عدد", ""],
                ["مجموع زمان توقف", summary["total_downtime_min"], "دقیقه", ""],
                ["MTTR", summary["mttr"], "ساعت", "میانگین زمان تعمیر"],
                ["MTBF", summary["mtbf"], "ساعت", "میانگین زمان بین خرابی‌ها"],
            ]
            for row in data:
                ws.append(row)
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 22

            # EM sheet
            em_ws = wb.create_sheet("توقفات EM")
            em_rows = db.fetch_all("""
                SELECT wo.order_number, e.name, wo.operator, wo.work_date,
                       wo.downtime_minutes, wo.priority, wo.status,
                       wo.root_cause, wo.action_taken
                FROM work_orders wo LEFT JOIN equipment e ON wo.equipment_id=e.id
                WHERE wo.order_type='EM' AND strftime('%Y-%m', wo.work_date)=?
            """, (month,))
            em_headers = ["شماره", "تجهیز", "اپراتور", "تاریخ",
                          "توقف (دقیقه)", "اولویت", "وضعیت", "علت", "اقدام"]
            em_ws.append(em_headers)
            for cell in em_ws[1]:
                cell.fill = orange_fill
                cell.font = Font(bold=True, color="000000")
            for r in em_rows:
                em_ws.append([r["order_number"], r["name"] or "", r["operator"],
                               r["work_date"], r["downtime_minutes"],
                               r["priority"], r["status"],
                               r["root_cause"] or "", r["action_taken"] or ""])

            wb.save(path)
            from widgets import ToastNotification
            ToastNotification(self, "گزارش اکسل ذخیره شد", "success")
        except Exception as ex:
            messagebox.showerror("خطا", str(ex))
    