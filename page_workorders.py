"""
CMMS Work Order Pages — نسخهٔ اشتراکی (سرور-محور)
دستور کارها روی «سرور» ذخیره می‌شوند تا همهٔ سیستم‌ها یک لیست مشترک ببینند.
ویرایش/حذف/بستن فقط توسط سازنده یا مدیر سیستم (چک سمت کلاینت + سرور).
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
import api_client_ext as apx
import database as db
import api_client
import wo_sync
from styles import COLORS, FONTS, OPERATOR_COLORS, PRIORITY_COLORS, STATUS_COLORS
from widgets import SectionTitle, StyledTreeview, IconButton, FormField, ToastNotification


def _validate_date(text):
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _current_user():
    u = api_client.current_user
    if not isinstance(u, dict) or not u.get("username"):
        try:
            u = api_client.whoami()
            if isinstance(u, dict):
                api_client.current_user = u
        except Exception:
            u = {}
    return u if isinstance(u, dict) else {}


def _fetch_user_names():
    try:
        users = api_client.get_users() or []
    except Exception:
        return []
    names = []
    for u in users:
        nm = (u.get("full_name") or u.get("username") or "").strip()
        if nm:
            names.append(nm)
    return sorted(set(names))

def _current_username():
    return (_current_user().get("username") or "").strip()
def refresh(self):
        """هر بار که این صفحه باز می‌شود، لیست تکنسین‌ها از سرور تازه می‌شود —
        کاربری که همین الان در «مدیریت کاربران» اضافه شده، بدون ری‌استارت دیده می‌شود"""
        if not getattr(self, "_is_admin", False):
            return
        self._load_tech_names()
        try:
            self._update_num()
        except Exception:
            pass

def _fetch_tech_users():
    """(نام نمایشی، username) — برای تطبیق دستور کار با کاربر سیستم"""
    try:
        users = api_client.get_users() or []
    except Exception:
        return []
    out = []
    for u in users:
        nm = (u.get("full_name") or u.get("username") or "").strip()
        un = (u.get("username") or "").strip()
        if nm and un:
            out.append((nm, un))
    return sorted(set(out))
# ═══════════════════ ثبت دستور کار جدید ═══════════════════

class NewWorkOrderPage(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self._is_admin = (_current_user().get("role") == "admin")
        wo_sync.ensure_local()
        if not self._is_admin:
            self._build_no_access()
            return
        self._tech_uname = {}
        self._build_ui()
        wo_sync.pull_async(callback=lambda ok: self.after(0, self._update_num))

    def _build_no_access(self):
        box = tk.Frame(self, bg=COLORS["bg_card"],
                       highlightbackground=COLORS["border"], highlightthickness=1)
        box.pack(expand=True, padx=40, pady=40)
        tk.Label(box, text="🔒", font=("Segoe UI Emoji", 42),
                 bg=COLORS["bg_card"]).pack(pady=(24, 8))
        tk.Label(box, text="ثبت دستور کار فقط توسط «مدیر سیستم» انجام می‌شود",
                 font=FONTS["heading"], bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"]).pack(pady=4)
        tk.Label(box, text="دستور کارهایی که مدیر برای شما ثبت کند در «لیست دستور کارها»\n"
                          "نمایش داده می‌شوند و می‌توانید برای آن‌ها گزارش کار بنویسید.",
                 font=FONTS["body"], bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], justify="center").pack(padx=24, pady=(4, 24))

    def _build_ui(self):
        outer = tk.Frame(self, bg=COLORS["bg_dark"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=COLORS["bg_dark"], highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                           bg=COLORS["bg_dark"], troughcolor=COLORS["bg_card"])
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=COLORS["bg_dark"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        self._inner = inner

        hdr = tk.Frame(inner, bg=COLORS["bg_header"])
        hdr.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(hdr, text="ثبت دستور کار جدید (روی سرور — همه می‌بینند)", font=FONTS["title"],
                 bg=COLORS["bg_header"], fg=COLORS["text_primary"]).pack(side="right", pady=14)

        self.order_type = tk.StringVar(value="EM")
        tab_fr = tk.Frame(inner, bg=COLORS["bg_dark"])
        tab_fr.pack(fill="x", padx=20, pady=(4, 0))
        self._num_lbl = None
        self._tabs = {}
        for otype, lbl, icon, color in [
            ("EM", "توقف اضطراری (EM)", "🚨", COLORS["red"]),
            ("PM", "نگهداری پیشگیرانه (PM)", "🔧", COLORS["blue"]),
        ]:
            btn = tk.Label(tab_fr, text=f"{icon}  {lbl}", font=FONTS["subhead"],
                           padx=24, pady=10, cursor="hand2", relief="flat")
            btn.pack(side="right", padx=(0, 4))
            self._tabs[otype] = (btn, color)
            btn.bind("<Button-1>", lambda e, t=otype: self._switch_type(t))
        self._switch_type("EM")

        card = tk.Frame(inner, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="x", padx=20, pady=10)

        cols_fr = tk.Frame(card, bg=COLORS["bg_card"])
        cols_fr.pack(fill="x", padx=20, pady=16)
        left  = tk.Frame(cols_fr, bg=COLORS["bg_card"])
        right = tk.Frame(cols_fr, bg=COLORS["bg_card"])
        right.pack(side="right", fill="x", expand=True)
        left.pack(side="right", fill="x", expand=True, padx=(0, 12))

        equip_list = db.fetch_all("SELECT id,name,code FROM equipment WHERE status='فعال' ORDER BY name")
        self._equip_map = {f"{e['name']} ({e['code'] or ''})": e["id"] for e in equip_list}
        equip_names = list(self._equip_map.keys())

        self.f_equip    = FormField(left, "تجهیز", "combobox", equip_names, required=True)
        self.f_operator = FormField(left, "اپراتور", "combobox", ["مکانیک","برق","تاسیسات"], required=True)
        self.f_date     = FormField(left, "تاریخ کار", required=True)
        self.f_priority = FormField(left, "اولویت", "combobox", ["بحرانی","بالا","متوسط","پایین"])
        for f in [self.f_equip, self.f_operator, self.f_date, self.f_priority]:
            f.pack(fill="x", pady=5)
        self.f_date.set(date.today().isoformat())
        self.f_priority.set("متوسط")

        # نام تکنسین: هم نوشتنی، هم قابل انتخاب از کاربرهای ثبت‌شده
        tech_fr = tk.Frame(right, bg=COLORS["bg_card"])
        tech_fr.pack(fill="x", pady=5)
        tk.Label(tech_fr, text="نام تکنسین", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                 anchor="e").pack(fill="x")
        self.f_tech = ttk.Combobox(tech_fr, font=FONTS["body"], justify="center",
                                   state="normal")
        self.f_tech.pack(fill="x", ipady=3)
        self._tech_names = []
        self._load_tech_names()

        time_fr = tk.Frame(right, bg=COLORS["bg_card"])
        time_fr.pack(fill="x", pady=5)
        self.f_end   = FormField(time_fr, "ساعت پایان")
        self.f_start = FormField(time_fr, "ساعت شروع")
        self.f_end.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.f_start.pack(side="left", fill="x", expand=True)
        self.f_start.set("08:00"); self.f_end.set("09:00")

        self.f_downtime = FormField(right, "مدت توقف (دقیقه)")
        self.f_status   = FormField(right, "وضعیت", "combobox", ["باز","در حال انجام","بسته","معلق"])
        for f in [self.f_downtime, self.f_status]:
            f.pack(fill="x", pady=5)
        self.f_downtime.set("0"); self.f_status.set("باز")

        desc_fr = tk.Frame(card, bg=COLORS["bg_card"])
        desc_fr.pack(fill="x", padx=20, pady=(0, 12))
        self.f_desc   = FormField(desc_fr, "شرح خرابی / کار انجام شده ✱", "text")
        self.f_action = FormField(desc_fr, "اقدام انجام شده", "text")
        self.f_cause  = FormField(desc_fr, "علت ریشه‌ای", "text")
        self.f_parts  = FormField(desc_fr, "قطعات مصرفی")
        for f in [self.f_desc, self.f_action, self.f_cause, self.f_parts]:
            f.pack(fill="x", pady=4)

        btn_row = tk.Frame(inner, bg=COLORS["bg_dark"])
        btn_row.pack(fill="x", padx=20, pady=12)
        IconButton(btn_row, "ثبت دستور کار", "💾", self._save,
                   color=COLORS["accent"]).pack(side="right")
        IconButton(btn_row, "پاک کردن فرم", "🗑️", self._clear,
                   color=COLORS["bg_card"]).pack(side="right", padx=(0, 8))
        self._num_lbl = tk.Label(btn_row, text="", font=FONTS["mono"],
                                 bg=COLORS["bg_dark"], fg=COLORS["text_muted"])
        self._num_lbl.pack(side="left")
        self._update_num()

    def _load_tech_names(self):
        def work():
            pairs = _fetch_tech_users()
            self.after(0, lambda p=pairs: self._set_tech_names(p))
        threading.Thread(target=work, daemon=True).start()

    def _set_tech_names(self, pairs):
        self._tech_uname = {nm: un for nm, un in pairs}
        self._tech_names = [nm for nm, _ in pairs]
        try:
            self.f_tech.configure(values=self._tech_names)
        except Exception:
            pass
    def _switch_type(self, otype):
        self.order_type.set(otype)
        for t, (btn, color) in self._tabs.items():
            if t == otype:
                btn.configure(bg=color, fg=COLORS["bg_dark"])
            else:
                btn.configure(bg=COLORS["bg_card"], fg=COLORS["text_secondary"])
        self._update_num()

    def _update_num(self):
        if not self._num_lbl:
            return
        num = db.generate_order_number(self.order_type.get())
        self._num_lbl.configure(text=f"شماره بعدی: {num}")

    def _save(self):
        otype    = self.order_type.get()
        eq_label = self.f_equip.get()
        operator = self.f_operator.get()
        desc     = self.f_desc.get().strip()
        wdate    = self.f_date.get().strip()
        tech = self.f_tech.get().strip()
        if not tech:
            messagebox.showerror("خطا", "نام تکنسین را انتخاب یا وارد کنید"); return
        tech_un = self._tech_uname.get(tech, "")
        if not tech_un:
            if not messagebox.askyesno("تکنسین ناشناس",
                    f"«{tech}» در بین کاربران سیستم نیست.\n"
                    "این دستور کار برای هیچ کاربری قابل مشاهده و گزارش‌دهی نخواهد بود.\n\nادامه می‌دهید؟"):
                return
        if not eq_label or eq_label not in self._equip_map:
            messagebox.showerror("خطا", "لطفاً تجهیز را انتخاب کنید"); return
        if not operator:
            messagebox.showerror("خطا", "لطفاً اپراتور را انتخاب کنید"); return
        if not desc:
            messagebox.showerror("خطا", "شرح کار الزامی است"); return
        if not wdate:
            messagebox.showerror("خطا", "تاریخ کار الزامی است"); return
        if not _validate_date(wdate):
            messagebox.showerror("خطا", "فرمت تاریخ باید دقیقاً YYYY-MM-DD باشد (مثلاً 2026-08-22).")
            return
        tech_un = self._tech_uname.get(tech, "")
        if not tech_un:
            if not messagebox.askyesno("تکنسین ناشناس",
                    f"«{tech}» در بین کاربران سیستم نیست.\n"
                    "این دستور کار برای هیچ کاربری قابل مشاهده و گزارش‌دهی نخواهد بود.\n\nادامه می‌دهید؟"):
                return
        if not tech:
            messagebox.showerror("خطا", "نام تکنسین را انتخاب یا وارد کنید"); return

        try: down = int(self.f_downtime.get() or 0)
        except ValueError: down = 0

        eq_id = self._equip_map[eq_label]
        eq_row = db.fetch_one("SELECT name, location FROM equipment WHERE id=?", (eq_id,))
        creator = _current_user().get("username") or "unknown"

        data = {
            "order_type": otype,
            "equipment_id": eq_id,
            "eq_name": (eq_row["name"] if eq_row else eq_label),
            "location": ((eq_row["location"] or "") if eq_row else ""),
            "operator": operator,
            "description": desc,
            "work_date": wdate,
            "start_time": self.f_start.get(),
            "end_time": self.f_end.get(),
            "downtime_minutes": down,
            "priority": self.f_priority.get(),
            "status": self.f_status.get(),
            "root_cause": self.f_cause.get(),
            "action_taken": self.f_action.get(),
            "parts_used": self.f_parts.get(),
            "technician_name": tech,
                        "technician_username": tech_un,
        }

        def work():
            try:
                res = wo_sync.create(data)
                onum = (res or {}).get("order_number", "")
                self.after(0, lambda: self._saved_ok(onum))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._save_failed(err, data, creator))

        threading.Thread(target=work, daemon=True).start()

    def _saved_ok(self, onum):
        ToastNotification(self, f"دستور کار {onum} روی سرور ثبت شد ✓ (همه می‌بینند)", "success")
        self._clear()
        self.app.refresh_dashboard()

    def _save_failed(self, err, data, creator):
        if not messagebox.askyesno("خطای اتصال به سرور",
                "ارتباط با سرور برقرار نشد:\n" + err + "\n\n"
                "دستور کار به‌صورت «محلی» ذخیره شود؟\n"
                "(با اولین اتصال موفق، خودکار به سرور منتقل می‌شود)"):
            return
        onum = db.generate_order_number(data["order_type"])
        db.execute("""
            INSERT INTO work_orders
            (order_number,order_type,equipment_id,eq_name,location,operator,
             description,work_date,start_time,end_time,downtime_minutes,
             priority,status,root_cause,action_taken,parts_used,
             technician_name,created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (onum, data["order_type"], data["equipment_id"], data["eq_name"],
             data["location"], data["operator"], data["description"],
             data["work_date"], data["start_time"], data["end_time"],
             data["downtime_minutes"], data["priority"], data["status"],
             data["root_cause"], data["action_taken"], data["parts_used"],
             data["technician_name"], creator))
        ToastNotification(self, f"دستور کار {onum} محلی ذخیره شد (آفلاین)", "info")
        self._clear()
        self.app.refresh_dashboard()

    def _clear(self):
        self.f_equip.set(""); self.f_operator.set(""); self.f_tech.set("")
        self.f_desc.set(""); self.f_action.set(""); self.f_cause.set(""); self.f_parts.set("")
        self.f_downtime.set("0"); self.f_date.set(date.today().isoformat())
        self.f_start.set("08:00"); self.f_end.set("09:00")
        self.f_priority.set("متوسط"); self.f_status.set("باز")
        self._update_num()


