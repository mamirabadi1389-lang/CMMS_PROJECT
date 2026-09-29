import tkinter as tk
from tkinter import messagebox
import json, os, sys
import database as db
from styles import COLORS, FONTS, THEMES, CURRENT_THEME, save_theme
from widgets import SectionTitle, IconButton, FormField, ToastNotification

import api_client

class SettingsPage(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self.is_admin = (api_client.current_user or {}).get("role") == "admin"
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        canvas = tk.Canvas(self, bg=COLORS["bg_dark"], highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                          bg=COLORS["bg_dark"], troughcolor=COLORS["bg_card"])
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        self.content = tk.Frame(canvas, bg=COLORS["bg_dark"])
        win = canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        hdr = tk.Frame(self.content, bg=COLORS["bg_header"])
        hdr.pack(fill="x", padx=20, pady=(16, 12))
        tk.Label(hdr, text="تنظیمات سیستم", font=FONTS["title"],
                 bg=COLORS["bg_header"], fg=COLORS["text_primary"]).pack(side="right", pady=12)

        self._section_card(self.content, "🎨  انتخاب تم ظاهری", self._build_theme_selector)
        if self.is_admin:
            self._section_card(self.content, "⚙️  تنظیمات عمومی", self._build_general)
            self._section_card(self.content, "🗄️  اطلاعات پایگاه داده", self._build_db_info)
        self._section_card(self.content, "ℹ️  درباره برنامه", self._build_about)

    def _section_card(self, parent, title, builder):
        card = tk.Frame(parent, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="x", padx=20, pady=8)
        hdr = tk.Frame(card, bg=COLORS["bg_header"])
        hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=FONTS["subhead"],
                 bg=COLORS["bg_header"], fg=COLORS["accent"],
                 padx=16, pady=10).pack(side="right")
        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=16, pady=12)
        builder(inner)

    # ═══════════════════════════════════════════════════════════════════════
    #  THEME SELECTOR
    # ═══════════════════════════════════════════════════════════════════════
    def _build_theme_selector(self, parent):
        info = tk.Frame(parent, bg=COLORS["bg_card"])
        info.pack(fill="x", pady=(0, 10))
        tk.Label(info, text=f"تم فعلی: {THEMES[CURRENT_THEME]['label']}",
                 font=FONTS["body_bold"], bg=COLORS["bg_card"],
                 fg=COLORS["accent"]).pack(side="right")
        tk.Label(info, text="با انتخاب تم جدید، برنامه پس از تأیید ری‌استارت می‌شود",
                 font=FONTS["small"], bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"]).pack(side="left")

        dark_lbl = tk.Label(parent, text="🌙  تم‌های تاریک صنعتی",
                            font=FONTS["body_bold"], bg=COLORS["bg_card"],
                            fg=COLORS["text_secondary"], anchor="e")
        dark_lbl.pack(fill="x", pady=(4, 6))
        self._theme_grid(parent, [k for k, v in THEMES.items() if v.get("type", "dark") == "dark"])

        light_lbl = tk.Label(parent, text="☀️  تم‌های روشن",
                             font=FONTS["body_bold"], bg=COLORS["bg_card"],
                             fg=COLORS["text_secondary"], anchor="e")
        light_lbl.pack(fill="x", pady=(14, 6))
        self._theme_grid(parent, [k for k, v in THEMES.items() if v.get("type", "dark") == "light"])

    def _theme_grid(self, parent, keys):
        grid = tk.Frame(parent, bg=COLORS["bg_card"])
        grid.pack(fill="x")
        row = None
        for idx, key in enumerate(keys):
            if idx % 3 == 0:
                row = tk.Frame(grid, bg=COLORS["bg_card"])
                row.pack(fill="x", pady=3)
            self._theme_card(row, key, THEMES[key])

    def _theme_card(self, parent, key, theme):
        bg_c, accent, card_bg = theme["preview"]
        tc = theme["colors"]
        is_active = (key == CURRENT_THEME)
        border_color = accent if is_active else COLORS["border"]

        outer = tk.Frame(parent, bg=border_color, padx=1, pady=1, cursor="hand2")
        outer.pack(side="right", fill="x", expand=True, padx=3)

        inner = tk.Frame(outer, bg=card_bg, padx=8, pady=6)
        inner.pack(fill="both", expand=True)

        strip = tk.Frame(inner, bg=card_bg)
        strip.pack(fill="x", pady=(0, 4))
        for c in theme["preview"]:
            swatch = tk.Frame(strip, bg=c, width=20, height=20)
            swatch.pack(side="right", padx=1)

        lbl_font = FONTS["body_bold"] if is_active else FONTS["small"]
        lbl_color = accent if is_active else tc["text_primary"]
        lbl = tk.Label(inner, text=theme["label"], font=lbl_font,
                       bg=card_bg, fg=lbl_color)
        lbl.pack(anchor="e")

        badge_text = "فعال" if is_active else ("تاریک" if theme.get("type", "dark") == "dark" else "روشن")
        if is_active:
            badge_bg = accent
            badge_fg = "#FFFFFF"
        else:
            badge_bg = tc["bg_input"]
            badge_fg = tc["text_muted"]
        badge = tk.Label(inner, text=badge_text, font=("Segoe UI", 7),
                         bg=badge_bg, fg=badge_fg, padx=6, pady=1)
        badge.pack(anchor="e", pady=(2, 0))

        def _on_enter(e, o=outer, ac=accent):
            if not is_active:
                o.configure(bg=ac)
        def _on_leave(e, o=outer, bc=border_color):
            if not is_active:
                o.configure(bg=bc)
        def _on_click(k=key, t=theme):
            if k == CURRENT_THEME:
                ToastNotification(self, "این تم در حال حاضر فعال است", "info")
                return
            if messagebox.askyesno("تغییر تم",
                    f"تم «{t['label']}» انتخاب شود؟\n\n"
                    "برنامه برای اعمال تغییرات ری‌استارت خواهد شد."):
                save_theme(k)
                ToastNotification(self, "تم ذخیره شد — در حال ری‌استارت...", "success")
                self._restart_app()

        for w in [outer, inner, lbl, badge]:
            w.bind("<Enter>", _on_enter)
            w.bind("<Leave>", _on_leave)
            w.bind("<Button-1>", lambda e: _on_click())

    def _restart_app(self):
        messagebox.showinfo("بازراه‌اندازی لازم است",
            "تم ذخیره شد.\n\nلطفاً برنامه را کامل ببندید و دوباره باز کنید تا تغییرات اعمال شود.")

    # ═══════════════════════════════════════════════════════════════════════
    #  GENERAL
    # ═══════════════════════════════════════════════════════════════════════
    def _build_general(self, parent):
        self.f_factory = FormField(parent, "نام کارخانه / سازمان")
        self.f_factory.pack(fill="x", pady=4)
        self.f_hours = FormField(parent, "ساعات کاری روزانه (برای محاسبه MTBF)")
        self.f_hours.pack(fill="x", pady=4)
        btn_row = tk.Frame(parent, bg=COLORS["bg_card"])
        btn_row.pack(fill="x", pady=8)
        IconButton(btn_row, "ذخیره تنظیمات", "💾", self._save_settings,
                   color=COLORS["accent"]).pack(side="right")

    def _save_settings(self):
        factory = self.f_factory.get().strip()
        hours = self.f_hours.get().strip()
        if factory:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('factory_name', ?)", (factory,))
        if hours:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('working_hours_per_day', ?)", (hours,))
        ToastNotification(self, "تنظیمات ذخیره شد", "success")

    # ═══════════════════════════════════════════════════════════════════════
    #  DB INFO
    # ═══════════════════════════════════════════════════════════════════════
    def _build_db_info(self, parent):
        db_path = db.DB_PATH
        size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        size_kb = size_bytes / 1024
        counts = {
            "تجهیزات": db.fetch_one("SELECT COUNT(*) as c FROM equipment")["c"],
            "دستور کارها": db.fetch_one("SELECT COUNT(*) as c FROM work_orders")["c"],
            "برنامه‌های PM": db.fetch_one("SELECT COUNT(*) as c FROM pm_schedules WHERE active=1")["c"],
            "قطعات یدکی": db.fetch_one("SELECT COUNT(*) as c FROM spare_parts")["c"],
        }
        info_grid = tk.Frame(parent, bg=COLORS["bg_card"])
        info_grid.pack(fill="x")
        path_row = tk.Frame(info_grid, bg=COLORS["bg_input"])
        path_row.pack(fill="x", pady=2)
        tk.Label(path_row, text="مسیر فایل:", font=FONTS["body_bold"],
                 bg=COLORS["bg_input"], fg=COLORS["text_secondary"],
                 padx=12, pady=6).pack(side="right")
        tk.Label(path_row, text=db_path, font=FONTS["mono"],
                 bg=COLORS["bg_input"], fg=COLORS["cyan"],
                 padx=12, pady=6).pack(side="left")
        size_row = tk.Frame(info_grid, bg=COLORS["bg_card"])
        size_row.pack(fill="x", pady=2)
        tk.Label(size_row, text="حجم فایل:", font=FONTS["body_bold"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                 padx=12, pady=4).pack(side="right")
        tk.Label(size_row, text=f"{size_kb:.1f} KB", font=FONTS["body"],
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 padx=12).pack(side="left")
        tk.Frame(info_grid, bg=COLORS["border"], height=1).pack(fill="x", pady=8)
        cnt_row = tk.Frame(info_grid, bg=COLORS["bg_card"])
        cnt_row.pack(fill="x")
        for label, val in counts.items():
            sf = tk.Frame(cnt_row, bg=COLORS["bg_input"])
            sf.pack(side="right", fill="x", expand=True, padx=4, pady=2)
            tk.Label(sf, text=str(val), font=FONTS["heading"],
                     bg=COLORS["bg_input"], fg=COLORS["accent"]).pack(pady=(8, 2))
            tk.Label(sf, text=label, font=FONTS["small"],
                     bg=COLORS["bg_input"], fg=COLORS["text_muted"]).pack(pady=(0, 8))
        btn_row = tk.Frame(parent, bg=COLORS["bg_card"])
        btn_row.pack(fill="x", pady=8)
        IconButton(btn_row, "پشتیبان‌گیری", "💾", self._backup_db,
                   color=COLORS["blue"]).pack(side="right", padx=4)
        IconButton(btn_row, "بازنشانی داده‌های نمونه", "🔄", self._reset_demo,
                   color=COLORS["red_dim"]).pack(side="left", padx=4)

    def _backup_db(self):
        from tkinter import filedialog
        import shutil
        from datetime import date
        path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite DB", "*.db"), ("All", "*.*")],
            initialfile=f"cmms_backup_{date.today().isoformat()}.db"
        )
        if not path:
            return
        try:
            shutil.copy2(db.DB_PATH, path)
            ToastNotification(self, "پشتیبان‌گیری انجام شد", "success")
        except Exception as ex:
            messagebox.showerror("خطا", str(ex))

    def _reset_demo(self):
        if messagebox.askyesno("هشدار",
                               "تمام داده‌های فعلی پاک می‌شوند و داده‌های نمونه جایگزین می‌شوند.\nآیا مطمئن هستید؟",
                               icon="warning"):
            try:
                os.remove(db.DB_PATH)
                db.init_database()
                ToastNotification(self, "داده‌های نمونه بارگذاری شدند", "info")
                self.app.refresh_all()
            except Exception as ex:
                messagebox.showerror("خطا", str(ex))

    # ═══════════════════════════════════════════════════════════════════════
    #  ABOUT
    # ═══════════════════════════════════════════════════════════════════════
    def _build_about(self, parent):
        about_items = [
            ("نام نرم‌افزار", "سیستم مدیریت نگهداری و تعمیرات (CMMS)"),
            ("نسخه", "1.2.0 — Multi-Theme"),
            ("پایگاه داده", "SQLite (محلی)"),
            ("زبان برنامه‌نویسی", "Python 3 + Tkinter"),
            ("تعداد تم‌ها", f"{len(THEMES)} تم (5 تاریک + 5 روشن)"),
            ("اپراتورهای پشتیبانی‌شده", "مکانیک  |  برق  |  تاسیسات"),
            ("انواع دستور کار", "PM (پیشگیرانه)  |  EM (اضطراری)"),
            ("شاخص‌های کلیدی", "MTTR  |  MTBF  |  OEE"),
        ]
        for lbl, val in about_items:
            row = tk.Frame(parent, bg=COLORS["bg_card"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=val, font=FONTS["body"],
                     bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                     anchor="w").pack(side="left", padx=12)
            tk.Label(row, text=lbl, font=FONTS["body_bold"],
                     bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                     width=24, anchor="e").pack(side="right", padx=12)
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", pady=10)
        tk.Label(parent, text="رنگ‌بندی اپراتورها:", font=FONTS["body_bold"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(anchor="e", padx=12)
        leg_row = tk.Frame(parent, bg=COLORS["bg_card"])
        leg_row.pack(fill="x", padx=12, pady=4)
        from styles import OPERATOR_COLORS
        for op, color in OPERATOR_COLORS.items():
            sf = tk.Frame(leg_row, bg=COLORS["bg_input"])
            sf.pack(side="right", padx=6, pady=2)
            tk.Label(sf, text="  ", bg=color, width=2).pack(side="right")
            tk.Label(sf, text=op, font=FONTS["body_bold"],
                     bg=COLORS["bg_input"], fg=color, padx=10, pady=6).pack(side="right")

        self._add_brand_logo(parent)

    def _resource_path(self, *parts):
        """مسیر فایل رو چه در حالت اجرای عادی و چه در exe ساخته‌شده با PyInstaller پیدا می‌کند."""
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, *parts)

    @staticmethod
    def _hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    def _add_brand_logo(self, parent):
        """لوگوی برند رو خیلی کوچک و کم‌رنگ، بدون سروصدا، پایین «درباره برنامه» نشون می‌ده."""
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return

        logo_path = self._resource_path("static", "logo_emblem.png")
        if not os.path.exists(logo_path):
            return

        try:
            img = Image.open(logo_path).convert("RGBA")
            target_h = 70
            target_w = max(1, int(img.width * (target_h / img.height)))
            img = img.resize((target_w, target_h), Image.LANCZOS)

            # کم‌رنگ کردن (کاهش opacity) با کاهش کانال alpha
            alpha = img.split()[3].point(lambda a: int(a * 0.35))
            img.putalpha(alpha)

            bg_rgb = self._hex_to_rgb(COLORS["bg_card"])
            bg = Image.new("RGBA", img.size, bg_rgb + (255,))
            composited = Image.alpha_composite(bg, img).convert("RGB")

            self._brand_logo_img = ImageTk.PhotoImage(composited)
        except Exception:
            return

        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", pady=(14, 8))
        logo_row = tk.Frame(parent, bg=COLORS["bg_card"])
        logo_row.pack(fill="x", pady=(0, 7))
        tk.Label(logo_row, image=self._brand_logo_img,
                 bg=COLORS["bg_card"]).pack(pady=2)

    def _load_settings(self):
    # این ویجت‌ها فقط برای ادمین ساخته می‌شوند
        if not self.is_admin:
            return
        factory = db.fetch_one("SELECT value FROM settings WHERE key='factory_name'")
        hours = db.fetch_one("SELECT value FROM settings WHERE key='working_hours_per_day'")
        if factory and hasattr(self, "f_factory"):
            self.f_factory.set(factory["value"])
        if hours and hasattr(self, "f_hours"):
            self.f_hours.set(hours["value"])