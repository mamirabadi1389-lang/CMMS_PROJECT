
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import database as db
import api_client
import equip_sync
from styles import COLORS, FONTS
from widgets import SectionTitle, IconButton, FormField, ToastNotification, StyledTreeview


def _current_username():
    u = api_client.current_user or {}
    return u.get("username") or "-"


class EquipmentPage(tk.Frame):
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
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=COLORS["bg_header"])
        hdr.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(hdr, text="مدیریت تجهیزات", font=FONTS["title"],
                 bg=COLORS["bg_header"], fg=COLORS["text_primary"]).pack(side="right", pady=12)
        tk.Label(hdr, text="سلسله‌مراتب: دسته‌بندی  ←  تجهیز",
                 font=FONTS["small"], bg=COLORS["bg_header"],
                 fg=COLORS["text_secondary"]).pack(side="left", pady=12)
        IconButton(hdr, "بروزرسانی", "🔄", self._manual_sync,
                   color=COLORS["blue"]).pack(side="left", pady=8, padx=6)

        # ── Main split: tree (left) + detail (right) ───────────────────────
        paned = tk.PanedWindow(self, orient="horizontal",
                               bg=COLORS["bg_dark"], sashwidth=6,
                               sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=20, pady=8)

        # ── Left: Hierarchy tree ───────────────────────────────────────────
        left_card = tk.Frame(paned, bg=COLORS["bg_card"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
        paned.add(left_card, minsize=280)

        tree_hdr = tk.Frame(left_card, bg=COLORS["bg_card"])
        tree_hdr.pack(fill="x", padx=8, pady=(8, 0))
        SectionTitle(tree_hdr, "ساختار تجهیزات", "🏗️").pack(side="right")

        # Buttons row
        tree_btns = tk.Frame(left_card, bg=COLORS["bg_card"])
        tree_btns.pack(fill="x", padx=8, pady=4)
        if self.is_admin:
            tk.Button(tree_btns, text="+ دسته", font=FONTS["small"],
                      bg=COLORS["accent_dim"], fg=COLORS["accent"],
                      relief="flat", padx=8, cursor="hand2",
                      command=self._add_category).pack(side="right", padx=2)
            tk.Button(tree_btns, text="+ تجهیز", font=FONTS["small"],
                      bg=COLORS["blue_dim"], fg=COLORS["blue"],
                      relief="flat", padx=8, cursor="hand2",
                      command=self._add_equipment).pack(side="right", padx=2)
        tk.Button(tree_btns, text="▲ جمع", font=FONTS["small"],
                  bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                  relief="flat", padx=6, cursor="hand2",
                  command=lambda: self._collapse_all()).pack(side="left", padx=2)
        tk.Button(tree_btns, text="▼ باز", font=FONTS["small"],
                  bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                  relief="flat", padx=6, cursor="hand2",
                  command=lambda: self._expand_all()).pack(side="left", padx=2)

        # Style tree
        style = ttk.Style()
        style.configure("Equip.Treeview",
                        background=COLORS["bg_table"],
                        foreground=COLORS["text_primary"],
                        fieldbackground=COLORS["bg_table"],
                        rowheight=28, font=FONTS["body"],
                        borderwidth=0)
        style.configure("Equip.Treeview.Heading",
                        background=COLORS["bg_header"],
                        foreground=COLORS["accent"],
                        font=FONTS["body_bold"])
        style.map("Equip.Treeview",
                  background=[("selected", COLORS["accent_dim"])],
                  foreground=[("selected", COLORS["text_primary"])])

        vsb = tk.Scrollbar(left_card, orient="vertical", bg=COLORS["bg_dark"])
        self.eq_tree = ttk.Treeview(left_card, columns=("name", "code", "status"),
                                    show="tree headings", style="Equip.Treeview",
                                    yscrollcommand=vsb.set, selectmode="browse")
        vsb.configure(command=self.eq_tree.yview)
        self.eq_tree.heading("#0", text="دسته/تجهیز", anchor="e")
        self.eq_tree.heading("name", text="نام", anchor="center")
        self.eq_tree.heading("code", text="کد", anchor="center")
        self.eq_tree.heading("status", text="وضعیت", anchor="center")
        self.eq_tree.column("#0", width=30, minwidth=30)
        self.eq_tree.column("name", width=160, minwidth=100, anchor="e")
        self.eq_tree.column("code", width=80, minwidth=60, anchor="center")
        self.eq_tree.column("status", width=70, minwidth=60, anchor="center")

        self.eq_tree.tag_configure("category", foreground=COLORS["accent"],
                                   font=FONTS["body_bold"])
        self.eq_tree.tag_configure("active", foreground=COLORS["green"])
        self.eq_tree.tag_configure("inactive", foreground=COLORS["text_muted"])
        self.eq_tree.tag_configure("breakdown", foreground=COLORS["red"])

        self.eq_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        vsb.pack(side="right", fill="y", pady=4)
        self.eq_tree.bind("<<TreeviewSelect>>", self._on_select)
        self.eq_tree.bind("<Double-1>", self._on_double_click)

        # ── Right: Detail panel ────────────────────────────────────────────
        right_card = tk.Frame(paned, bg=COLORS["bg_card"],
                              highlightbackground=COLORS["border"], highlightthickness=1)
        paned.add(right_card, minsize=380)

        SectionTitle(right_card, "اطلاعات تجهیز", "📋").pack(fill="x", padx=12, pady=(8, 0))

        self.detail_frame = tk.Frame(right_card, bg=COLORS["bg_card"])
        self.detail_frame.pack(fill="both", expand=True, padx=12, pady=8)

        self._show_placeholder()

        # Action buttons
        btn_row = tk.Frame(right_card, bg=COLORS["bg_card"])
        btn_row.pack(fill="x", padx=12, pady=8)
        self.btn_edit = tk.Button(btn_row, text="✏️  ویرایش", font=FONTS["body_bold"],
                                  bg=COLORS["blue_dim"], fg=COLORS["blue"],
                                  relief="flat", padx=12, pady=6, cursor="hand2",
                                  command=self._edit_selected, state="disabled")
        self.btn_edit.pack(side="right", padx=4)
        self.btn_del = tk.Button(btn_row, text="🗑️  حذف", font=FONTS["body_bold"],
                                 bg=COLORS["red_dim"], fg=COLORS["red"],
                                 relief="flat", padx=12, pady=6, cursor="hand2",
                                 command=self._delete_selected, state="disabled")
        self.btn_del.pack(side="right", padx=4)
        self.btn_history = tk.Button(btn_row, text="📋  سابقه تعمیرات", font=FONTS["body_bold"],
                                     bg=COLORS["bg_input"], fg=COLORS["text_secondary"],
                                     relief="flat", padx=12, pady=6, cursor="hand2",
                                     command=self._show_history, state="disabled")
        self.btn_history.pack(side="left", padx=4)

    def _show_placeholder(self):
        for w in self.detail_frame.winfo_children():
            w.destroy()
        tk.Label(self.detail_frame, text="یک تجهیز را از لیست انتخاب کنید",
                 font=FONTS["body"], bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"]).pack(expand=True, pady=40)

    def refresh(self):
        try:
            prev_sel = self.tree.tree.selection()   # در equipment: self.eq_tree.selection()
        except Exception:
            prev_sel = ()
        self.eq_tree.delete(*self.eq_tree.get_children())
        categories = db.fetch_all("SELECT * FROM equipment_categories ORDER BY name")
        for cat in categories:
            cat_iid = f"cat_{cat['id']}"
            self.eq_tree.insert("", "end", iid=cat_iid,
                                text=f"  {cat['icon']}",
                                values=(cat["name"], "", ""),
                                tags=("category",), open=True)
            equips = db.fetch_all(
                "SELECT * FROM equipment WHERE category_id=? ORDER BY name",
                (cat["id"],)
            )
            for eq in equips:
                tag = {"فعال": "active", "غیرفعال": "inactive",
                       "در تعمیر": "breakdown"}.get(eq["status"], "active")
                status_icon = {"فعال": "✅", "غیرفعال": "⭕",
                               "در تعمیر": "🔴"}.get(eq["status"], "")
                self.eq_tree.insert(cat_iid, "end", iid=f"eq_{eq['id']}",
                                    text="  ",
                                    values=(eq["name"], eq["code"] or "",
                                            f"{status_icon} {eq['status']}"),
                                    tags=(tag,))
                        # حفظ انتخاب کاربر هنگام رفرش خودکار
            for iid in prev_sel:
                if self.tree.tree.exists(iid):
                    self.tree.tree.selection_set(iid)
                    break
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
    def _on_select(self, event):
        sel = self.eq_tree.selection()
        if not sel:
            return
        edit_del_state = "normal" if self.is_admin else "disabled"
        iid = sel[0]
        if iid.startswith("cat_"):
            self._show_category_detail(int(iid[4:]))
            self.btn_edit.configure(state=edit_del_state)
            self.btn_del.configure(state=edit_del_state)
            self.btn_history.configure(state="disabled")
        elif iid.startswith("eq_"):
            self._show_equipment_detail(int(iid[3:]))
            self.btn_edit.configure(state=edit_del_state)
            self.btn_del.configure(state=edit_del_state)
            self.btn_history.configure(state="normal")

    def _on_double_click(self, event):
        sel = self.eq_tree.selection()
        if sel:
            self._edit_selected()

    def _show_category_detail(self, cat_id):
        cat = db.fetch_one("SELECT * FROM equipment_categories WHERE id=?", (cat_id,))
        if not cat:
            return
        for w in self.detail_frame.winfo_children():
            w.destroy()

        count = db.fetch_one("SELECT COUNT(*) as c FROM equipment WHERE category_id=?", (cat_id,))
        row = tk.Frame(self.detail_frame, bg=COLORS["bg_card"])
        row.pack(fill="x", pady=8)
        tk.Label(row, text=cat["icon"], font=("Segoe UI Emoji", 36),
                 bg=COLORS["bg_card"]).pack(side="right", padx=16)
        info = tk.Frame(row, bg=COLORS["bg_card"])
        info.pack(side="right", fill="x", expand=True)
        tk.Label(info, text=cat["name"], font=FONTS["heading"],
                 bg=COLORS["bg_card"], fg=COLORS["accent"]).pack(anchor="e")
        tk.Label(info, text=f"تعداد تجهیزات: {count['c']}",
                 font=FONTS["body"], bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"]).pack(anchor="e")
        tk.Label(info, text=f"ایجاد: {cat['created_at'][:10]}",
                 font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"]).pack(anchor="e")
        self._current_selection = ("category", cat_id)

    def _show_equipment_detail(self, eq_id):
        eq = db.fetch_one("""
            SELECT e.*, c.name as cat_name, c.icon as cat_icon
            FROM equipment e LEFT JOIN equipment_categories c ON e.category_id=c.id
            WHERE e.id=?
        """, (eq_id,))
        if not eq:
            return
        for w in self.detail_frame.winfo_children():
            w.destroy()

        canvas = tk.Canvas(self.detail_frame, bg=COLORS["bg_card"], highlightthickness=0)
        sb = tk.Scrollbar(self.detail_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=COLORS["bg_card"])
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Header
        status_colors = {"فعال": COLORS["green"], "غیرفعال": COLORS["text_muted"],
                         "در تعمیر": COLORS["red"]}
        sc = status_colors.get(eq["status"], COLORS["text_muted"])
        hdr = tk.Frame(inner, bg=COLORS["bg_card"])
        hdr.pack(fill="x", pady=8)
        tk.Label(hdr, text=eq["cat_icon"] or "⚙️", font=("Segoe UI Emoji", 28),
                 bg=COLORS["bg_card"]).pack(side="right", padx=8)
        hdr_info = tk.Frame(hdr, bg=COLORS["bg_card"])
        hdr_info.pack(side="right", fill="x", expand=True)
        tk.Label(hdr_info, text=eq["name"], font=FONTS["heading"],
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(anchor="e")
        tk.Label(hdr_info, text=f"● {eq['status']}", font=FONTS["body_bold"],
                 bg=COLORS["bg_card"], fg=sc).pack(anchor="e")
        tk.Label(hdr_info, text=eq["cat_name"] or "", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(anchor="e")

        # Separator
        tk.Frame(inner, bg=COLORS["border"], height=1).pack(fill="x", pady=8)

        # Fields grid
        fields = [
            ("کد تجهیز", eq["code"]),
            ("موقعیت", eq["location"]),
            ("برند", eq["brand"]),
            ("مدل", eq["model"]),
            ("سریال", eq["serial_number"]),
            ("تاریخ نصب", eq["install_date"]),
            ("ثبت‌کننده", eq["created_by"] if "created_by" in eq.keys() else None),
        ]
        grid = tk.Frame(inner, bg=COLORS["bg_card"])
        grid.pack(fill="x", padx=4)
        for i, (lbl, val) in enumerate(fields):
            row_fr = tk.Frame(grid, bg=COLORS["bg_input" if i % 2 else "bg_card"])
            row_fr.pack(fill="x", pady=1)
            tk.Label(row_fr, text=val or "—", font=FONTS["body"],
                     bg=row_fr["bg"], fg=COLORS["text_primary"],
                     anchor="w").pack(side="left", padx=12, pady=4)
            tk.Label(row_fr, text=lbl, font=FONTS["body_bold"],
                     bg=row_fr["bg"], fg=COLORS["text_secondary"],
                     anchor="e").pack(side="right", padx=12, pady=4)

        # Stats
        stats = db.fetch_one("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN order_type='EM' THEN 1 ELSE 0 END) as em,
                   SUM(downtime_minutes) as total_down
            FROM work_orders WHERE equipment_id=?
        """, (eq_id,))

        tk.Frame(inner, bg=COLORS["border"], height=1).pack(fill="x", pady=8)
        stat_row = tk.Frame(inner, bg=COLORS["bg_card"])
        stat_row.pack(fill="x")
        for val, lbl, color in [
            (stats["total"] or 0, "کل دستور کار", COLORS["blue"]),
            (stats["em"] or 0, "توقف اضطراری", COLORS["red"]),
            (f"{(stats['total_down'] or 0) // 60}h", "مجموع توقف", COLORS["yellow"]),
        ]:
            sf = tk.Frame(stat_row, bg=COLORS["bg_card"])
            sf.pack(side="right", fill="x", expand=True, padx=4)
            tk.Label(sf, text=str(val), font=FONTS["heading"],
                     bg=COLORS["bg_card"], fg=color).pack()
            tk.Label(sf, text=lbl, font=FONTS["small"],
                     bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack()

        if eq["notes"]:
            tk.Frame(inner, bg=COLORS["border"], height=1).pack(fill="x", pady=8)
            tk.Label(inner, text=eq["notes"], font=FONTS["body"],
                     bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                     wraplength=340, justify="right").pack(padx=8, pady=4, anchor="e")

        self._current_selection = ("equipment", eq_id)

    def _edit_selected(self):
        sel = self.eq_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("cat_"):
            self._edit_category_dialog(int(iid[4:]))
        elif iid.startswith("eq_"):
            self._edit_equipment_dialog(int(iid[3:]))

    def _delete_selected(self):
        sel = self.eq_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("cat_"):
            cat_id = int(iid[4:])
            count = db.fetch_one("SELECT COUNT(*) as c FROM equipment WHERE category_id=?", (cat_id,))
            if count["c"] > 0:
                messagebox.showerror("خطا", f"این دسته {count['c']} تجهیز دارد. ابتدا تجهیزات را حذف کنید.")
                return
            if messagebox.askyesno("حذف دسته", "آیا این دسته‌بندی حذف شود؟"):
                def work():
                    try:
                        equip_sync.delete_category(cat_id)
                        def ok():
                            ToastNotification(self, "دسته‌بندی حذف شد", "info")
                            self.refresh()
                            self._show_placeholder()
                        self.after(0, ok)
                    except Exception as e:
                        err = str(e)
                        self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))
                threading.Thread(target=work, daemon=True).start()
        elif iid.startswith("eq_"):
            eq_id = int(iid[3:])
            if messagebox.askyesno("حذف تجهیز", "آیا این تجهیز حذف شود؟\n(سابقه دستور کارها حفظ می‌شود)", icon="warning"):
                def work():
                    try:
                        equip_sync.delete_equipment(eq_id)
                        def ok():
                            ToastNotification(self, "تجهیز حذف شد", "info")
                            self.refresh()
                            self._show_placeholder()
                        self.after(0, ok)
                    except Exception as e:
                        err = str(e)
                        self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))
                threading.Thread(target=work, daemon=True).start()

    def _add_category(self):
        self._category_dialog(None)

    def _add_equipment(self):
        sel = self.eq_tree.selection()
        cat_id = None
        if sel and sel[0].startswith("cat_"):
            cat_id = int(sel[0][4:])
        self._equipment_dialog(None, cat_id)

    def _category_dialog(self, cat_id):
        existing = db.fetch_one("SELECT * FROM equipment_categories WHERE id=?", (cat_id,)) if cat_id else None
        dlg = tk.Toplevel(self)
        dlg.title("ویرایش دسته‌بندی" if existing else "دسته‌بندی جدید")
        dlg.configure(bg=COLORS["bg_dark"])
        dlg.geometry("400x240")
        dlg.grab_set()

        card = tk.Frame(dlg, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        f_name = FormField(card, "نام دسته‌بندی", required=True)
        f_name.pack(fill="x", padx=16, pady=8)
        if existing:
            f_name.set(existing["name"])

        icons = ["⚙️", "🔧", "💧", "🌀", "⚡", "🏭", "🛢️", "💨", "🛡️", "❄️", "🔩", "⛽"]
        f_icon_var = tk.StringVar(value=existing["icon"] if existing else "⚙️")
        icon_row = tk.Frame(card, bg=COLORS["bg_card"])
        icon_row.pack(fill="x", padx=16, pady=4)
        tk.Label(icon_row, text="آیکون:", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="right")
        for ic in icons:
            def mk(i=ic):
                return lambda: f_icon_var.set(i)
            tk.Button(icon_row, text=ic, font=("Segoe UI Emoji", 14),
                      bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                      relief="flat", cursor="hand2", command=mk()).pack(side="left", padx=2)

        def _save():
            name = f_name.get().strip()
            if not name:
                messagebox.showerror("خطا", "نام دسته الزامی است")
                return
            icon = f_icon_var.get()

            def work():
                try:
                    if cat_id:
                        equip_sync.update_category(cat_id, {"name": name, "icon": icon})
                    else:
                        equip_sync.create_category(name, icon)
                    def ok():
                        dlg.destroy()
                        ToastNotification(self, "ذخیره شد", "success")
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

    def _edit_category_dialog(self, cat_id):
        self._category_dialog(cat_id)

    def _equipment_dialog(self, eq_id, default_cat_id=None):
        existing = db.fetch_one("SELECT * FROM equipment WHERE id=?", (eq_id,)) if eq_id else None
        cats = db.fetch_all("SELECT * FROM equipment_categories ORDER BY name")
        if not cats:
            messagebox.showwarning("دسته‌بندی لازم است",
                "برای افزودن تجهیز، ابتدا با دکمه «+ دسته» یک دسته‌بندی بسازید.")
            return
        cat_map = {f"{c['icon']} {c['name']}": c["id"] for c in cats}
        cat_names = list(cat_map.keys())

        dlg = tk.Toplevel(self)
        dlg.title("ویرایش تجهیز" if existing else "تجهیز جدید")
        dlg.configure(bg=COLORS["bg_dark"])
        dlg.geometry("560x560")
        dlg.grab_set()

        canvas = tk.Canvas(dlg, bg=COLORS["bg_dark"], highlightthickness=0)
        sb = tk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=COLORS["bg_dark"])
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        card = tk.Frame(inner, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="x", padx=16, pady=16)

        flds = {}

        # ── دسته‌بندی: تمام‌عرض (خط اول فرم) ──
        f_cat = FormField(card, "دسته‌بندی", "combobox", cat_names, required=True)
        f_cat.pack(fill="x", padx=16, pady=(8, 4))
        if existing and existing.get("category_id"):
            cat = db.fetch_one("SELECT * FROM equipment_categories WHERE id=?",
                               (existing["category_id"],))
            if cat:
                f_cat.set(f"{cat['icon']} {cat['name']}")
        elif default_cat_id:
            cat = db.fetch_one("SELECT * FROM equipment_categories WHERE id=?",
                               (default_cat_id,))
            if cat:
                f_cat.set(f"{cat['icon']} {cat['name']}")
        flds["category"] = f_cat

        # ── بقیه فیلدها: دو ستونه با شمارنده‌ی مستقل (فیکس باگ نام تجهیز) ──
        rest_defs = [
            ("نام تجهیز", "name", "entry", None),
            ("کد تجهیز", "code", "entry", None),
            ("موقعیت", "location", "entry", None),
            ("برند", "brand", "entry", None),
            ("مدل", "model", "entry", None),
            ("شماره سریال", "serial_number", "entry", None),
            ("تاریخ نصب", "install_date", "entry", None),
            ("وضعیت", "status", "combobox", ["فعال", "غیرفعال", "در تعمیر"]),
        ]
        row_fr = None
        for i, (lbl, key, ftype, opts) in enumerate(rest_defs):
            if i % 2 == 0:                      # ستون اولِ هر ردیف → فریم جدید
                row_fr = tk.Frame(card, bg=COLORS["bg_card"])
                row_fr.pack(fill="x", padx=16, pady=2)
            f = FormField(row_fr, lbl, ftype, opts, required=(key == "name"))
            f.pack(side="right" if i % 2 == 0 else "left",
                   fill="x", expand=True,
                   padx=(0, 4) if i % 2 == 0 else (4, 0))
            if existing and existing.get(key):
                f.set(str(existing[key]))
            elif key == "status":
                f.set("فعال")
            flds[key] = f

        f_notes = FormField(card, "یادداشت", "text")
        f_notes.pack(fill="x", padx=16, pady=4)
        if existing and existing.get("notes"):
            f_notes.set(existing["notes"])

        def _save():
            cat_str = flds["category"].get()
            if cat_str not in cat_map:
                messagebox.showerror("خطا", "لطفاً دسته‌بندی را انتخاب کنید")
                return
            name = flds["name"].get().strip()
            if not name:
                messagebox.showerror("خطا", "نام تجهیز الزامی است")
                return
            cat_id_val = cat_map[cat_str]
            cat_row = db.fetch_one("SELECT name, icon FROM equipment_categories WHERE id=?",
                                   (cat_id_val,))
            data = {
                "category_name": cat_row["name"] if cat_row else None,
                "category_icon": cat_row["icon"] if cat_row else None,
                "name": name, "code": flds["code"].get(),
                "location": flds["location"].get(),
                "brand": flds["brand"].get(), "model": flds["model"].get(),
                "serial_number": flds["serial_number"].get(),
                "install_date": flds["install_date"].get(),
                "status": flds["status"].get(), "notes": f_notes.get(),
            }

            def work():
                try:
                    if eq_id:
                        equip_sync.update_equipment(eq_id, data)
                    else:
                        equip_sync.create_equipment(data)
                    def ok():
                        dlg.destroy()
                        ToastNotification(self, "تجهیز ذخیره شد", "success")
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
    def _edit_equipment_dialog(self, eq_id):
        self._equipment_dialog(eq_id)

    def _expand_all(self):
        for item in self.eq_tree.get_children():
            self.eq_tree.item(item, open=True)

    def _collapse_all(self):
        for item in self.eq_tree.get_children():
            self.eq_tree.item(item, open=False)

    def _show_history(self):
        sel = self.eq_tree.selection()
        if not sel or not sel[0].startswith("eq_"):
            return
        eq_id = int(sel[0][3:])
        eq = db.fetch_one("SELECT name FROM equipment WHERE id=?", (eq_id,))
        rows = db.fetch_all("""
            SELECT order_number, order_type, work_date, operator,
                   description, downtime_minutes, status
            FROM work_orders WHERE equipment_id=? ORDER BY id DESC
        """, (eq_id,))

        dlg = tk.Toplevel(self)
        dlg.title(f"سابقه تعمیرات — {eq['name'] if eq else ''}")
        dlg.configure(bg=COLORS["bg_dark"])
        dlg.geometry("720x480")
        dlg.grab_set()

        tk.Label(dlg, text=f"📋  سابقه تعمیرات:  {eq['name'] if eq else ''}",
                 font=FONTS["heading"], bg=COLORS["bg_dark"],
                 fg=COLORS["accent"]).pack(padx=16, pady=12, anchor="e")

        cols = ("شماره", "نوع", "تاریخ", "اپراتور", "توقف(دق)", "وضعیت")
        tree = StyledTreeview(dlg, cols)
        tree.pack(fill="both", expand=True, padx=16, pady=8)
        for r in rows:
            tree.insert((r["order_number"],
                         "🔴 EM" if r["order_type"] == "EM" else "🔵 PM",
                         r["work_date"], r["operator"],
                         r["downtime_minutes"], r["status"]))

        tk.Label(dlg, text=f"مجموع: {len(rows)} دستور کار", font=FONTS["small"],
                 bg=COLORS["bg_dark"], fg=COLORS["text_muted"]).pack(pady=4)
