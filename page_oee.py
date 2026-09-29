# page_oee.py — OEE (کارایی کلی تجهیزات / زمان مفید کارکرد)
import tkinter as tk
from tkinter import ttk
from datetime import date

import oee_data
from styles import COLORS, FONTS
from widgets import (SectionTitle, IconButton, FormField, ToastNotification,
                     StyledTreeview, GaugeMeter, KPICard)

PERIODS = [("۷ روز اخیر", 7), ("۳۰ روز اخیر", 30), ("۹۰ روز اخیر", 90), ("۱ سال اخیر", 365)]


class OEEPage(tk.Frame):
    def __init__(self, parent, app=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self._days = 30
        self._rows = []
        self._selected_id = None
        self._build_ui()
        self.refresh()

    # ---------------- ساخت رابط ----------------
    def _build_ui(self):
        hdr = tk.Frame(self, bg=COLORS["bg_header"])
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text="📈 OEE — زمان مفید کارکرد تجهیزات", font=FONTS["title"],
                 bg=COLORS["bg_header"], fg=COLORS["text_primary"]).pack(side="right", pady=12)

        period_fr = tk.Frame(hdr, bg=COLORS["bg_header"])
        period_fr.pack(side="left", pady=12)
        tk.Label(period_fr, text="بازه:", font=FONTS["small"],
                 bg=COLORS["bg_header"], fg=COLORS["text_secondary"]).pack(side="right", padx=(0, 6))
        self.period_cb = ttk.Combobox(period_fr, values=[p[0] for p in PERIODS],
                                      state="readonly", width=12, font=FONTS["small"])
        self.period_cb.current(1)
        self.period_cb.pack(side="right")
        self.period_cb.bind("<<ComboboxSelected>>", lambda e: self._on_period_change())

        # ---- KPI row ----
        kpi_row = tk.Frame(self, bg=COLORS["bg_dark"])
        kpi_row.pack(fill="x", padx=20, pady=(16, 8))
        self.kpi_oee  = KPICard(kpi_row, "میانگین OEE", "–", "٪", COLORS["accent"], "📈")
        self.kpi_av   = KPICard(kpi_row, "در دسترس بودن", "–", "٪", COLORS["blue"],   "🟢")
        self.kpi_perf = KPICard(kpi_row, "کارایی",        "–", "٪", COLORS["yellow"], "⚙️")
        self.kpi_qual = KPICard(kpi_row, "کیفیت",         "–", "٪", COLORS["green"],  "✅")
        for k in [self.kpi_oee, self.kpi_av, self.kpi_perf, self.kpi_qual]:
            k.pack(side="left", fill="x", expand=True, padx=4)

        # ---- Main split ----
        paned = tk.PanedWindow(self, orient="horizontal", bg=COLORS["bg_dark"],
                               sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=20, pady=8)

        left_card = tk.Frame(paned, bg=COLORS["bg_card"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
        paned.add(left_card, minsize=420)
        SectionTitle(left_card, "OEE هر تجهیز", "🏭").pack(fill="x", padx=8, pady=(8, 0))

        cols = ("name", "code", "availability", "performance", "quality", "oee")
        heads = ["تجهیز", "کد", "دسترس‌پذیری", "کارایی", "کیفیت", "OEE"]
        self.tree = StyledTreeview(left_card, cols, heads)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.tree.bind("<<TreeviewSelect>>", self._on_select)

        right_card = tk.Frame(paned, bg=COLORS["bg_card"],
                              highlightbackground=COLORS["border"], highlightthickness=1)
        paned.add(right_card, minsize=340)
        SectionTitle(right_card, "جزئیات تجهیز", "🔍").pack(fill="x", padx=12, pady=(8, 0))

        self.detail_frame = tk.Frame(right_card, bg=COLORS["bg_card"])
        self.detail_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self._show_placeholder()

    def _show_placeholder(self):
        for w in self.detail_frame.winfo_children():
            w.destroy()
        tk.Label(self.detail_frame, text="یک تجهیز را از لیست انتخاب کنید",
                 font=FONTS["body"], bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"]).pack(expand=True, pady=40)

    # ---------------- به‌روزرسانی ----------------
    def _on_period_change(self):
        idx = self.period_cb.current()
        self._days = PERIODS[idx][1]
        self.refresh()

    def refresh(self):
        self._rows = oee_data.calc_oee_all(days=self._days)
        self._render()
        if self._selected_id:
            self._show_detail(self._selected_id)

    def _render(self):
        self.tree.clear()
        if not self._rows:
            self.kpi_oee.update_value("–"); self.kpi_av.update_value("–")
            self.kpi_perf.update_value("–"); self.kpi_qual.update_value("–")
            return
        for r in self._rows:
            self.tree.insert(
                (r["name"], r["code"] or "-", f"{r['availability']}٪",
                 f"{r['performance']}٪", f"{r['quality']}٪", f"{r['oee']}٪"),
                iid=str(r["equipment_id"]))
        n = len(self._rows)
        avg_oee = round(sum(r["oee"] for r in self._rows) / n, 1)
        avg_av  = round(sum(r["availability"] for r in self._rows) / n, 1)
        avg_pf  = round(sum(r["performance"] for r in self._rows) / n, 1)
        avg_ql  = round(sum(r["quality"] for r in self._rows) / n, 1)
        self.kpi_oee.update_value(avg_oee)
        self.kpi_av.update_value(avg_av)
        self.kpi_perf.update_value(avg_pf)
        self.kpi_qual.update_value(avg_ql)

    def _on_select(self, _evt=None):
        sel = self.tree.tree.selection()
        if not sel:
            return
        self._selected_id = int(sel[0])
        self._show_detail(self._selected_id)

    # ---------------- پنل جزئیات ----------------
    def _show_detail(self, equipment_id):
        row = next((r for r in self._rows if r["equipment_id"] == equipment_id), None)
        for w in self.detail_frame.winfo_children():
            w.destroy()
        if not row:
            self._show_placeholder()
            return

        tk.Label(self.detail_frame, text=row["name"], font=FONTS["heading"],
                 bg=COLORS["bg_card"], fg=COLORS["accent"]).pack(anchor="e", pady=(0, 8))

        gauge_fr = tk.Frame(self.detail_frame, bg=COLORS["bg_card"])
        gauge_fr.pack(fill="x")
        GaugeMeter(gauge_fr, value=row["oee"], max_val=100, label="OEE",
                   color=COLORS["accent"], size=150).pack()

        subs = tk.Frame(self.detail_frame, bg=COLORS["bg_card"])
        subs.pack(fill="x", pady=(6, 10))
        for lbl, val, clr in [("دسترس‌پذیری", row["availability"], COLORS["blue"]),
                              ("کارایی", row["performance"], COLORS["yellow"]),
                              ("کیفیت", row["quality"], COLORS["green"])]:
            f = tk.Frame(subs, bg=COLORS["bg_card"])
            f.pack(side="right", fill="x", expand=True)
            tk.Label(f, text=f"{val}٪", font=FONTS["subhead"],
                     bg=COLORS["bg_card"], fg=clr).pack()
            tk.Label(f, text=lbl, font=FONTS["small"],
                     bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack()

        tk.Label(self.detail_frame,
                 text=f"مجموع توقف اضطراری در بازه: {row['downtime_minutes'] or 0} دقیقه",
                 font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"]).pack(anchor="e", pady=(0, 10))

        tk.Frame(self.detail_frame, bg=COLORS["border"], height=1).pack(fill="x", pady=6)

        SectionTitle(self.detail_frame, "ثبت کارایی/کیفیت (دستی)", "✍️",
                    accent=False).pack(fill="x")

        form_fr = tk.Frame(self.detail_frame, bg=COLORS["bg_card"])
        form_fr.pack(fill="x", pady=6)
        self.f_date = FormField(form_fr, "تاریخ", required=True)
        self.f_date.set(date.today().isoformat())
        self.f_date.pack(fill="x", pady=3)
        self.f_perf = FormField(form_fr, "کارایی ٪ (اختیاری)")
        self.f_perf.pack(fill="x", pady=3)
        self.f_good = FormField(form_fr, "تعداد سالم (اختیاری)")
        self.f_good.pack(fill="x", pady=3)
        self.f_total = FormField(form_fr, "تعداد کل تولید (اختیاری)")
        self.f_total.pack(fill="x", pady=3)
        self.f_notes = FormField(form_fr, "یادداشت", "text")
        self.f_notes.pack(fill="x", pady=3)

        IconButton(form_fr, text="ثبت", icon="💾", command=lambda: self._add_entry(equipment_id),
                  color=COLORS["green"]).pack(pady=8)

        SectionTitle(self.detail_frame, "سوابق دستیِ اخیر", "🗂️",
                    accent=False).pack(fill="x", pady=(6, 0))
        hist_cols = ("date", "perf", "qual", "notes")
        self.hist_tree = StyledTreeview(self.detail_frame, hist_cols,
                                        ["تاریخ", "کارایی", "کیفیت", "یادداشت"], row_height=26)
        self.hist_tree.pack(fill="both", expand=True, pady=(4, 4))
        entries = oee_data.list_entries(equipment_id=equipment_id, limit=30)
        for e in entries:
            self.hist_tree.insert((e["entry_date"],
                                   f"{e['performance_pct']}٪" if e["performance_pct"] is not None else "-",
                                   f"{e['quality_pct']}٪" if e["quality_pct"] is not None else "-",
                                   e["notes"] or ""), iid=str(e["id"]))
        IconButton(self.detail_frame, text="حذف رکورد انتخاب‌شده", icon="🗑",
                  command=lambda: self._delete_entry(equipment_id),
                  color=COLORS["red"], fg="#fff", width=160).pack(pady=(0, 6))

    def _add_entry(self, equipment_id):
        entry_date = self.f_date.get().strip() or date.today().isoformat()

        def _to_float(v):
            try:
                return float(v) if str(v).strip() != "" else None
            except ValueError:
                return None

        def _to_int(v):
            try:
                return int(v) if str(v).strip() != "" else None
            except ValueError:
                return None

        try:
            oee_data.add_entry(
                equipment_id, entry_date,
                performance_pct=_to_float(self.f_perf.get()),
                good_qty=_to_int(self.f_good.get()),
                total_qty=_to_int(self.f_total.get()),
                notes=self.f_notes.get().strip())
            ToastNotification(self, "ثبت شد", "success")
            self.refresh()
        except Exception as e:
            ToastNotification(self, f"خطا: {e}", "error")

    def _delete_entry(self, equipment_id):
        sel = self.hist_tree.tree.selection()
        if not sel:
            ToastNotification(self, "ابتدا یک رکورد را انتخاب کنید", "info")
            return
        try:
            oee_data.delete_entry(int(sel[0]))
            ToastNotification(self, "حذف شد", "success")
            self.refresh()
        except Exception as e:
            ToastNotification(self, f"خطا: {e}", "error")
