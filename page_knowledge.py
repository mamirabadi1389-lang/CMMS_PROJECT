# page_knowledge.py — ثبت تجربیات: دانشنامه‌ی فنی سازمان
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import database as db
import api_client
import api_client_ext
from styles import COLORS, FONTS
from widgets import StyledTreeview, FormField, IconButton, ToastNotification

CATEGORIES = ["مکانیکی", "برقی", "تاسیسات", "ابزار دقیق", "نرم‌افزاری", "سایر"]


def _text_field(parent, label, height=4, required=False):
    """فیلد متنی چندخطی هم‌رنگ برنامه — بدون تغییر در widgets.py"""
    fr = tk.Frame(parent, bg=COLORS["bg_card"])
    req = " *" if required else ""
    tk.Label(fr, text=f"{label}{req}", font=FONTS["small"], bg=COLORS["bg_card"],
             fg=COLORS["text_secondary"], anchor="w").pack(fill="x")
    txt = tk.Text(fr, font=FONTS["body"], bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                 insertbackground=COLORS["accent"], relief="flat",
                 highlightbackground=COLORS["border"], highlightthickness=1,
                 height=height, wrap="word")
    txt.pack(fill="x", pady=(2, 0))
    return fr, txt


class KnowledgePage(tk.Frame):
    def __init__(self, parent, app=None):
        super().__init__(parent, bg=COLORS["bg_dark"])
        self.app = app
        self._rows = []
        self._edit_id = None

        user = api_client.current_user or {}
        if not user:
            try:
                api_client.current_user = api_client.whoami()
                user = api_client.current_user
            except Exception:
                user = {}
        self.is_admin = user.get("role") == "admin"
        self.username = user.get("username")

        # ---------- هدر ----------
        hdr = tk.Frame(self, bg=COLORS["bg_dark"])
        hdr.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(hdr, text="📚 ثبت تجربیات — دانشنامه‌ی فنی سازمان", font=FONTS["heading"],
                 bg=COLORS["bg_dark"], fg=COLORS["text_primary"]).pack(side="right")
        IconButton(hdr, text="بروزرسانی", icon="🔄", command=self.refresh,
                  color=COLORS["bg_card"], fg=COLORS["text_primary"], width=90).pack(side="left")

        body = tk.Frame(self, bg=COLORS["bg_dark"])
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ---------- کارت ثبت تجربه (سمت راست) ----------
        form_card = tk.Frame(body, bg=COLORS["bg_card"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
        form_card.pack(side="right", fill="y", padx=(0, 12))
        form_card.configure(width=360)
        form_card.pack_propagate(False)

        form_canvas = tk.Canvas(form_card, bg=COLORS["bg_card"], highlightthickness=0)
        form_scroll = tk.Scrollbar(form_card, orient="vertical", command=form_canvas.yview,
                                   bg=COLORS["bg_card"], troughcolor=COLORS["bg_dark"])
        form_canvas.configure(yscrollcommand=form_scroll.set)
        form_scroll.pack(side="left", fill="y")
        form_canvas.pack(side="right", fill="both", expand=True)
        form_inner = tk.Frame(form_canvas, bg=COLORS["bg_card"])
        _form_win = form_canvas.create_window((0, 0), window=form_inner, anchor="nw")
        form_inner.bind("<Configure>",
                        lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.bind("<Configure>",
                         lambda e: form_canvas.itemconfig(_form_win, width=e.width))
        form_canvas.bind("<MouseWheel>",
                         lambda e: form_canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        form_card = form_inner  # بقیه‌ی فیلدها مثل قبل داخل form_card ساخته می‌شوند

        self.form_title_lbl = tk.Label(form_card, text="✍️  ثبت تجربه‌ی جدید", font=FONTS["heading"],
                                       bg=COLORS["bg_card"], fg=COLORS["accent"])
        self.form_title_lbl.pack(fill="x", padx=16, pady=(16, 8))

        self.f_title = FormField(form_card, "عنوان", "entry", required=True)
        self.f_title.pack(fill="x", padx=16)

        self.f_category = FormField(form_card, "دسته‌بندی", "combobox", options=CATEGORIES)
        self.f_category.set(CATEGORIES[0])
        self.f_category.pack(fill="x", padx=16, pady=(10, 0))

        eq_fr = tk.Frame(form_card, bg=COLORS["bg_card"])
        eq_fr.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(eq_fr, text="تجهیز مرتبط (اختیاری)", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"], anchor="w").pack(fill="x")
        equip_names = [r["name"] for r in db.fetch_all("SELECT name FROM equipment ORDER BY name")]
        self.f_eq = ttk.Combobox(eq_fr, values=equip_names, font=FONTS["body"], state="normal")
        self.f_eq.pack(fill="x", ipady=3)

        self.f_wo_ref = FormField(form_card, "شماره دستور کار مرتبط (اختیاری)", "entry")
        self.f_wo_ref.pack(fill="x", padx=16, pady=(10, 0))

        problem_fr, self.problem_txt = _text_field(form_card, "شرح مشکل", height=4, required=True)
        problem_fr.pack(fill="x", padx=16, pady=(10, 0))

        solution_fr, self.solution_txt = _text_field(form_card, "راه‌حل / اقدام انجام‌شده", height=4)
        solution_fr.pack(fill="x", padx=16, pady=(10, 0))

        tips_fr, self.tips_txt = _text_field(form_card, "نکته برای دفعات بعد", height=2)
        tips_fr.pack(fill="x", padx=16, pady=(10, 0))

        self.f_tags = FormField(form_card, "برچسب‌ها (با کاما جدا کنید)", "entry")
        self.f_tags.pack(fill="x", padx=16, pady=(10, 0))

        btn_row = tk.Frame(form_card, bg=COLORS["bg_card"])
        btn_row.pack(pady=16)
        self.save_btn = IconButton(btn_row, text="ثبت تجربه", icon="💾",
                                   command=self._save, color=COLORS["green"])
        self.save_btn.pack(side="right", padx=4)
        IconButton(btn_row, text="پاک کردن فرم", icon="✖", command=self._clear_form,
                  color=COLORS["bg_card"], fg=COLORS["text_primary"], width=110).pack(side="right", padx=4)

        # ---------- کارت لیست تجربیات (سمت چپ) ----------
        list_card = tk.Frame(body, bg=COLORS["bg_dark"])
        list_card.pack(side="right", fill="both", expand=True)

        filt_fr = tk.Frame(list_card, bg=COLORS["bg_dark"])
        filt_fr.pack(fill="x", pady=(0, 8))
        self.search_entry = tk.Entry(filt_fr, font=FONTS["body"], bg=COLORS["bg_input"],
                                     fg=COLORS["text_primary"], relief="flat",
                                     insertbackground=COLORS["accent"], justify="right")
        self.search_entry.pack(side="right", fill="x", expand=True, ipady=5, padx=(8, 8))
        self.search_entry.bind("<Return>", lambda e: self.refresh())
        self.filter_cat = ttk.Combobox(filt_fr, values=["همه دسته‌ها"] + CATEGORIES,
                                       state="readonly", font=FONTS["small"], width=14)
        self.filter_cat.current(0)
        self.filter_cat.pack(side="right")
        self.filter_cat.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        IconButton(filt_fr, text="جستجو", icon="🔎", command=self.refresh,
                  color=COLORS["accent_dim"], fg=COLORS["accent"], width=90).pack(side="right", padx=(8, 0))

        cols = ["id", "title", "category", "eq_name", "author", "created_at"]
        heads = ["#", "عنوان", "دسته", "تجهیز", "ثبت‌کننده", "تاریخ"]
        self.tree = StyledTreeview(list_card, cols, heads)
        self.tree.pack(fill="both", expand=True)

        btns = tk.Frame(list_card, bg=COLORS["bg_dark"])
        btns.pack(fill="x", pady=(10, 0))
        IconButton(btns, text="مشاهده", icon="👁", command=self._view,
                  color=COLORS["bg_card"], fg=COLORS["text_primary"], width=90).pack(side="right", padx=(8, 0))
        IconButton(btns, text="ویرایش", icon="✏️", command=self._edit,
                  color=COLORS["accent"], width=90).pack(side="right", padx=8)
        IconButton(btns, text="حذف", icon="🗑", command=self._delete,
                  color=COLORS["red"], fg="#fff", width=90).pack(side="right", padx=8)

        self.refresh()

    # ---------------- ثبت / ویرایش ----------------
    def _collect_form(self):
        eq_name = self.f_eq.get().strip()
        return {
            "title": self.f_title.get().strip(),
            "category": self.f_category.get().strip() or CATEGORIES[-1],
            "eq_name": eq_name or None,
            "work_order_ref": self.f_wo_ref.get().strip() or None,
            "problem": self.problem_txt.get("1.0", "end-1c").strip(),
            "solution": self.solution_txt.get("1.0", "end-1c").strip(),
            "tips": self.tips_txt.get("1.0", "end-1c").strip(),
            "tags": self.f_tags.get().strip() or None,
        }

    def _save(self):
        data = self._collect_form()
        if not data["title"] or not data["problem"]:
            ToastNotification(self, "عنوان و شرح مشکل الزامی است", "error")
            return
        edit_id = self._edit_id

        def work():
            try:
                if edit_id:
                    api_client_ext.exp_update(edit_id, data)
                    msg = "ویرایش شد"
                else:
                    api_client_ext.exp_create(data)
                    msg = "تجربه با موفقیت ثبت شد"
                self.after(0, lambda: ToastNotification(self, msg, "success"))
                self.after(0, self._clear_form)
                self.after(0, self.refresh)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"ثبت ناموفق: {err}", "error"))

        threading.Thread(target=work, daemon=True).start()

    def _clear_form(self):
        self._edit_id = None
        self.form_title_lbl.configure(text="✍️  ثبت تجربه‌ی جدید")
        self.f_title.set("")
        self.f_category.set(CATEGORIES[0])
        self.f_eq.set("")
        self.f_wo_ref.set("")
        self.problem_txt.delete("1.0", "end")
        self.solution_txt.delete("1.0", "end")
        self.tips_txt.delete("1.0", "end")
        self.f_tags.set("")

    # ---------------- لیست ----------------
    def refresh(self):
        search = self.search_entry.get().strip() if hasattr(self, "search_entry") else ""
        cat = None
        if hasattr(self, "filter_cat") and self.filter_cat.current() > 0:
            cat = self.filter_cat.get()

        def load():
            try:
                rows = api_client_ext.exp_list(category=cat, q=search or None)
            except Exception as e:
                err = str(e)
                self._rows = []
                self.after(0, lambda: ToastNotification(self, f"خطا در دریافت تجربیات: {err}", "error"))
                return
            self._rows = rows
            self.after(0, self._render)

        threading.Thread(target=load, daemon=True).start()

    def _render(self):
        self.tree.clear()
        for e in self._rows:
            self.tree.insert(
                [e["id"], e.get("title", ""), e.get("category", ""),
                 e.get("eq_name") or "-", e.get("author", ""), e.get("created_at", "")])

    # ---------------- مشاهده ----------------
    def _view(self):
        row = self._selected_row()
        if not row:
            ToastNotification(self, "ابتدا یک تجربه را انتخاب کنید", "info")
            return
        win = tk.Toplevel(self)
        win.title(f"تجربه #{row['id']} — {row.get('title', '')}")
        win.geometry("560x520")
        win.configure(bg=COLORS["bg_card"])
        win.grab_set()

        tk.Label(win, text=row.get("title", ""), font=FONTS["heading"],
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 wraplength=520).pack(padx=16, pady=(16, 4))
        info = (f"دسته: {row.get('category', '')}   |   تجهیز: {row.get('eq_name') or '-'}   |   "
                f"ثبت‌کننده: {row.get('author', '')}   |   تاریخ: {row.get('created_at', '')}")
        tk.Label(win, text=info, font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], wraplength=520).pack(padx=16)

        def _section(label, value):
            tk.Label(win, text=label, font=FONTS["body_bold"], bg=COLORS["bg_card"],
                     fg=COLORS["accent"], anchor="e").pack(fill="x", padx=16, pady=(10, 0))
            txt = tk.Text(win, font=FONTS["body"], bg=COLORS["bg_input"],
                         fg=COLORS["text_primary"], relief="flat", height=4, wrap="word")
            txt.pack(fill="x", padx=16, pady=(2, 0))
            txt.insert("1.0", value or "-")
            txt.configure(state="disabled")

        _section("شرح مشکل:", row.get("problem"))
        _section("راه‌حل / اقدام انجام‌شده:", row.get("solution"))
        _section("نکته برای دفعات بعد:", row.get("tips"))
        if row.get("tags"):
            tk.Label(win, text=f"برچسب‌ها: {row['tags']}", font=FONTS["small"],
                     bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(padx=16, pady=(8, 12))

    # ---------------- ویرایش ----------------
    def _edit(self):
        row = self._selected_row()
        if not row:
            ToastNotification(self, "ابتدا یک تجربه را انتخاب کنید", "info")
            return
        if not (self.is_admin or row.get("author") == self.username):
            ToastNotification(self, "فقط ثبت‌کننده یا مدیر مجاز است", "error")
            return
        self._edit_id = row["id"]
        self.form_title_lbl.configure(text=f"✏️  ویرایش تجربه #{row['id']}")
        self.f_title.set(row.get("title", ""))
        self.f_category.set(row.get("category") or CATEGORIES[0])
        self.f_eq.set(row.get("eq_name") or "")
        self.f_wo_ref.set(row.get("work_order_ref") or "")
        self.problem_txt.delete("1.0", "end"); self.problem_txt.insert("1.0", row.get("problem") or "")
        self.solution_txt.delete("1.0", "end"); self.solution_txt.insert("1.0", row.get("solution") or "")
        self.tips_txt.delete("1.0", "end"); self.tips_txt.insert("1.0", row.get("tips") or "")
        self.f_tags.set(row.get("tags") or "")

    # ---------------- حذف ----------------
    def _delete(self):
        row = self._selected_row()
        if not row:
            ToastNotification(self, "ابتدا یک تجربه را انتخاب کنید", "info")
            return
        if not (self.is_admin or row.get("author") == self.username):
            ToastNotification(self, "فقط ثبت‌کننده یا مدیر مجاز است", "error")
            return
        if not messagebox.askyesno("حذف تجربه", f"تجربه «{row.get('title')}» حذف شود؟", parent=self):
            return

        def work():
            try:
                api_client_ext.exp_delete(row["id"])
                self.after(0, lambda: ToastNotification(self, "حذف شد", "success"))
                self.after(0, self.refresh)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))

        threading.Thread(target=work, daemon=True).start()

    # ---------------- ابزار ----------------
    def _selected_row(self):
        sel = self.tree.get_selected_values()
        if not sel:
            return None
        for e in self._rows:
            if str(e["id"]) == str(sel[0]):
                return e
        return None
