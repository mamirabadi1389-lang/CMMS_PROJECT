"""
CMMS PM Schedule & Spare Parts pages
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta

import database as db
import api_client
import equip_sync
import wo_sync
from styles import COLORS, FONTS, OPERATOR_COLORS
from widgets import SectionTitle, StyledTreeview, IconButton, FormField, ToastNotification


def _current_username():
    u = api_client.current_user or {}
    return u.get("username") or "-"


# ─── PM Schedule Page ──────────────────────────────────────────────────────────

class PMSchedulePage(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self.is_admin = (api_client.current_user or {}).get("role") == "admin"
        self._build_ui()
        self.refresh()
        equip_sync.pull_async(callback=self._after_sync)

    def _after_sync(self, result):
        def ui():
            equip_sync.notify_new_items(self, result, _current_username(), ToastNotification)
            self.refresh()
        self.after(0, ui)

    def _build_ui(self):
        hdr = tk.Frame(self, bg=COLORS["bg_header"])
        hdr.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(hdr, text="برنامه نگهداری پیشگیرانه (PM)", font=FONTS["title"],
                 bg=COLORS["bg_header"], fg=COLORS["text_primary"]).pack(side="right", pady=12)
        if self.is_admin:
            IconButton(hdr, "برنامه جدید", "＋", self._add_pm,
                       color=COLORS["blue"]).pack(side="left", pady=8)
        IconButton(hdr, "بروزرسانی", "🔄", self._manual_sync,
                   color=COLORS["blue"]).pack(side="left", pady=8, padx=6)
        # Filter row
        flt = tk.Frame(self, bg=COLORS["bg_dark"])
        flt.pack(fill="x", padx=20, pady=4)
        self.show_due = tk.BooleanVar(value=False)
        tk.Checkbutton(flt, text="فقط سررسید شده", variable=self.show_due,
                       bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                       selectcolor=COLORS["bg_input"], font=FONTS["body"],
                       activebackground=COLORS["bg_dark"], cursor="hand2",
                       command=self.refresh).pack(side="right")

        # Status summary badges
        badge_row = tk.Frame(self, bg=COLORS["bg_dark"])
        badge_row.pack(fill="x", padx=20, pady=4)
        self.badge_overdue = tk.Label(badge_row, text="گذشته: 0",
                                      font=FONTS["small"],
                                      bg=COLORS["red_dim"], fg=COLORS["red"], padx=10, pady=4)
        self.badge_overdue.pack(side="right", padx=4)
        self.badge_due7 = tk.Label(badge_row, text="این هفته: 0",
                                   font=FONTS["small"],
                                   bg=COLORS["yellow_dim"], fg=COLORS["yellow"], padx=10, pady=4)
        self.badge_due7.pack(side="right", padx=4)
        self.badge_ok = tk.Label(badge_row, text="به‌روز: 0",
                                 font=FONTS["small"],
                                 bg=COLORS["green_dim"], fg=COLORS["green"], padx=10, pady=4)
        self.badge_ok.pack(side="right", padx=4)

        # Tree
        cols = ("تجهیز", "وظیفه", "تناوب (روز)", "آخرین انجام", "سررسید بعدی",
                "اپراتور", "زمان تخمینی (h)", "وضعیت", "ثبت‌کننده")
        self.tree = StyledTreeview(self, cols, row_height=34)
        self.tree.pack(fill="both", expand=True, padx=20, pady=4)
        widths = [160, 180, 90, 100, 100, 80, 100, 90, 100]
        for col, w in zip(cols, widths):
            self.tree.tree.column(col, width=w)

        self.tree.tree.tag_configure("overdue", foreground=COLORS["red"])
        self.tree.tree.tag_configure("due_soon", foreground=COLORS["yellow"])
        self.tree.tree.tag_configure("ok", foreground=COLORS["green"])

        btn_row = tk.Frame(self, bg=COLORS["bg_dark"])
        btn_row.pack(fill="x", padx=20, pady=8)
        if self.is_admin:
            IconButton(btn_row, "ثبت انجام", "✓", self._mark_done,
                       color=COLORS["green"]).pack(side="right", padx=4)
            IconButton(btn_row, "ویرایش", "✏️", self._edit_selected,
                       color=COLORS["blue"]).pack(side="right", padx=4)
            IconButton(btn_row, "حذف", "🗑️", self._delete_selected,
                       color=COLORS["red"]).pack(side="right", padx=4)
    def _manual_sync(self):
        """بروزرسانی دستی از سرور"""
        def work():
            try:
                result = equip_sync.pull()
                def ok():
                    equip_sync.notify_new_items(self, result, _current_username(), ToastNotification)
                    self.refresh()
                    ToastNotification(self, "بروزرسانی شد ✓", "success")
                self.after(0, ok)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"بروزرسانی ناموفق: {err}", "error"))
        threading.Thread(target=work, daemon=True).start()
    def refresh(self):
        try:
            prev_sel = self.tree.tree.selection()   # در equipment: self.eq_tree.selection()
        except Exception:
            prev_sel = ()
        rows = db.fetch_all("""
            SELECT ps.*, e.name as eq_name
            FROM pm_schedules ps JOIN equipment e ON ps.equipment_id=e.id
            WHERE ps.active=1
            ORDER BY ps.next_due
        """)
        self.tree.clear()
        today = date.today().isoformat()
        week = (date.today() + timedelta(days=7)).isoformat()
        overdue = due7 = ok = 0

        for r in rows:
            nd = r["next_due"] or ""
            if nd < today:
                tag = "overdue"
                status = "🔴 گذشته"
                overdue += 1
            elif nd <= week:
                tag = "due_soon"
                status = "🟡 این هفته"
                due7 += 1
            else:
                tag = "ok"
                status = "✅ به‌روز"
                ok += 1

            if self.show_due.get() and tag == "ok":
                continue

            self.tree.insert(
                (r["eq_name"], r["task_name"],
                 r["frequency_days"], r["last_done"] or "-",
                 r["next_due"] or "-", r["operator"] or "-",
                 r["estimated_hours"], status,
                 r["created_by"] if "created_by" in r.keys() and r["created_by"] else "-"),
                tags=(tag,),
                iid=str(r["id"])
            )

        self.badge_overdue.configure(text=f"گذشته: {overdue}")
        self.badge_due7.configure(text=f"این هفته: {due7}")
        self.badge_ok.configure(text=f"به‌روز: {ok}")
                # حفظ انتخاب کاربر هنگام رفرش خودکار
        for iid in prev_sel:
            if self.tree.tree.exists(iid):
                self.tree.tree.selection_set(iid)
                break
    def _get_sel_id(self):
        sel = self.tree.tree.selection()
        if not sel:
            messagebox.showinfo("انتخاب", "لطفاً یک برنامه PM انتخاب کنید")
            return None
        return int(sel[0])

    def _mark_done(self):
        pid = self._get_sel_id()
        if not pid:
            return
        pm = db.fetch_one("SELECT * FROM pm_schedules WHERE id=?", (pid,))
        if not pm:
            return
        today = date.today()
        next_due = (today + timedelta(days=pm["frequency_days"])).isoformat()
        eq = db.fetch_one("SELECT * FROM equipment WHERE id=?", (pm["equipment_id"],))

        def work():
            try:
                equip_sync.update_pm(pid, {"last_done": today.isoformat(), "next_due": next_due})
                res = wo_sync.create({
                    "order_type": "PM",
                    "equipment_id": pm["equipment_id"],
                    "eq_name": eq["name"] if eq else None,
                    "location": eq["location"] if eq else None,
                    "operator": pm["operator"] or "مکانیک",
                    "description": f"انجام PM: {pm['task_name']}",
                    "work_date": today.isoformat(),
                    "status": "بسته",
                    "priority": "متوسط",
                })
                order_num = res.get("order_number", "") if isinstance(res, dict) else ""
                def ok():
                    ToastNotification(self, f"PM انجام شد — {order_num} صادر شد", "success")
                    self.refresh()
                    self.app.refresh_dashboard()
                self.after(0, ok)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))

        threading.Thread(target=work, daemon=True).start()

    def _add_pm(self):
        self._pm_dialog(None)

    def _edit_selected(self):
        pid = self._get_sel_id()
        if pid:
            self._pm_dialog(pid)

    def _delete_selected(self):
        pid = self._get_sel_id()
        if not pid:
            return
        if messagebox.askyesno("حذف", "این برنامه PM حذف شود؟"):
            def work():
                try:
                    equip_sync.update_pm(pid, {"active": 0})
                    def ok():
                        ToastNotification(self, "برنامه PM حذف شد", "info")
                        self.refresh()
                    self.after(0, ok)
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))
            threading.Thread(target=work, daemon=True).start()

    def _pm_dialog(self, pm_id):
        existing = db.fetch_one("SELECT * FROM pm_schedules WHERE id=?", (pm_id,)) if pm_id else None
        equips = db.fetch_all("SELECT id, name, code FROM equipment WHERE status='فعال' ORDER BY name")
        eq_map = {f"{e['name']} ({e['code'] or ''})": e["id"] for e in equips}
        eq_names = list(eq_map.keys())

        dlg = tk.Toplevel(self)
        dlg.title("ویرایش برنامه PM" if existing else "برنامه PM جدید")
        dlg.configure(bg=COLORS["bg_dark"])
        dlg.geometry("520x420")
        dlg.grab_set()

        card = tk.Frame(dlg, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        f_eq = FormField(card, "تجهیز", "combobox", eq_names, required=True)
        f_eq.pack(fill="x", padx=16, pady=6)
        if existing:
            eq = db.fetch_one("SELECT name, code FROM equipment WHERE id=?", (existing["equipment_id"],))
            if eq:
                f_eq.set(f"{eq['name']} ({eq['code'] or ''})")

        f_task = FormField(card, "نام وظیفه", required=True)
        f_task.pack(fill="x", padx=16, pady=6)
        if existing:
            f_task.set(existing["task_name"])

        row2 = tk.Frame(card, bg=COLORS["bg_card"])
        row2.pack(fill="x", padx=16, pady=6)
        f_freq = FormField(row2, "تناوب (روز)", required=True)
        f_freq.set(str(existing["frequency_days"]) if existing else "30")
        f_freq.pack(side="right", fill="x", expand=True, padx=(4, 0))
        f_hrs = FormField(row2, "زمان تخمینی (ساعت)")
        f_hrs.set(str(existing["estimated_hours"]) if existing else "1.0")
        f_hrs.pack(side="right", fill="x", expand=True)

        f_op = FormField(card, "اپراتور مسئول", "combobox",
                         ["مکانیک", "برق", "تاسیسات"])
        f_op.set(existing["operator"] if existing and existing["operator"] else "مکانیک")
        f_op.pack(fill="x", padx=16, pady=6)

        def _save():
            eq_str = f_eq.get()
            if eq_str not in eq_map:
                messagebox.showerror("خطا", "تجهیز را انتخاب کنید")
                return
            task = f_task.get().strip()
            if not task:
                messagebox.showerror("خطا", "نام وظیفه الزامی است")
                return
            try:
                freq = int(f_freq.get())
                hrs = float(f_hrs.get())
            except ValueError:
                messagebox.showerror("خطا", "تناوب و ساعت باید عدد باشند")
                return
            eq_id = eq_map[eq_str]
            eq_name_only = eq_str.rsplit(" (", 1)[0]
            today = date.today().isoformat()
            next_due = (date.today() + timedelta(days=freq)).isoformat()

            def work():
                try:
                    if pm_id:
                        equip_sync.update_pm(pm_id, {
                            "eq_name": eq_name_only, "task_name": task,
                            "frequency_days": freq, "operator": f_op.get(),
                            "estimated_hours": hrs,
                        })
                    else:
                        equip_sync.create_pm({
                            "eq_name": eq_name_only, "task_name": task,
                            "frequency_days": freq, "last_done": today,
                            "next_due": next_due, "operator": f_op.get(),
                            "estimated_hours": hrs, "active": True,
                        })
                    def ok():
                        dlg.destroy()
                        ToastNotification(self, "برنامه PM ذخیره شد", "success")
                        self.refresh()
                    self.after(0, ok)
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda: ToastNotification(self, f"ذخیره نشد: {err}", "error"))

            threading.Thread(target=work, daemon=True).start()

        btn_row = tk.Frame(dlg, bg=COLORS["bg_dark"])
        btn_row.pack(fill="x", padx=16, pady=8)
        IconButton(btn_row, "ذخیره", "💾", _save, color=COLORS["accent"]).pack(side="right")
        IconButton(btn_row, "انصراف", "✗", dlg.destroy, color=COLORS["bg_card"]).pack(side="right", padx=(0, 8))


# ─── Spare Parts Page ──────────────────────────────────────────────────────────

class SparePartsPage(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self.is_admin = (api_client.current_user or {}).get("role") == "admin"
        self._build_ui()
        self.refresh()
        equip_sync.pull_async(callback=self._after_sync)

    def _after_sync(self, result):
        def ui():
            equip_sync.notify_new_items(self, result, _current_username(), ToastNotification)
            self.refresh()
        self.after(0, ui)

    def _build_ui(self):
        hdr = tk.Frame(self, bg=COLORS["bg_header"])
        hdr.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(hdr, text="انبار قطعات یدکی", font=FONTS["title"],
                 bg=COLORS["bg_header"], fg=COLORS["text_primary"]).pack(side="right", pady=12)
        if self.is_admin:
            IconButton(hdr, "قطعه جدید", "＋", self._add_part,
                       color=COLORS["green"]).pack(side="left", pady=8)
        IconButton(hdr, "بروزرسانی", "🔄", self._manual_sync,
                   color=COLORS["blue"]).pack(side="left", pady=8, padx=6)
        # Search
        sf = tk.Frame(self, bg=COLORS["bg_input"],
                      highlightbackground=COLORS["border"], highlightthickness=1)
        sf.pack(fill="x", padx=20, pady=4)
        tk.Label(sf, text="🔍", bg=COLORS["bg_input"], fg=COLORS["text_muted"]).pack(side="left", padx=4)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        tk.Entry(sf, textvariable=self.search_var, font=FONTS["body"],
                 bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                 insertbackground=COLORS["accent"], relief="flat", bd=0, width=30).pack(
            side="left", ipady=5, padx=4)

        # Only low stock toggle
        self.low_only = tk.BooleanVar(value=False)
        tk.Checkbutton(sf, text="فقط کم‌موجودی", variable=self.low_only,
                       bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                       selectcolor=COLORS["bg_card"], font=FONTS["body"],
                       activebackground=COLORS["bg_input"], cursor="hand2",
                       command=self.refresh).pack(side="right", padx=8)

        cols = ("نام قطعه", "شماره قطعه", "دسته", "موجودی", "واحد",
                "حداقل", "موقعیت انبار", "تأمین‌کننده", "وضعیت", "ثبت‌کننده")
        self.tree = StyledTreeview(self, cols)
        self.tree.pack(fill="both", expand=True, padx=20, pady=4)
        widths = [180, 100, 90, 70, 60, 70, 100, 120, 80, 100]
        for col, w in zip(cols, widths):
            self.tree.tree.column(col, width=w)

        self.tree.tree.tag_configure("low_stock", foreground=COLORS["red"])
        self.tree.tree.tag_configure("warn_stock", foreground=COLORS["yellow"])
        self.tree.tree.tag_configure("ok_stock", foreground=COLORS["green"])

        btn_row = tk.Frame(self, bg=COLORS["bg_dark"])
        btn_row.pack(fill="x", padx=20, pady=8)
        if self.is_admin:
            IconButton(btn_row, "ویرایش", "✏️", self._edit_selected,
                       color=COLORS["blue"]).pack(side="right", padx=4)
            IconButton(btn_row, "تعدیل موجودی", "±", self._adjust_quantity,
                       color=COLORS["yellow"]).pack(side="right", padx=4)
            IconButton(btn_row, "حذف", "🗑️", self._delete_selected,
                       color=COLORS["red"]).pack(side="right", padx=4)

        # Summary
        self.summary_lbl = tk.Label(self, text="", font=FONTS["small"],
                                    bg=COLORS["bg_dark"], fg=COLORS["text_muted"])
        self.summary_lbl.pack(side="bottom", pady=4)
    def _manual_sync(self):
        """بروزرسانی دستی از سرور"""
        def work():
            try:
                result = equip_sync.pull()
                def ok():
                    equip_sync.notify_new_items(self, result, _current_username(), ToastNotification)
                    self.refresh()
                    ToastNotification(self, "بروزرسانی شد ✓", "success")
                self.after(0, ok)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"بروزرسانی ناموفق: {err}", "error"))
        threading.Thread(target=work, daemon=True).start()
    def refresh(self):
        try:
            prev_sel = self.tree.tree.selection()   # در equipment: self.eq_tree.selection()
        except Exception:
            prev_sel = ()
        search = self.search_var.get().strip().lower()
        rows = db.fetch_all("SELECT * FROM spare_parts ORDER BY name")
        self.tree.clear()
        low = warn = ok = 0
        for r in rows:
            if search and search not in f"{r['name']} {r['part_number'] or ''} {r['category'] or ''}".lower():
                continue
            ratio = r["quantity"] / max(r["min_stock"], 1)
            if r["quantity"] <= 0:
                tag = "low_stock"
                status = "🔴 تمام شده"
                low += 1
            elif ratio < 1:
                tag = "low_stock"
                status = "🔴 کم"
                low += 1
            elif ratio < 1.5:
                tag = "warn_stock"
                status = "🟡 کم"
                warn += 1
            else:
                tag = "ok_stock"
                status = "✅ کافی"
                ok += 1
            if self.low_only.get() and tag == "ok_stock":
                continue
            self.tree.insert(
                (r["name"], r["part_number"] or "-", r["category"] or "-",
                 r["quantity"], r["unit"],
                 r["min_stock"], r["location"] or "-",
                 r["supplier"] or "-", status,
                 r["created_by"] if "created_by" in r.keys() and r["created_by"] else "-"),
                tags=(tag,),
                iid=str(r["id"])
            )
        self.summary_lbl.configure(
            text=f"کل قطعات: {low+warn+ok}  |  کم‌موجودی: {low}  |  هشدار: {warn}  |  کافی: {ok}"
        )
                    # حفظ انتخاب کاربر هنگام رفرش خودکار
        for iid in prev_sel:
            if self.tree.tree.exists(iid):
                self.tree.tree.selection_set(iid)
                break
    def _get_sel_id(self):
        sel = self.tree.tree.selection()
        if not sel:
            messagebox.showinfo("انتخاب", "یک قطعه انتخاب کنید")
            return None
        return int(sel[0])

    def _add_part(self):
        self._part_dialog(None)

    def _edit_selected(self):
        pid = self._get_sel_id()
        if pid:
            self._part_dialog(pid)

    def _delete_selected(self):
        pid = self._get_sel_id()
        if not pid:
            return
        if messagebox.askyesno("حذف", "این قطعه حذف شود؟"):
            def work():
                try:
                    equip_sync.delete_part(pid)
                    def ok():
                        ToastNotification(self, "قطعه حذف شد", "info")
                        self.refresh()
                    self.after(0, ok)
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))
            threading.Thread(target=work, daemon=True).start()

    def _adjust_quantity(self):
        pid = self._get_sel_id()
        if not pid:
            return
        part = db.fetch_one("SELECT * FROM spare_parts WHERE id=?", (pid,))
        if not part:
            return
        dlg = tk.Toplevel(self)
        dlg.title(f"تعدیل موجودی: {part['name']}")
        dlg.configure(bg=COLORS["bg_dark"])
        dlg.geometry("320x200")
        dlg.grab_set()

        card = tk.Frame(dlg, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(card, text=f"موجودی فعلی: {part['quantity']} {part['unit']}",
                 font=FONTS["body_bold"], bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"]).pack(padx=16, pady=8, anchor="e")

        f_delta = FormField(card, "تغییر موجودی (+ اضافه / - کسر)")
        f_delta.set("0")
        f_delta.pack(fill="x", padx=16, pady=4)

        def _save():
            try:
                delta = int(f_delta.get())
            except ValueError:
                messagebox.showerror("خطا", "عدد صحیح وارد کنید")
                return
            new_qty = max(0, part["quantity"] + delta)

            def work():
                try:
                    equip_sync.update_part(pid, {"quantity": new_qty})
                    def ok():
                        dlg.destroy()
                        ToastNotification(self, f"موجودی به {new_qty} {part['unit']} تغییر یافت", "success")
                        self.refresh()
                    self.after(0, ok)
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))
            threading.Thread(target=work, daemon=True).start()

        IconButton(card, "ذخیره", "💾", _save, color=COLORS["accent"]).pack(pady=8)

    def _part_dialog(self, part_id):
        existing = db.fetch_one("SELECT * FROM spare_parts WHERE id=?", (part_id,)) if part_id else None
        dlg = tk.Toplevel(self)
        dlg.title("ویرایش قطعه" if existing else "قطعه جدید")
        dlg.configure(bg=COLORS["bg_dark"])
        dlg.geometry("520x480")
        dlg.grab_set()

        card = tk.Frame(dlg, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        field_defs = [
            ("name", "نام قطعه", "entry", None, True),
            ("part_number", "شماره قطعه", "entry", None, False),
            ("category", "دسته", "combobox",
             ["بیرینگ", "تسمه", "روانکار", "فیلتر", "برق", "لوله‌کشی", "هیدرولیک", "پنوماتیک", "سایر"], False),
            ("quantity", "موجودی", "entry", None, False),
            ("unit", "واحد", "combobox", ["عدد", "کیلو", "لیتر", "متر", "جفت"], False),
            ("min_stock", "حداقل موجودی", "entry", None, False),
            ("location", "موقعیت انبار", "entry", None, False),
            ("supplier", "تأمین‌کننده", "entry", None, False),
        ]

        flds = {}
        row_fr = None
        for idx, (key, lbl, ftype, opts, req) in enumerate(field_defs):
            if idx % 2 == 0:
                row_fr = tk.Frame(card, bg=COLORS["bg_card"])
                row_fr.pack(fill="x", padx=16, pady=3)
            f = FormField(row_fr, lbl, ftype, opts, required=req)
            f.pack(side="right" if idx % 2 == 0 else "left",
                   fill="x", expand=True, padx=(4, 0) if idx % 2 == 0 else (0, 4))
            if existing and existing.get(key) is not None:
                f.set(str(existing[key]))
            elif key == "unit":
                f.set("عدد")
            elif key in ("quantity", "min_stock"):
                f.set("0")
            flds[key] = f

        def _save():
            name = flds["name"].get().strip()
            if not name:
                messagebox.showerror("خطا", "نام قطعه الزامی است")
                return
            try:
                qty = int(flds["quantity"].get() or 0)
                minq = int(flds["min_stock"].get() or 0)
            except ValueError:
                messagebox.showerror("خطا", "موجودی باید عدد باشد")
                return
            data = {
                "name": name, "part_number": flds["part_number"].get(),
                "category": flds["category"].get(), "quantity": qty,
                "unit": flds["unit"].get(), "min_stock": minq,
                "location": flds["location"].get(), "supplier": flds["supplier"].get(),
            }

            def work():
                try:
                    if part_id:
                        equip_sync.update_part(part_id, data)
                    else:
                        equip_sync.create_part(data)
                    def ok():
                        dlg.destroy()
                        ToastNotification(self, "قطعه ذخیره شد", "success")
                        self.refresh()
                    self.after(0, ok)
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda: ToastNotification(self, f"ذخیره نشد: {err}", "error"))

            threading.Thread(target=work, daemon=True).start()

        btn_row = tk.Frame(dlg, bg=COLORS["bg_dark"])
        btn_row.pack(fill="x", padx=16, pady=8)
        IconButton(btn_row, "ذخیره", "💾", _save, color=COLORS["accent"]).pack(side="right")
        IconButton(btn_row, "انصراف", "✗", dlg.destroy, color=COLORS["bg_card"]).pack(side="right", padx=(0, 8))
