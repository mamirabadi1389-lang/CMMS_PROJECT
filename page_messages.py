# page_messages.py
import threading
import tkinter as tk
from tkinter import ttk
import api_client
from styles import COLORS, FONTS
from widgets import StyledTreeview, FormField, IconButton, ToastNotification

KINDS = ["درخواست", "پیام", "گزارش خرابی", "درخواست قطعه"]
STATUSES = ["جدید", "در حال بررسی", "انجام شد", "رد شد"]
MSG_STATUS_COLORS = {
    "جدید": "#f59e0b",
    "در حال بررسی": "#4f8cff",
    "انجام شد": "#2fbf71",
    "رد شد": "#ef4444",
}


class MessagesPage(tk.Frame):
    def __init__(self, parent, app=None):
        super().__init__(parent, bg=COLORS["bg_dark"])
        self.app = app
        self._rows = []

        # تشخیص نقش کاربر (ادمین یا عادی)
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
        tk.Label(hdr, text="📨 پیام‌ها و درخواست‌ها", font=FONTS["heading"],
                 bg=COLORS["bg_dark"], fg=COLORS["text_primary"]).pack(side="right")
        IconButton(hdr, text="بروزرسانی", icon="🔄", command=self.refresh,
                   color=COLORS["bg_card"], fg=COLORS["text_primary"],
                   width=90).pack(side="left")

        body = tk.Frame(self, bg=COLORS["bg_dark"])
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ---------- کارت ارسال پیام (سمت راست) ----------
        form_card = tk.Frame(body, bg=COLORS["bg_card"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
        form_card.pack(side="right", fill="y", padx=(0, 12))
        form_card.configure(width=340)
        form_card.pack_propagate(False)

        tk.Label(form_card, text="✉️  ارسال پیام جدید", font=FONTS["heading"],
                 bg=COLORS["bg_card"], fg=COLORS["accent"]).pack(fill="x", padx=16, pady=(16, 8))

        self.f_subject = FormField(form_card, "موضوع", "entry", required=True)
        self.f_subject.pack(fill="x", padx=16)

        self.f_kind = FormField(form_card, "نوع", "combobox", options=KINDS)
        self.f_kind.set(KINDS[0])
        self.f_kind.pack(fill="x", padx=16, pady=(10, 0))

        self.f_body = FormField(form_card, "متن پیام", "text", required=True)
        self.f_body.pack(fill="x", padx=16, pady=(10, 0))

        IconButton(form_card, text="ارسال به سرور", icon="📤",
                   command=self._send, color=COLORS["green"]).pack(pady=16)

        # ---------- کارت لیست پیام‌ها (سمت چپ) ----------
        list_card = tk.Frame(body, bg=COLORS["bg_dark"])
        list_card.pack(side="right", fill="both", expand=True)

        cols = ["id", "subject", "kind", "sender", "status", "date", "reply"]
        heads = ["#", "موضوع", "نوع", "فرستنده", "وضعیت", "تاریخ", "پاسخ ادمین"]
        self.tree = StyledTreeview(list_card, cols, heads)
        self.tree.pack(fill="both", expand=True)
        for st, clr in MSG_STATUS_COLORS.items():
            self.tree.tree.tag_configure(f"st_{st}", foreground=clr)

        btns = tk.Frame(list_card, bg=COLORS["bg_dark"])
        btns.pack(fill="x", pady=(10, 0))
        IconButton(btns, text="مشاهده", icon="👁", command=self._view,
                   color=COLORS["bg_card"], fg=COLORS["text_primary"],
                   width=90).pack(side="right", padx=(8, 0))
        if self.is_admin:
            IconButton(btns, text="تغییر وضعیت", icon="✔", command=self._change_status,
                       color=COLORS["accent"], width=110).pack(side="right", padx=8)

        self.refresh()

    # ---------------- ارسال ----------------
    def _send(self):
        subject = self.f_subject.get().strip()
        body_txt = self.f_body.get().strip()
        kind = self.f_kind.get().strip() or "درخواست"
        if not subject or not body_txt:
            ToastNotification(self, "موضوع و متن پیام الزامی است", "error")
            return

        def work():
            try:
                api_client.send_message(subject=subject, body=body_txt, kind=kind)
                self.after(0, lambda: ToastNotification(self, "پیام با موفقیت ارسال شد", "success"))
                self.after(0, self._clear_form)
                self.after(0, self.refresh)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: ToastNotification(self, f"ارسال ناموفق: {err}", "error"))

        threading.Thread(target=work, daemon=True).start()

    def _clear_form(self):
        self.f_subject.set("")
        self.f_kind.set(KINDS[0])
        self.f_body.set("")

    # ---------------- لیست ----------------
    def refresh(self):
        def load():
            try:
                rows = api_client.get_messages()
            except Exception as e:
                err = str(e)
                self._rows = []
                self.after(0, lambda: ToastNotification(self, f"خطا در دریافت پیام‌ها: {err}", "error"))
                return
            self._rows = rows
            self.after(0, self._render)

        threading.Thread(target=load, daemon=True).start()

    def _render(self):
        self.tree.clear()
        for m in self._rows:
            st = m.get("status") or ""
            tags = (f"st_{st}",) if st in MSG_STATUS_COLORS else ()
            self.tree.insert(
                [m["id"], m.get("subject", ""), m.get("kind", ""),
                 m.get("sender", ""), st, m.get("created_at", ""), m.get("reply") or "—"],
                tags=tags)

    # ---------------- مشاهده ----------------
    def _view(self):
        row = self._selected_row()
        if not row:
            ToastNotification(self, "ابتدا یک پیام را انتخاب کنید", "info")
            return
        win = tk.Toplevel(self)
        win.title(f"پیام #{row['id']}")
        win.geometry("480x430")
        win.configure(bg=COLORS["bg_card"])
        win.grab_set()
        tk.Label(win, text=row.get("subject", ""), font=FONTS["heading"],
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 wraplength=440).pack(padx=16, pady=(16, 4))
        info = (f"فرستنده: {row.get('sender', '')}   |   "
                f"نوع: {row.get('kind', '')}   |   وضعیت: {row.get('status', '')}")
        tk.Label(win, text=info, font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"]).pack(padx=16)
        txt = tk.Text(win, font=FONTS["body"], bg=COLORS["bg_input"],
                      fg=COLORS["text_primary"], relief="flat",
                      height=9, wrap="word")
        txt.pack(fill="both", expand=True, padx=16, pady=10)
        txt.insert("1.0", row.get("body", ""))
        txt.configure(state="disabled")
        if row.get("reply"):
            tk.Label(win, text=f"💬 پاسخ ادمین: {row['reply']}", font=FONTS["body"],
                     bg=COLORS["bg_card"], fg=COLORS["green"],
                     wraplength=440).pack(padx=16, pady=(0, 12))

    # ---------------- تغییر وضعیت (فقط ادمین) ----------------
    def _change_status(self):
        row = self._selected_row()
        if not row:
            ToastNotification(self, "ابتدا یک پیام را انتخاب کنید", "info")
            return
        win = tk.Toplevel(self)
        win.title(f"تغییر وضعیت پیام #{row['id']}")
        win.geometry("400x310")
        win.configure(bg=COLORS["bg_card"])
        win.grab_set()

        tk.Label(win, text=f"پیام #{row['id']} — {row.get('subject', '')}",
                 font=FONTS["body_bold"], bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"], wraplength=360).pack(pady=(16, 8))
        tk.Label(win, text="وضعیت جدید:", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack()
        cb = ttk.Combobox(win, values=STATUSES, state="readonly",
                          font=FONTS["body"], justify="center")
        cb.set(row.get("status") if row.get("status") in STATUSES else STATUSES[0])
        cb.pack(pady=4, ipady=3)

        tk.Label(win, text="پاسخ / توضیح (اختیاری):", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(pady=(10, 0))
        ent = tk.Entry(win, font=FONTS["body"], bg=COLORS["bg_input"],
                       fg=COLORS["text_primary"], justify="center",
                       insertbackground=COLORS["accent"])
        ent.pack(fill="x", padx=30, ipady=5, pady=4)

        def save():
            try:
                api_client.update_message(int(row["id"]),
                                          status=cb.get(), reply=ent.get().strip())
                win.destroy()
                ToastNotification(self, "بروزرسانی شد", "success")
                self.refresh()
            except Exception as e:
                ToastNotification(self, f"خطا: {e}", "error")

        IconButton(win, text="ذخیره", icon="💾", command=save,
                   color=COLORS["green"]).pack(pady=14)

    # ---------------- ابزار ----------------
    def _selected_row(self):
        sel = self.tree.get_selected_values()
        if not sel:
            return None
        for m in self._rows:
            if str(m["id"]) == str(sel[0]):
                return m
        return None