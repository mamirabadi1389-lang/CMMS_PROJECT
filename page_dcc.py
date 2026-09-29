# page_dcc.py — DCC: منبع اطلاعاتی/اسناد فنی تجهیزات سازمان
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import database as db
import api_client
import api_client_ext
from styles import COLORS, FONTS
from widgets import StyledTreeview, FormField, IconButton, ToastNotification

CATEGORIES = ["دیتاشیت", "مانوال", "نقشه فنی", "گواهی/استاندارد", "گزارش", "سایر"]


class DCCPage(tk.Frame):
    def __init__(self, parent, app=None):
        super().__init__(parent, bg=COLORS["bg_dark"])
        self.app = app
        self._rows = []
        self._picked_file = None

        user = api_client.current_user or {}
        if not user:
            try:
                api_client.current_user = api_client.whoami()
                user = api_client.current_user
            except Exception:
                user = {}
        self.is_admin = user.get("role") == "admin"

        # ---------- هدر ----------
        hdr = tk.Frame(self, bg=COLORS["bg_dark"])
        hdr.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(hdr, text="🗂️ DCC — منبع اطلاعاتی تجهیزات سازمان", font=FONTS["heading"],
                 bg=COLORS["bg_dark"], fg=COLORS["text_primary"]).pack(side="right")
        IconButton(hdr, text="بروزرسانی", icon="🔄", command=self.refresh,
                   color=COLORS["bg_card"], fg=COLORS["text_primary"],
                   width=90).pack(side="left")

        body = tk.Frame(self, bg=COLORS["bg_dark"])
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ---------- کارت آپلود (سمت راست) ----------
        form_card = tk.Frame(body, bg=COLORS["bg_card"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
        form_card.pack(side="right", fill="y", padx=(0, 12))
        form_card.configure(width=340)
        form_card.pack_propagate(False)

        tk.Label(form_card, text="📤  افزودن سند جدید", font=FONTS["heading"],
                 bg=COLORS["bg_card"], fg=COLORS["accent"]).pack(fill="x", padx=16, pady=(16, 8))

        self.f_title = FormField(form_card, "عنوان سند", "entry", required=True)
        self.f_title.pack(fill="x", padx=16)

        self.f_category = FormField(form_card, "دسته‌بندی", "combobox", options=CATEGORIES)
        self.f_category.set(CATEGORIES[0])
        self.f_category.pack(fill="x", padx=16, pady=(10, 0))

        # نام تجهیز — قابل انتخاب یا نوشتن آزاد (مشابه بخش دستور کار)
        eq_fr = tk.Frame(form_card, bg=COLORS["bg_card"])
        eq_fr.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(eq_fr, text="تجهیز مرتبط", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"], anchor="w").pack(fill="x")
        equip_names = [r["name"] for r in db.fetch_all("SELECT name FROM equipment ORDER BY name")]
        self.f_eq = ttk.Combobox(eq_fr, values=["عمومی (سازمانی)"] + equip_names,
                                 font=FONTS["body"], state="normal")
        self.f_eq.set("عمومی (سازمانی)")
        self.f_eq.pack(fill="x", ipady=3)

        self.f_desc = FormField(form_card, "توضیحات", "text")
        self.f_desc.pack(fill="x", padx=16, pady=(10, 0))

        file_fr = tk.Frame(form_card, bg=COLORS["bg_card"])
        file_fr.pack(fill="x", padx=16, pady=(10, 0))
        self.file_lbl = tk.Label(file_fr, text="فایلی انتخاب نشده", font=FONTS["small"],
                                 bg=COLORS["bg_card"], fg=COLORS["text_muted"], anchor="e")
        self.file_lbl.pack(fill="x")
        IconButton(file_fr, text="انتخاب فایل", icon="📎", command=self._pick_file,
                  color=COLORS["bg_card"], fg=COLORS["text_primary"], width=110).pack(pady=4)

        IconButton(form_card, text="آپلود به سرور", icon="📤",
                  command=self._upload, color=COLORS["green"]).pack(pady=16)

        # ---------- کارت لیست اسناد (سمت چپ) ----------
        list_card = tk.Frame(body, bg=COLORS["bg_dark"])
        list_card.pack(side="right", fill="both", expand=True)

        search_fr = tk.Frame(list_card, bg=COLORS["bg_dark"])
        search_fr.pack(fill="x", pady=(0, 8))
        self.search_entry = tk.Entry(search_fr, font=FONTS["body"], bg=COLORS["bg_input"],
                                     fg=COLORS["text_primary"], relief="flat",
                                     insertbackground=COLORS["accent"], justify="right")
        self.search_entry.pack(side="right", fill="x", expand=True, ipady=5, padx=(8, 0))
        self.search_entry.bind("<Return>", lambda e: self.refresh())
        IconButton(search_fr, text="جستجو", icon="🔎", command=self.refresh,
                  color=COLORS["accent_dim"], fg=COLORS["accent"], width=90).pack(side="right")

        cols = ["id", "title", "category", "eq_name", "uploaded_by", "created_at"]
        heads = ["#", "عنوان", "دسته", "تجهیز", "آپلودکننده", "تاریخ"]
        self.tree = StyledTreeview(list_card, cols, heads)
        self.tree.pack(fill="both", expand=True)

        btns = tk.Frame(list_card, bg=COLORS["bg_dark"])
        btns.pack(fill="x", pady=(10, 0))
        IconButton(btns, text="دانلود", icon="⬇️", command=self._download,
                  color=COLORS["accent"], width=100).pack(side="right", padx=(8, 0))
        IconButton(btns, text="حذف", icon="🗑", command=self._delete,
                  color=COLORS["red"], fg="#fff", width=90).pack(side="right", padx=8)

        self.refresh()

    # ---------------- انتخاب فایل ----------------
    def _pick_file(self):
        path = filedialog.askopenfilename(title="انتخاب فایل سند")
        if path:
            self._picked_file = path
            self.file_lbl.configure(text=os.path.basename(path))

    # ---------------- آپلود ----------------
    def _upload(self):
        title = self.f_title.get().strip()
        if not title:
            ToastNotification(self, "عنوان سند الزامی است", "error")
            return
        category = self.f_category.get().strip() or CATEGORIES[-1]
        eq_name = self.f_eq.get().strip()
        if eq_name == "عمومی (سازمانی)":
            eq_name = ""
        description = self.f_desc.get().strip()
        file_path = self._picked_file

        def work():
            try:
                api_client_ext.dcc_upload(file_path, title, category, eq_name, description)
                self.after(0, lambda: ToastNotification(self, "سند با موفقیت آپلود شد", "success"))
                self.after(0, self._clear_form)
                self.after(0, self.refresh)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"آپلود ناموفق: {err}", "error"))

        threading.Thread(target=work, daemon=True).start()

    def _clear_form(self):
        self.f_title.set("")
        self.f_category.set(CATEGORIES[0])
        self.f_eq.set("عمومی (سازمانی)")
        self.f_desc.set("")
        self._picked_file = None
        self.file_lbl.configure(text="فایلی انتخاب نشده")

    # ---------------- لیست ----------------
    def refresh(self):
        search = self.search_entry.get().strip() if hasattr(self, "search_entry") else ""

        def load():
            try:
                rows = api_client_ext.dcc_list(q=search or None)
            except Exception as e:
                err = str(e)
                self._rows = []
                self.after(0, lambda: ToastNotification(self, f"خطا در دریافت اسناد: {err}", "error"))
                return
            self._rows = rows
            self.after(0, self._render)

        threading.Thread(target=load, daemon=True).start()

    def _render(self):
        self.tree.clear()
        for d in self._rows:
            self.tree.insert(
                [d["id"], d.get("title", ""), d.get("category", ""),
                 d.get("eq_name") or "عمومی", d.get("uploaded_by", ""),
                 d.get("created_at", "")])

    # ---------------- دانلود ----------------
    def _download(self):
        row = self._selected_row()
        if not row:
            ToastNotification(self, "ابتدا یک سند را انتخاب کنید", "info")
            return
        default_name = row.get("file_name") or f"document_{row['id']}"
        save_path = filedialog.asksaveasfilename(initialfile=default_name)
        if not save_path:
            return

        def work():
            try:
                api_client_ext.dcc_download(row["id"], save_path)
                self.after(0, lambda: ToastNotification(self, "دانلود انجام شد", "success"))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))

        threading.Thread(target=work, daemon=True).start()

    # ---------------- حذف ----------------
    def _delete(self):
        row = self._selected_row()
        if not row:
            ToastNotification(self, "ابتدا یک سند را انتخاب کنید", "info")
            return
        if not (self.is_admin or row.get("uploaded_by") == (api_client.current_user or {}).get("username")):
            ToastNotification(self, "فقط آپلودکننده یا مدیر مجاز است", "error")
            return
        if not messagebox.askyesno("حذف سند", f"سند «{row.get('title')}» حذف شود؟", parent=self):
            return

        def work():
            try:
                api_client_ext.dcc_delete(row["id"])
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
        for d in self._rows:
            if str(d["id"]) == str(sel[0]):
                return d
        return None