# ═══════════════════ لیست دستور کارها ═══════════════════

# ═══════════════════ لیست دستور کارها ═══════════════════

class WorkOrderListPage(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self._all_rows = []
        self._user_map = {}
        self._tech_names = []
        self._perf_rows = []
        self._is_admin = (_current_user().get("role") == "admin")
        self._me = _current_username()
        wo_sync.ensure_local()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        toolbar = tk.Frame(self, bg=COLORS["bg_header"])
        toolbar.pack(fill="x", padx=20, pady=(16, 8))
        title = "لیست دستور کارها (مدیریت)" if self._is_admin else "دستور کارهای من"
        tk.Label(toolbar, text=title, font=FONTS["title"],
                 bg=COLORS["bg_header"], fg=COLORS["text_primary"]).pack(side="right", pady=12)
        IconButton(toolbar, "بروزرسانی", "🔄", self._manual_refresh,
                  color=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(side="right", padx=(0, 10))

        filter_fr = tk.Frame(toolbar, bg=COLORS["bg_header"])
        filter_fr.pack(side="left", pady=8)
        for lbl, attr, vals, w in [
            ("نوع:", "filter_type", ["همه","EM","PM"], 6),
            ("اپراتور:", "filter_op", ["همه","مکانیک","برق","تاسیسات"], 10),
            ("وضعیت:", "filter_status", ["همه","باز","در حال انجام","بسته","معلق"], 12),
            ("گزارش:", "filter_report", ["همه","ارسال شده","تأیید شده","بدون گزارش"], 10),
        ]:
            tk.Label(filter_fr, text=lbl, font=FONTS["small"],
                     bg=COLORS["bg_header"], fg=COLORS["text_secondary"]).pack(side="right", padx=(8,2))
            cb = ttk.Combobox(filter_fr, values=vals, width=w, state="readonly", font=FONTS["small"])
            cb.set(vals[0])
            cb.pack(side="right", padx=2)
            cb.bind("<<ComboboxSelected>>", lambda e: self._apply_filters())
            setattr(self, attr, cb)

        sf = tk.Frame(toolbar, bg=COLORS["bg_input"],
                      highlightbackground=COLORS["border"], highlightthickness=1)
        sf.pack(side="left", padx=(12,0))
        tk.Label(sf, text="🔍", bg=COLORS["bg_input"], fg=COLORS["text_muted"]).pack(side="left", padx=4)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._apply_filters())
        tk.Entry(sf, textvariable=self.search_var, font=FONTS["body"],
                 bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                 insertbackground=COLORS["accent"], relief="flat", bd=0, width=22).pack(
            side="left", ipady=5, padx=4)

        badge_row = tk.Frame(self, bg=COLORS["bg_dark"])
        badge_row.pack(fill="x", padx=20, pady=(0,6))
        self.badge_total = tk.Label(badge_row, text="کل: 0", font=FONTS["small"],
                                    bg=COLORS["blue_dim"], fg=COLORS["blue"], padx=10, pady=4)
        self.badge_em    = tk.Label(badge_row, text="EM: 0", font=FONTS["small"],
                                    bg=COLORS["red_dim"], fg=COLORS["red"], padx=10, pady=4)
        self.badge_pm    = tk.Label(badge_row, text="PM: 0", font=FONTS["small"],
                                    bg=COLORS["blue_dim"], fg=COLORS["blue"], padx=10, pady=4)
        self.badge_open  = tk.Label(badge_row, text="باز: 0", font=FONTS["small"],
                                    bg=COLORS["yellow_dim"], fg=COLORS["yellow"], padx=10, pady=4)
        for b in [self.badge_total, self.badge_em, self.badge_pm, self.badge_open]:
            b.pack(side="right", padx=4)
        if self._is_admin:
            self.badge_pending = tk.Label(badge_row, text="📨 بررسی: 0", font=FONTS["small"],
                                          bg=COLORS["yellow_dim"], fg=COLORS["yellow"], padx=10, pady=4)
            self.badge_pending.pack(side="right", padx=4)

        cols = ("شماره","نوع","تجهیز","موقعیت","اپراتور","تکنسین","تاریخ",
                "توقف(دق)","اولویت","وضعیت","گزارش","سازنده")
        self.tree_frame = StyledTreeview(self, columns=cols)
        self.tree_frame.pack(fill="both", expand=True, padx=20, pady=4)
        for col, w in zip(cols, [115,55,165,90,75,95,85,70,65,85,100,110]):
            self.tree_frame.tree.column(col, width=w, minwidth=w)
        self.tree_frame.tree.tag_configure("rep_wait", foreground=COLORS["yellow"])
        self.tree_frame.tree.tag_configure("rep_ok", foreground=COLORS["green"])
        self.tree_frame.tree.bind("<Double-1>", self._on_double_click)

        btn_row = tk.Frame(self, bg=COLORS["bg_dark"])
        btn_row.pack(fill="x", padx=20, pady=10)
        if self._is_admin:
            # مدیر: فقط «مشاهده» گزارش — ثبت گزارش کارِ تکنسین است
            IconButton(btn_row, "مشاهده گزارش", "👁️", self._view_selected_report,
                       color=COLORS["purple"]).pack(side="right", padx=4)
            IconButton(btn_row, "ویرایش",     "✏️", self._edit_selected,   color=COLORS["blue"]).pack(side="right", padx=4)
            IconButton(btn_row, "بستن دستور", "✓",  self._close_selected,  color=COLORS["green"]).pack(side="right", padx=4)
            IconButton(btn_row, "حذف",        "🗑️", self._delete_selected, color=COLORS["red"]).pack(side="right", padx=4)
        else:
            IconButton(btn_row, "ثبت گزارش کار", "📨", self._report_selected,
                       color=COLORS["blue"]).pack(side="right", padx=4)
        IconButton(btn_row, "کارنامه" if self._is_admin else "کارنامه من", "📊",
                   self._show_performance, color=COLORS["purple"]).pack(side="right", padx=4)
        IconButton(btn_row, "خروجی اکسل", "📥", self._export_excel, color=COLORS["bg_card"]).pack(side="left", padx=4)
        if self._is_admin:
            hint = "🔒 مدیر فقط گزارش را مشاهده و امتیازدهی می‌کند | دابل‌کلیک روی ردیفِ دارای گزارش → مشاهده"
        else:
            hint = "🔒 دستور کارهایی که مدیر برای شما ثبت کرده را می‌بینید — با «ثبت گزارش کار» نتیجه را برای مدیر بفرستید"
        tk.Label(btn_row, text=hint, font=FONTS["small"], bg=COLORS["bg_dark"],
                 fg=COLORS["text_muted"]).pack(side="left", padx=10)

    def refresh(self):
        self._reload_local()
        self._load_users()
        wo_sync.pull_async(callback=lambda ok: self.after(0, lambda: self._after_pull(ok)))

    
    def _after_pull(self, ok):
        if not ok:
            ToastNotification(self, "⚠️ همگام‌سازی با سرور نشد — داده‌های محلی نشان داده می‌شود", "error")
        self._reload_local()
        # ⚠️ قبلاً اینجا بی‌قیدوشرط on_wo_list_viewed() صدا زده می‌شد؛ اما این متد
        # از sync پس‌زمینه هم اجرا می‌شود (وقتی کاربر روی صفحه‌ی دیگری است)
        # → همه‌چیز «دیده‌شده» می‌شد و بج بعد از ~۱ ثانیه صفر می‌شد!
        if self._is_user_viewing():
            try:
                self.app.on_wo_list_viewed()
            except Exception:
                pass

    def _manual_refresh(self):
        ToastNotification(self, "در حال دریافت آخرین دستور کارها…", "info")

        def done(ok):
            def _ui():
                if ok:
                    ToastNotification(self, "بروزرسانی شد ✓", "success")
                else:
                    ToastNotification(self, "⚠️ اتصال به سرور برقرار نشد", "error")
                self._reload_local()
                if self._is_user_viewing():
                    try:
                        self.app.on_wo_list_viewed()
                    except Exception:
                        pass
            self.after(0, _ui)

        wo_sync.pull_async(callback=done)

    def _is_user_viewing(self):
        """آیا کاربر همین الان این صفحه را روی نمایشگر می‌بیند؟
        (وقتی sync از پس‌زمینه اجرا می‌شود، این صفحه مخفی است)"""
        try:
            if getattr(self.app, "_current_page", None) is not self:
                return False
        except Exception:
            pass
        try:
            return bool(self.winfo_ismapped())
        except Exception:
            return False
    def _reload_local(self):
        if self._is_admin or not self._me:
            where, args = "", ()
        else:
            where = " WHERE (wo.technician_username=? OR wo.created_by=?)"
            args = (self._me, self._me)
        self._all_rows = db.fetch_all(f"""
            SELECT wo.id, wo.order_number, wo.order_type,
                   COALESCE(wo.eq_name, e.name) as eq_name,
                   COALESCE(wo.location, e.location) as location,
                   wo.operator, wo.technician_name, wo.technician_username,
                   wo.work_date, wo.downtime_minutes, wo.priority, wo.status,
                   wo.created_by, wo.report_status, wo.report_text,
                   wo.report_rating, wo.report_submitted_at, wo.report_comment,
                   wo.description
            FROM work_orders wo LEFT JOIN equipment e ON wo.equipment_id = e.id
            {where}
            ORDER BY wo.id DESC""", args)
        self._apply_filters()
    def _load_users(self):
        def work():
            umap, names = {}, []
            try:
                users = api_client.get_users() or []
                for u in users:
                    un = (u.get("username") or "").strip()
                    fn = (u.get("full_name") or un).strip()
                    if un:
                        umap[un] = fn or un
                    if fn:
                        names.append(fn)
            except Exception:
                pass
            def apply():
                self._user_map = umap
                self._tech_names = sorted(set(names))
                self._apply_filters()
            self.after(0, apply)
        threading.Thread(target=work, daemon=True).start()

    def _creator_display(self, row):
        raw = (row["created_by"] or "").strip() if row else ""
        if not raw:
            return "-"
        return self._user_map.get(raw) or raw

    def _apply_filters(self):
        ftype   = self.filter_type.get()
        fop     = self.filter_op.get()
        fstatus = self.filter_status.get()
        frep    = self.filter_report.get()
        search  = self.search_var.get().strip().lower()

        filtered = []
        for r in self._all_rows:
            if ftype   != "همه" and r["order_type"] != ftype:   continue
            if fop     != "همه" and r["operator"]   != fop:     continue
            if fstatus != "همه" and r["status"]      != fstatus: continue
            rs = r.get("report_status") or ""
            if frep == "ارسال شده" and rs != "ارسال شده":  continue
            if frep == "تأیید شده" and rs != "تأیید شده":  continue
            if frep == "بدون گزارش" and rs:                 continue
            if search:
                s = f"{r['order_number']} {r['eq_name']} {r['technician_name']} {r['operator']}".lower()
                if search not in s: continue
            filtered.append(r)

        self.tree_frame.clear()
        em_cnt = pm_cnt = open_cnt = 0
        for r in filtered:
            if r["order_type"]=="EM": em_cnt += 1
            else: pm_cnt += 1
            if r["status"]=="باز": open_cnt += 1
            rs = r.get("report_status") or ""
            if rs == "تأیید شده":
                rep = f"⭐ {r['report_rating']:g}" if r.get("report_rating") is not None else "✅ تأیید"
            elif rs == "ارسال شده":
                rep = "📨 ارسال شده"
            else:
                rep = "-"
            tags = [f"op_{r['operator']}"] if r["operator"] in OPERATOR_COLORS else []
            if rs == "ارسال شده": tags.append("rep_wait")
            elif rs == "تأیید شده": tags.append("rep_ok")
            self.tree_frame.insert(
                (r["order_number"],
                 "🔴 EM" if r["order_type"]=="EM" else "🔵 PM",
                 r["eq_name"] or "-", r["location"] or "-",
                 r["operator"], r["technician_name"] or "-",
                 r["work_date"], r["downtime_minutes"],
                 r["priority"], r["status"], rep,
                 self._creator_display(r)),
                tags=tuple(tags), iid=str(r["id"]))

        self.badge_total.configure(text=f"کل: {len(filtered)}")
        self.badge_em.configure(text=f"EM: {em_cnt}")
        self.badge_pm.configure(text=f"PM: {pm_cnt}")
        self.badge_open.configure(text=f"باز: {open_cnt}")
        if self._is_admin:
            pending = sum(1 for r in self._all_rows
                          if (r.get("report_status") or "") == "ارسال شده")
            self.badge_pending.configure(text=f"📨 بررسی: {pending}")

    def _get_selected_id(self):
        sel = self.tree_frame.tree.selection()
        if not sel:
            messagebox.showinfo("انتخاب", "لطفاً یک ردیف انتخاب کنید"); return None
        return int(sel[0])

    def _row_by_id(self, wid):
        return next((r for r in self._all_rows if str(r["id"]) == str(wid)), None)

    def _is_assigned_to_me(self, row):
        return bool(self._me) and (row.get("technician_username") or "").strip() == self._me

    def _can_modify(self, wo_id):
        if self._is_admin:
            return True
        row = self._row_by_id(wo_id)
        if not row:
            return False
        creator = (row["created_by"] or "").strip()
        return bool(creator) and creator == self._me

    def _deny_modify(self):
        ToastNotification(self, "⛔ فقط سازندهٔ این دستور کار یا مدیر سیستم اجازهٔ تغییر دارد", "error")

    def _on_double_click(self, e):
        wid = self._get_selected_id()
        if not wid: return
        row = self._row_by_id(wid)
        if not row: return
        if self._is_admin:
            # مدیر: اگر گزارشی رسیده → مشاهده، وگرنه → ویرایش
            if (row.get("report_text") or "").strip():
                self._view_report_dialog(wid)
            else:
                self._open_edit_dialog(wid)
        elif self._is_assigned_to_me(row):
            self._report_dialog(wid)
        elif self._can_modify(wid):
            self._open_edit_dialog(wid)
        else:
            ToastNotification(self, "⛔ این دستور کار برای شما نیست", "error")


    def _edit_selected(self):
        wid = self._get_selected_id()
        if not wid: return
        if not self._can_modify(wid):
            self._deny_modify(); return
        self._open_edit_dialog(wid)

    def _close_selected(self):
        wid = self._get_selected_id()
        if not wid: return
        if not self._can_modify(wid):
            self._deny_modify(); return
        if not messagebox.askyesno("تأیید", "آیا این دستور کار بسته شود؟"):
            return
        def work():
            try:
                wo_sync.update(wid, {"status": "بسته"})
                def ok():
                    ToastNotification(self, "دستور کار بسته شد ✓", "success")
                    self._reload_local(); self.app.refresh_dashboard()
                self.after(0, ok)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"خطا در بستن: {err}", "error"))
        threading.Thread(target=work, daemon=True).start()

    def _delete_selected(self):
        wid = self._get_selected_id()
        if not wid: return
        if not self._can_modify(wid):
            self._deny_modify(); return
        if not messagebox.askyesno("حذف", "آیا از حذف مطمئن هستید؟", icon="warning"):
            return
        def work():
            try:
                wo_sync.delete(wid)
                def ok():
                    ToastNotification(self, "حذف شد", "info")
                    # حذف محلیِ فوری — تا سطر با migrate بعدی دوباره زنده نشود
                    try:
                        db.execute("DELETE FROM work_orders WHERE id=?", (wid,))
                    except Exception:
                        pass
                    try:
                        wo_sync.pull_quiet()
                    except Exception:
                        pass
                    self._reload_local()
                    self.app.refresh_dashboard()
                    try:
                        self.app.update_wo_badges(initial=True)
                    except Exception:
                        pass
                self.after(0, ok)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"خطا در حذف: {err}", "error"))
        threading.Thread(target=work, daemon=True).start()
    def _export_excel(self):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx", filetypes=[("Excel","*.xlsx")],
                initialfile="work_orders_export.xlsx")
            if not path: return
            wb = openpyxl.Workbook(); ws = wb.active; ws.title="دستور کارها"
            headers=["شماره","نوع","تجهیز","موقعیت","اپراتور","تکنسین","تاریخ",
                     "توقف (دقیقه)","اولویت","وضعیت","گزارش","امتیاز","سازنده"]
            ws.append(headers)
            fill = PatternFill("solid", fgColor="F97316")
            for cell in ws[1]:
                cell.fill = fill; cell.font = Font(bold=True, color="000000")
                cell.alignment = Alignment(horizontal="center")
            for r in self._all_rows:
                rs = r.get("report_status") or ""
                rep = {"ارسال شده":"ارسال شده","تأیید شده":"تأیید شده"}.get(rs, "")
                rate = r.get("report_rating")
                ws.append([r["order_number"],r["order_type"],r["eq_name"] or "",
                           r["location"] or "",r["operator"],r["technician_name"] or "",
                           r["work_date"],r["downtime_minutes"],r["priority"],r["status"],
                           rep, round(rate,2) if rate is not None else "",
                           self._creator_display(r)])
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(len(str(c.value or "")) for c in col)+4
            wb.save(path)
            ToastNotification(self, "فایل اکسل ذخیره شد ✓", "success")
        except Exception as ex:
            messagebox.showerror("خطا", str(ex))

    # ─────────────── گزارش کار تکنسین ───────────────

    def _report_selected(self):
        wid = self._get_selected_id()
        if not wid: return
        row = self._row_by_id(wid)
        if not row: return
        if not self._is_assigned_to_me(row):
            ToastNotification(self, "⛔ فقط تکنسینِ تعیین‌شده برای این دستور کار می‌تواند گزارش بنویسد", "error")
            return
        self._report_dialog(wid)


    def _report_dialog(self, wo_id):
        row = db.fetch_one("""
            SELECT wo.*, e.name as eq_name FROM work_orders wo
            LEFT JOIN equipment e ON wo.equipment_id=e.id WHERE wo.id=?""", (wo_id,))
        if not row: return

        dlg = tk.Toplevel(self)
        dlg.title(f"گزارش کار — {row['order_number']}")
        dlg.configure(bg=COLORS["bg_dark"]); dlg.geometry("600x660"); dlg.grab_set()

        tk.Label(dlg, text=f"📨  گزارش کار برای {row['order_number']}", font=FONTS["heading"],
                 bg=COLORS["bg_dark"], fg=COLORS["accent"]).pack(padx=20, pady=(12,0), anchor="e")
        tk.Label(dlg, text=f"🔧 {row.get('eq_name') or '-'}   |   📅 {row['work_date']}   |   اولویت: {row['priority']}",
                 font=FONTS["small"], bg=COLORS["bg_dark"], fg=COLORS["text_muted"]).pack(padx=20, anchor="e")

        card = tk.Frame(dlg, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=8)
        frm = tk.Frame(card, bg=COLORS["bg_card"])
        frm.pack(fill="both", expand=True, padx=16, pady=10)

        # شرح کار از طرف مدیر (فقط خواندنی)
        tk.Label(frm, text="شرح کار (از طرف مدیر)", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"], anchor="e").pack(fill="x")
        desc_txt = tk.Text(frm, font=FONTS["body"], bg=COLORS["bg_input"],
                           fg=COLORS["text_muted"], relief="flat", height=3, wrap="word")
        desc_txt.pack(fill="x", pady=(2,6))
        desc_txt.insert("1.0", row["description"] or "-")
        desc_txt.configure(state="disabled")

        f_act = FormField(frm, "شرح اقدام انجام شده", "text")
        f_act.set(row["action_taken"] or ""); f_act.pack(fill="x", pady=4)
        f_parts = FormField(frm, "قطعات مصرفی")
        f_parts.set(row["parts_used"] or ""); f_parts.pack(fill="x", pady=4)

        row_fr = tk.Frame(frm, bg=COLORS["bg_card"]); row_fr.pack(fill="x", pady=4)
        f_start = FormField(row_fr, "ساعت شروع"); f_start.set(row["start_time"] or "")
        f_start.pack(side="right", fill="x", expand=True, padx=(0,4))
        f_end = FormField(row_fr, "ساعت پایان"); f_end.set(row["end_time"] or "")
        f_end.pack(side="right", fill="x", expand=True)

        row_fr2 = tk.Frame(frm, bg=COLORS["bg_card"]); row_fr2.pack(fill="x", pady=4)
        f_down = FormField(row_fr2, "مدت توقف (دقیقه)")
        f_down.set(str(row["downtime_minutes"] or 0))
        f_down.pack(side="right", fill="x", expand=True, padx=(0,4))
        f_status = FormField(row_fr2, "وضعیت کار", "combobox", ["باز","در حال انجام","بسته","معلق"])
        f_status.set(row["status"] or "در حال انجام")
        f_status.pack(side="right", fill="x", expand=True)

        f_report = FormField(frm, "گزارش نهایی برای مدیر ✱", "text")
        f_report.set(row["report_text"] or ""); f_report.pack(fill="x", pady=4)

        if row.get("report_status"):
            info = f"📨 گزارش قبلاً در {row.get('report_submitted_at') or '-'} ارسال شده — با ذخیره، جایگزین می‌شود"
            if row.get("report_rating") is not None:
                info += f"   |   ⭐ امتیاز مدیر: {row['report_rating']:g}"
            tk.Label(frm, text=info, font=FONTS["small"], bg=COLORS["bg_card"],
                     fg=COLORS["yellow"], anchor="e").pack(fill="x", pady=(2,0))

        def _save():
            rep = f_report.get().strip()
            if not rep:
                messagebox.showerror("خطا", "متن گزارش نهایی الزامی است"); return
            try: down = int(f_down.get() or 0)
            except ValueError: down = 0
            data = {"report_text": rep, "action_taken": f_act.get(),
                    "parts_used": f_parts.get(), "start_time": f_start.get(),
                    "end_time": f_end.get(), "downtime_minutes": down,
                    "status": f_status.get()}
            def work():
                try:
                    apx.wo_submit_report(wo_id, data)
                    wo_sync.pull_quiet()
                    def ok():
                        dlg.destroy()
                        ToastNotification(self, "گزارش کار برای مدیر ارسال شد ✓", "success")
                        self._reload_local(); self.app.refresh_dashboard()
                    self.after(0, ok)
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda: ToastNotification(self, f"ارسال گزارش ناموفق: {err}", "error"))
            threading.Thread(target=work, daemon=True).start()

        btn_row = tk.Frame(dlg, bg=COLORS["bg_dark"]); btn_row.pack(fill="x", padx=20, pady=10)
        IconButton(btn_row, "ارسال گزارش", "📨", _save, color=COLORS["accent"]).pack(side="right")
        IconButton(btn_row, "انصراف", "✗", dlg.destroy, color=COLORS["bg_card"]).pack(side="right", padx=(0,8))

    # ─────────────── کارنامه عملکرد ───────────────
        # ─────────────── مشاهده گزارش (فقط مدیر) ───────────────

    def _view_selected_report(self):
        wid = self._get_selected_id()
        if not wid: return
        self._view_report_dialog(wid)

    def _view_report_dialog(self, wo_id):
        row = db.fetch_one("""
            SELECT wo.*, e.name as eq_name FROM work_orders wo
            LEFT JOIN equipment e ON wo.equipment_id=e.id WHERE wo.id=?""", (wo_id,))
        if not row:
            return
        if not (row.get("report_text") or "").strip():
            messagebox.showinfo(
                "گزارشی نیست",
                f"برای دستور کار {row['order_number']} هنوز گزارشی از طرف تکنسین ارسال نشده است.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"مشاهده گزارش — {row['order_number']}")
        dlg.configure(bg=COLORS["bg_dark"]); dlg.geometry("640x680"); dlg.grab_set()

        tk.Label(dlg, text=f"👁️  گزارش کار — {row['order_number']}", font=FONTS["heading"],
                 bg=COLORS["bg_dark"], fg=COLORS["accent"]).pack(padx=20, pady=(12, 0), anchor="e")
        tech_disp = self._user_map.get((row.get("technician_username") or "").strip(),
                                       row.get("technician_name") or "-")
        tk.Label(dlg, text=f"👤 تکنسین: {tech_disp}   |   🔧 {row.get('eq_name') or '-'}   |   "
                           f"📅 {row['work_date']}   |   وضعیت: {row['status']}",
                 font=FONTS["small"], bg=COLORS["bg_dark"], fg=COLORS["text_muted"]).pack(
            padx=20, anchor="e")

        card = tk.Frame(dlg, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=8)
        frm = tk.Frame(card, bg=COLORS["bg_card"])
        frm.pack(fill="both", expand=True, padx=16, pady=10)

        def _ro(title, text, height=3, highlight=False):
            tk.Label(frm, text=title, font=FONTS["small"], bg=COLORS["bg_card"],
                     fg=COLORS["accent"] if highlight else COLORS["text_secondary"],
                     anchor="e").pack(fill="x")
            t = tk.Text(frm, font=FONTS["body"], bg=COLORS["bg_input"],
                        fg=COLORS["text_primary"], relief="flat", height=height, wrap="word")
            t.pack(fill="x", pady=(2, 6))
            t.insert("1.0", text or "—")
            t.configure(state="disabled")

        _ro("شرح کار (ثبت مدیر)", row.get("description"))
        _ro("اقدام انجام شده", row.get("action_taken"))
        _ro("قطعات مصرفی", row.get("parts_used"), height=2)
        tk.Label(frm, text=f"🕒 {row.get('start_time') or '-'} تا {row.get('end_time') or '-'}   |   "
                           f"⏱ توقف: {row.get('downtime_minutes') or 0} دقیقه   |   "
                           f"📨 زمان ارسال گزارش: {row.get('report_submitted_at') or '-'}",
                 font=FONTS["small"], bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                 anchor="e").pack(fill="x", pady=2)
        _ro("گزارش نهایی تکنسین", row.get("report_text"), height=6, highlight=True)

        if row.get("report_rating") is not None:
            stars = "⭐" * int(round(row["report_rating"]))
            tk.Label(frm, text=f"امتیاز شما: {row['report_rating']:g}  {stars}   |   "
                               f"نظر: {row.get('report_comment') or '-'}",
                     font=FONTS["subhead"], bg=COLORS["bg_card"], fg=COLORS["yellow"],
                     anchor="e").pack(fill="x", pady=(2, 0))
        else:
            f_rate = FormField(frm, "امتیازدهی به این گزارش (۰ تا ۵)", "combobox",
                               ["5", "4.5", "4", "3.5", "3", "2.5", "2", "1.5", "1", "0.5", "0"])
            f_rate.set("5")
            f_rate.pack(fill="x", pady=2)
            f_cmt = FormField(frm, "نظر مدیر")
            f_cmt.pack(fill="x", pady=2)

            def _save_rate():
                try:
                    rating = float(f_rate.get())
                except ValueError:
                    messagebox.showerror("خطا", "امتیاز را انتخاب کنید")
                    return
                def work():
                    try:
                        apx.wo_rate(wo_id, rating, f_cmt.get())
                        wo_sync.pull_quiet()
                        def ok():
                            dlg.destroy()
                            ToastNotification(self, "امتیاز ثبت شد ✓", "success")
                            self._reload_local()
                        self.after(0, ok)
                    except Exception as e:
                        err = str(e)
                        self.after(0, lambda: ToastNotification(self, f"ثبت امتیاز ناموفق: {err}", "error"))
                threading.Thread(target=work, daemon=True).start()

            IconButton(frm, "ثبت امتیاز", "⭐", _save_rate, color=COLORS["yellow"]).pack(pady=4)

        btn_row = tk.Frame(dlg, bg=COLORS["bg_dark"])
        btn_row.pack(fill="x", padx=20, pady=8)
        IconButton(btn_row, "بستن", "✗", dlg.destroy, color=COLORS["bg_card"]).pack(side="right")
    def _show_performance(self):
        dlg = tk.Toplevel(self)
        dlg.title("کارنامه عملکرد پرسنل")
        dlg.configure(bg=COLORS["bg_dark"]); dlg.geometry("980x640"); dlg.grab_set()

        tk.Label(dlg, text="📊  کارنامه عملکرد پرسنل", font=FONTS["title"],
                 bg=COLORS["bg_dark"], fg=COLORS["text_primary"]).pack(padx=20, pady=(12,0), anchor="e")
        tk.Label(dlg, text="میانگین امتیاز از امتیازدهی مدیر به گزارش‌های کار محاسبه می‌شود (۰ تا ۵)",
                 font=FONTS["small"], bg=COLORS["bg_dark"], fg=COLORS["text_muted"]).pack(padx=20, anchor="e")

        cols = ("تکنسین","کل دستور کار","بسته‌شده","گزارش در انتظار بررسی","تأییدشده","میانگین امتیاز","میانگین توقف EM (دق)")
        perf_tree = StyledTreeview(dlg, cols, row_height=30)
        perf_tree.pack(fill="x", padx=20, pady=8)
        for col, w in zip(cols, [160,90,80,130,80,100,115]):
            perf_tree.tree.column(col, width=w, minwidth=w)

        detail_lbl = tk.Label(dlg, text="یک نفر را از جدول بالا انتخاب کنید…", font=FONTS["body"],
                              bg=COLORS["bg_dark"], fg=COLORS["text_secondary"], anchor="e")
        detail_lbl.pack(fill="x", padx=20, anchor="e")

        dcols = ("شماره","نوع","تجهیز","تاریخ","وضعیت","گزارش","امتیاز")
        detail_tree = StyledTreeview(dlg, dcols, row_height=28)
        detail_tree.pack(fill="both", expand=True, padx=20, pady=4)
        for col, w in zip(dcols, [120,55,160,90,90,120,70]):
            detail_tree.tree.column(col, width=w, minwidth=w)

        def _load_detail(un=None):
            detail_tree.clear()
            if not un: return
            rows = db.fetch_all("""SELECT wo.*, e.name as eq_name FROM work_orders wo
                LEFT JOIN equipment e ON wo.equipment_id=e.id
                WHERE wo.technician_username=? ORDER BY wo.id DESC""", (un,))
            for r in rows:
                rs = r.get("report_status")
                if rs == "تأیید شده":
                    rep = "✅ تأیید شده"
                    rate = f"⭐ {r['report_rating']:g}" if r.get("report_rating") is not None else "-"
                elif rs == "ارسال شده":
                    rep, rate = "📨 در انتظار بررسی", "-"
                else:
                    rep, rate = "-", "-"
                detail_tree.insert((r["order_number"],
                                    "🔴 EM" if r["order_type"]=="EM" else "🔵 PM",
                                    r.get("eq_name") or "-", r["work_date"], r["status"],
                                    rep, rate), iid=str(r["id"]))

        def _on_perf_select(e):
            sel = perf_tree.tree.selection()
            if not sel: return
            un = sel[0]
            nm = perf_tree.tree.item(sel[0])["values"][0]
            detail_lbl.configure(text=f"🔧 دستور کارهای {nm}")
            _load_detail(un)
        perf_tree.tree.bind("<<TreeviewSelect>>", _on_perf_select)

        def _fill(rows):
            perf_tree.clear()
            self._perf_rows = rows or []
            if not self._perf_rows:
                detail_lbl.configure(text="داده‌ای نیست — هنوز دستور کاری به پرسنل نسبت داده نشده")
                return
            for r in self._perf_rows:
                avg = r.get("avg_rating")
                star = f"⭐ {avg:.1f}" if avg is not None else "—"
                perf_tree.insert((
                    r.get("technician_name") or r.get("technician_username") or "-",
                    r.get("total") or 0, r.get("closed") or 0,
                    r.get("pending_reports") or 0, r.get("confirmed") or 0,
                    star, round(r.get("avg_downtime") or 0)),
                    iid=str(r["technician_username"]))
            if len(self._perf_rows) == 1:
                un = str(self._perf_rows[0]["technician_username"])
                perf_tree.tree.selection_set(un)

        def _fetch():
            rows = None
            try:
                rows = apx.performance_list()
                wo_sync.pull_quiet()
            except Exception:
                rows = None
            def ui():
                if rows is None:
                    ToastNotification(dlg, "دریافت کارنامه ناموفق — اتصال سرور را بررسی کنید", "error")
                    return
                _fill(rows)
            try:
                self.after(0, ui)
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

        btn_fr = tk.Frame(dlg, bg=COLORS["bg_dark"]); btn_fr.pack(fill="x", padx=20, pady=8)
        if self._is_admin:
            IconButton(btn_fr, "امتیازدهی به گزارش", "⭐",
                       lambda: self._rate_selected_report(dlg, detail_tree),
                       color=COLORS["yellow"]).pack(side="right", padx=4)
        IconButton(btn_fr, "خروجی اکسل کارنامه", "📥",
                   lambda: self._export_performance(dlg),
                   color=COLORS["bg_card"]).pack(side="left", padx=4)

    def _rate_selected_report(self, dlg, detail_tree):
        sel = detail_tree.tree.selection()
        if not sel:
            messagebox.showinfo("انتخاب", "یک دستور کار از جدول پایین انتخاب کنید"); return
        wo_id = int(sel[0])
        row = db.fetch_one("SELECT * FROM work_orders WHERE id=?", (wo_id,))
        if not row: return
        if not row.get("report_status"):
            messagebox.showwarning("گزارشی نیست", "برای این دستور کار هنوز گزارشی ارسال نشده است"); return

        rd = tk.Toplevel(dlg)
        rd.title(f"امتیازدهی — {row['order_number']}")
        rd.configure(bg=COLORS["bg_dark"]); rd.geometry("400x360"); rd.grab_set()
        card = tk.Frame(rd, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(card, text=f"گزارش {row['technician_name'] or '-'}:", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"], anchor="e").pack(fill="x", padx=12, pady=(8,0))
        txt = tk.Text(card, font=FONTS["body"], bg=COLORS["bg_input"],
                      fg=COLORS["text_primary"], relief="flat", height=4, wrap="word")
        txt.pack(fill="x", padx=12, pady=4)
        txt.insert("1.0", row.get("report_text") or "")
        txt.configure(state="disabled")

        f_rate = FormField(card, "امتیاز (۰ تا ۵)", "combobox",
                           ["5","4.5","4","3.5","3","2.5","2","1.5","1","0.5","0"])
        f_rate.set("5" if row.get("report_rating") is None else f"{row['report_rating']:g}")
        f_rate.pack(fill="x", padx=12, pady=4)
        f_cmt = FormField(card, "نظر مدیر")
        f_cmt.set(row.get("report_comment") or "")
        f_cmt.pack(fill="x", padx=12, pady=4)

        def _save():
            try: rating = float(f_rate.get())
            except ValueError:
                messagebox.showerror("خطا", "امتیاز را انتخاب کنید"); return
            def work():
                try:
                    apx.wo_rate(wo_id, rating, f_cmt.get())
                    wo_sync.pull_quiet()
                    def ok():
                        rd.destroy()
                        ToastNotification(dlg, "امتیاز ثبت شد ✓", "success")
                        try: dlg.destroy()
                        except Exception: pass
                        self._show_performance()
                    self.after(0, ok)
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda: ToastNotification(dlg, f"ثبت امتیاز ناموفق: {err}", "error"))
            threading.Thread(target=work, daemon=True).start()

        IconButton(card, "ثبت امتیاز", "⭐", _save, color=COLORS["yellow"]).pack(pady=8)

    def _export_performance(self, parent):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                filetypes=[("Excel","*.xlsx")], initialfile="performance_report.xlsx",
                parent=parent)
            if not path: return
            wb = openpyxl.Workbook(); ws = wb.active; ws.title="کارنامه پرسنل"
            ws.append(["تکنسین","کل دستور کار","بسته‌شده","گزارش در انتظار بررسی","تأییدشده","میانگین امتیاز","میانگین توقف EM (دق)"])
            fill = PatternFill("solid", fgColor="F97316")
            for cell in ws[1]:
                cell.fill = fill; cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
            for r in self._perf_rows:
                ws.append([r.get("technician_name") or r.get("technician_username") or "-",
                           r.get("total") or 0, r.get("closed") or 0,
                           r.get("pending_reports") or 0, r.get("confirmed") or 0,
                           round(r["avg_rating"],2) if r.get("avg_rating") is not None else "",
                           round(r.get("avg_downtime") or 0)])
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(len(str(c.value or "")) for c in col)+4
            wb.save(path)
            ToastNotification(parent, "فایل اکسل کارنامه ذخیره شد ✓", "success")
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=parent)

    # ─────────────── ویرایش (مدیر/سازنده) ───────────────

    def _open_edit_dialog(self, wo_id):
        row = db.fetch_one("""
            SELECT wo.*, e.name as eq_name FROM work_orders wo
            LEFT JOIN equipment e ON wo.equipment_id=e.id WHERE wo.id=?""",(wo_id,))
        if not row: return

        dlg = tk.Toplevel(self)
        dlg.title(f"ویرایش — {row['order_number']}")
        dlg.configure(bg=COLORS["bg_dark"]); dlg.geometry("640x660"); dlg.grab_set()

        tk.Label(dlg, text=f"✏️  {row['order_number']}", font=FONTS["heading"],
                 bg=COLORS["bg_dark"], fg=COLORS["accent"]).pack(padx=20, pady=(12,0), anchor="e")
        tk.Label(dlg, text=f"👤  سازنده: {self._creator_display(row)}",
                 font=FONTS["small"], bg=COLORS["bg_dark"],
                 fg=COLORS["text_muted"]).pack(padx=20, pady=(0,4), anchor="e")

        card = tk.Frame(dlg, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=4)
        frm = tk.Frame(card, bg=COLORS["bg_card"])
        frm.pack(fill="both", expand=True, padx=16, pady=12)

        flds={}
        defs=[("اپراتور","operator","combobox",["مکانیک","برق","تاسیسات"]),
              ("تاریخ کار","work_date","entry",None),
              ("توقف (دقیقه)","downtime_minutes","entry",None),
              ("اولویت","priority","combobox",["بحرانی","بالا","متوسط","پایین"]),
              ("وضعیت","status","combobox",["باز","در حال انجام","بسته","معلق"])]
        row_fr=None
        for idx,(lbl,key,ft,opts) in enumerate(defs):
            if idx%2==0:
                row_fr=tk.Frame(frm,bg=COLORS["bg_card"]); row_fr.pack(fill="x",pady=4)
            f=FormField(row_fr,lbl,ft,opts)
            f.pack(side="right" if idx%2==0 else "left",fill="x",expand=True,
                   padx=(4,0) if idx%2==0 else (0,4))
            f.set(str(row[key] or "")); flds[key]=f

        tech_fr=tk.Frame(frm,bg=COLORS["bg_card"]); tech_fr.pack(fill="x",pady=4)
        tk.Label(tech_fr,text="نام تکنسین",font=FONTS["small"],
                 bg=COLORS["bg_card"],fg=COLORS["text_secondary"],anchor="e").pack(fill="x")
        f_tech=ttk.Combobox(tech_fr,values=list(self._tech_names or []),
                            font=FONTS["body"],justify="center",state="normal")
        f_tech.set(row["technician_name"] or "")
        f_tech.pack(fill="x",ipady=3)

        f_desc=FormField(frm,"شرح کار","text"); f_desc.set(row["description"] or ""); f_desc.pack(fill="x",pady=4)
        f_act =FormField(frm,"اقدام انجام شده","text"); f_act.set(row["action_taken"] or ""); f_act.pack(fill="x",pady=4)

        # ── گزارش تکنسین (اگر ارسال شده) + امتیازدهی مدیر ──
        f_rate = None
        if row.get("report_text"):
            tk.Frame(frm, bg=COLORS["border"], height=1).pack(fill="x", pady=6)
            tk.Label(frm, text=f"📨 گزارش تکنسین — ارسال در {row.get('report_submitted_at') or '-'}",
                     font=FONTS["subhead"], bg=COLORS["bg_card"],
                     fg=COLORS["yellow"], anchor="e").pack(fill="x")
            rep_txt = tk.Text(frm, font=FONTS["body"], bg=COLORS["bg_input"],
                              fg=COLORS["text_primary"], relief="flat", height=3, wrap="word")
            rep_txt.pack(fill="x", pady=2)
            rep_txt.insert("1.0", row["report_text"])
            rep_txt.configure(state="disabled")
            if row.get("report_rating") is not None:
                tk.Label(frm, text=f"⭐ امتیاز فعلی: {row['report_rating']:g}",
                         font=FONTS["small"], bg=COLORS["bg_card"],
                         fg=COLORS["text_secondary"], anchor="e").pack(fill="x")
            if self._is_admin:
                f_rate = FormField(frm, "امتیازدهی به گزارش (۰ تا ۵)", "combobox",
                                   ["—","5","4.5","4","3.5","3","2.5","2","1.5","1","0.5","0"])
                f_rate.set("—" if row.get("report_rating") is None else f"{row['report_rating']:g}")
                f_rate.pack(fill="x", pady=2)

        def _save():
            try: down=int(flds["downtime_minutes"].get() or 0)
            except: down=0
            new_date = flds["work_date"].get().strip()
            if not _validate_date(new_date):
                messagebox.showerror("خطا", "فرمت تاریخ باید دقیقاً YYYY-MM-DD باشد.")
                return
            data = {
                "operator": flds["operator"].get(),
                "technician_name": f_tech.get().strip(),
                "work_date": new_date,
                "downtime_minutes": down,
                "priority": flds["priority"].get(),
                "status": flds["status"].get(),
                "description": f_desc.get(),
                "action_taken": f_act.get(),
            }
            def work():
                try:
                    wo_sync.update(wo_id, data)
                    if f_rate is not None and f_rate.get() != "—":
                        try:
                            apx.wo_rate(wo_id, float(f_rate.get()))
                        except Exception:
                            pass
                    def ok():
                        dlg.destroy()
                        ToastNotification(self, "تغییرات روی سرور ذخیره شد ✓", "success")
                        self._reload_local(); self.app.refresh_dashboard()
                    self.after(0, ok)
                except Exception as e:
                    err = str(e)
                    self.after(0, lambda: ToastNotification(self, f"ذخیره نشد — اتصال به سرور را بررسی کن\n{err}", "error"))
            threading.Thread(target=work, daemon=True).start()

        btn_row=tk.Frame(dlg,bg=COLORS["bg_dark"]); btn_row.pack(fill="x",padx=20,pady=10)
        IconButton(btn_row,"ذخیره تغییرات","💾",_save,color=COLORS["accent"]).pack(side="right")
        IconButton(btn_row,"انصراف","✗",dlg.destroy,color=COLORS["bg_card"]).pack(side="right",padx=(0,8))        