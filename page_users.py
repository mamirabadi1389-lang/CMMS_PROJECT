# page_users.py
import threading
import tkinter as tk
from tkinter import messagebox
import api_client
from styles import COLORS, FONTS
from widgets import StyledTreeview, FormField, IconButton, ToastNotification


class UsersPage(tk.Frame):
    def __init__(self, parent, app=None):
        super().__init__(parent, bg=COLORS["bg_dark"])
        self.app = app
        self._rows = []

        # ---------- هدر ----------
        hdr = tk.Frame(self, bg=COLORS["bg_dark"])
        hdr.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(hdr, text="👥 مدیریت کاربران", font=FONTS["heading"],
                 bg=COLORS["bg_dark"], fg=COLORS["text_primary"]).pack(side="right")
        IconButton(hdr, text="بروزرسانی", icon="🔄", command=self.refresh,
                   color=COLORS["bg_card"], fg=COLORS["text_primary"],
                   width=90).pack(side="left")

        body = tk.Frame(self, bg=COLORS["bg_dark"])
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ---------- فرم کاربر جدید (سمت راست) ----------
        form_card = tk.Frame(body, bg=COLORS["bg_card"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
        form_card.pack(side="right", fill="y", padx=(0, 12))
        form_card.configure(width=340)
        form_card.pack_propagate(False)

        tk.Label(form_card, text="➕  کاربر جدید", font=FONTS["heading"],
                 bg=COLORS["bg_card"], fg=COLORS["accent"]).pack(fill="x", padx=16, pady=(16, 8))

        self.f_user = FormField(form_card, "نام کاربری", "entry", required=True)
        self.f_user.pack(fill="x", padx=16)

        self.f_pass = FormField(form_card, "رمز عبور", "entry", required=True)
        self.f_pass.pack(fill="x", padx=16, pady=(10, 0))

        self.f_name = FormField(form_card, "نام و نام خانوادگی", "entry")
        self.f_name.pack(fill="x", padx=16, pady=(10, 0))

        self.f_role = FormField(form_card, "نقش", "combobox",
                                options=["کاربر عادی", "مدیر"])
        self.f_role.set("کاربر عادی")
        self.f_role.pack(fill="x", padx=16, pady=(10, 0))

        IconButton(form_card, text="ثبت کاربر", icon="💾",
                   command=self._add, color=COLORS["green"]).pack(pady=16)

        # ---------- لیست کاربران (سمت چپ) ----------
        list_card = tk.Frame(body, bg=COLORS["bg_dark"])
        list_card.pack(side="right", fill="both", expand=True)

        self.tree = StyledTreeview(list_card,
                                   ["id", "username", "full_name", "role"],
                                   ["#", "نام کاربری", "نام کامل", "نقش"])
        self.tree.pack(fill="both", expand=True)

        btns = tk.Frame(list_card, bg=COLORS["bg_dark"])
        btns.pack(fill="x", pady=(10, 0))
        IconButton(btns, text="حذف کاربر", icon="🗑", command=self._delete,
                   color=COLORS["red"], fg="#fff", width=110).pack(side="left")

        self.refresh()

    # ---------------- افزودن ----------------
        # ---------------- افزودن ----------------
    def _add(self):
        username = self.f_user.get().strip()
        password = self.f_pass.get().strip()
        full_name = self.f_name.get().strip() or username
        role = "admin" if self.f_role.get() == "مدیر" else "user"
        if not username or not password:
            ToastNotification(self, "نام کاربری و رمز الزامی است", "error")
            return

        def work():
            try:
                api_client.add_user(username, password, full_name, role)
                self.after(0, lambda: ToastNotification(self, "کاربر ثبت شد", "success"))
                self.after(0, self._clear)
                self.after(0, self.refresh)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))

        threading.Thread(target=work, daemon=True).start()

    # ---------------- لیست ----------------
    def refresh(self):
        def load():
            try:
                rows = api_client.get_users()
            except Exception as e:
                err = str(e)
                self._rows = []
                self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))
                return
            self._rows = rows
            self.after(0, self._render)

        threading.Thread(target=load, daemon=True).start()

    # ---------------- حذف ----------------
    def _delete(self):
        sel = self.tree.get_selected_values()
        if not sel:
            ToastNotification(self, "ابتدا یک کاربر را انتخاب کنید", "info")
            return
        uid = int(sel[0])
        uname = next((u["username"] for u in self._rows if u["id"] == uid), None)
        if uname == "admin":
            ToastNotification(self, "حساب اصلی ادمین قابل حذف نیست", "error")
            return
        if not messagebox.askyesno("حذف کاربر", f"کاربر «{uname}» حذف شود؟", parent=self):
            return

        def work():
            try:
                api_client.delete_user(uid)
                self.after(0, lambda: ToastNotification(self, "کاربر حذف شد", "success"))
                self.after(0, self.refresh)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"خطا: {err}", "error"))

        threading.Thread(target=work, daemon=True).start()
    def _clear(self):
        self.f_user.set("")
        self.f_pass.set("")
        self.f_name.set("")
        self.f_role.set("کاربر عادی")

    # ---------------- لیست ----------------
    

    def _render(self):
        self.tree.clear()
        for u in self._rows:
            role_fa = "مدیر سیستم" if u.get("role") == "admin" else "کاربر عادی"
            self.tree.insert([u["id"], u.get("username", ""),
                              u.get("full_name", ""), role_fa])

