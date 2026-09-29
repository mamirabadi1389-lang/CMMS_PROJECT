# main.py — CMMS
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import traceback
import time
import startup
import api_client
import discovery
from page_messages import MessagesPage
from styles import *
# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logger
logger.install_requests_logging()

def _log_dir():
    base = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CMMS"
    )
    os.makedirs(base, exist_ok=True)
    return base


LOG_PATH = os.path.join(_log_dir(), "error.log")


def _log_and_show_error(exc_type, exc_value, exc_tb):
    import logger
    try:
        logger.log.error("خطای غیرمنتظره:\n" + "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)))
    except Exception:
        pass
    try:
        messagebox.showerror(
            "خطای برنامه",
            f"یک خطای غیرمنتظره رخ داد.\n\n{exc_value}\n\n"
            f"جزئیات کامل در فایل زیر ذخیره شد:\n"
            f"{os.path.join(logger._logs_dir(), 'cmms.log')}")
    except Exception:
        pass

sys.excepthook = _log_and_show_error

import database as db
from styles import COLORS, FONTS, SIDEBAR_MENU, OPERATOR_COLORS


class SidebarButton(tk.Frame):
    """Animated sidebar navigation button — با بج شمارنده (مثل پیام‌رسان‌ها)."""
    def __init__(self, parent, icon, label, command, active=False, **kwargs):
        super().__init__(parent, bg=COLORS["bg_sidebar"], cursor="hand2", **kwargs)
        self._active = active
        self._hover = False
        self._command = command
        self._icon = icon
        self._label = label
        self._badge_count = 0

        # ── بج شمارنده ── همیشه پک است تا جای خودش ثابت بماند؛
        # وقتی عددی نیست هم‌رنگ پس‌زمینه می‌شود و دیده نمی‌شود
        self._badge = tk.Label(self, text="", font=("Segoe UI", 9, "bold"),
                               bg=COLORS["bg_sidebar"], fg=COLORS["bg_sidebar"],
                               padx=7, pady=1)
        self._badge.pack(side="right", padx=(0, 6))

        self._indicator = tk.Frame(self, bg=COLORS["bg_sidebar"], width=3)
        self._indicator.pack(side="left", fill="y")

        self._icon_lbl = tk.Label(self, text=icon, font=("Segoe UI Emoji", 15),
                                  bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"],
                                  width=3)
        self._icon_lbl.pack(side="left", padx=(6, 2), pady=12)

        self._text_lbl = tk.Label(self, text=label, font=FONTS["sidebar"],
                                  bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"],
                                  anchor="w")
        self._text_lbl.pack(side="left", fill="x", expand=True, padx=(0, 12))

        if active:
            self._set_active()
        else:
            self._set_inactive()

        for widget in [self, self._icon_lbl, self._text_lbl, self._indicator, self._badge]:
            widget.bind("<Button-1>", lambda e: self._on_click())
            widget.bind("<Enter>", lambda e: self._on_hover())
            widget.bind("<Leave>", lambda e: self._on_leave())

    # ── بج ──────────────────────────────────────────────
    def set_badge(self, count):
        """عدد شمارنده؛ ۰ یا None یعنی بدون بج"""
        try:
            self._badge_count = max(0, int(count or 0))
        except (TypeError, ValueError):
            self._badge_count = 0
        self._sync_badge()

    def _sync_badge(self):
        if self._badge_count > 0:
            text = str(self._badge_count) if self._badge_count < 100 else "99+"
            self._badge.configure(text=text, bg=COLORS["red"], fg="#FFFFFF")
        else:
            bg = COLORS["bg_hover"] if (self._active or self._hover) else COLORS["bg_sidebar"]
            self._badge.configure(text="", bg=bg, fg=bg)

    def _on_click(self):
        if self._command:
            self._command()

    def _on_hover(self):
        self._hover = True
        if not self._active:
            self._icon_lbl.configure(bg=COLORS["bg_hover"])
            self._text_lbl.configure(bg=COLORS["bg_hover"])
            self.configure(bg=COLORS["bg_hover"])
        self._sync_badge()

    def _on_leave(self):
        self._hover = False
        if not self._active:
            self._set_inactive()
        else:
            self._sync_badge()

    def _set_active(self):
        self._active = True
        self._indicator.configure(bg=COLORS["accent"])
        self._icon_lbl.configure(bg=COLORS["bg_hover"], fg=COLORS["accent"])
        self._text_lbl.configure(bg=COLORS["bg_hover"], fg=COLORS["text_primary"],
                                 font=(*FONTS["sidebar"][:2], "bold"))
        self.configure(bg=COLORS["bg_hover"])
        self._sync_badge()

    def _set_inactive(self):
        self._active = False
        self._indicator.configure(bg=COLORS["bg_sidebar"])
        self._icon_lbl.configure(bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"])
        self._text_lbl.configure(bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"],
                                 font=FONTS["sidebar"])
        self.configure(bg=COLORS["bg_sidebar"])
        self._sync_badge()

    def set_active(self, active: bool):
        if active:
            self._set_active()
        else:
            self._set_inactive()

class CMMSApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("CMMS — سیستم مدیریت نگهداری و تعمیرات")
        self.geometry("1280x780")
        self.minsize(1100, 680)
        self.configure(bg=COLORS["bg_dark"])
        self.option_add("*TCombobox*Listbox.background", COLORS["bg_input"])
        self.option_add("*TCombobox*Listbox.foreground", COLORS["text_primary"])
        self.option_add("*TCombobox*Listbox.selectBackground", COLORS["accent_dim"])
        self.option_add("*TCombobox*Listbox.selectForeground", COLORS["text_primary"])
        self.option_add("*TCombobox*Listbox.font", FONTS["body"])
        # Try to set icon (Windows)
        db.init_database()

        self._build_layout()

        self._pages = {}
        self._current_page = None
        self._current_page_name = None
        self._nav_buttons = {}
        self._build_nav()

        self._badge_count_prev = None
        self.update_wo_badges(initial=True)

        # Show dashboard on launch
        self.show_page("داشبورد")
        self._sync_job = self.after(5000, self._auto_sync)
    # ── اسکرول منوی سایدبار ────────────────────────────────────────────
    def _on_nav_frame_configure(self, event=None):
        self._nav_canvas.configure(scrollregion=self._nav_canvas.bbox("all"))

    def _on_nav_canvas_configure(self, event):
        self._nav_canvas.itemconfigure(self._nav_window, width=event.width)

    def _bind_nav_wheel(self, event=None):
        self.bind_all("<MouseWheel>", self._on_nav_mousewheel)
        self.bind_all("<Button-4>", self._on_nav_mousewheel)
        self.bind_all("<Button-5>", self._on_nav_mousewheel)

    def _unbind_nav_wheel(self, event=None):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _on_nav_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            self._nav_canvas.yview_scroll(-2, "units")
        elif getattr(event, "num", None) == 5:
            self._nav_canvas.yview_scroll(2, "units")
        else:
            self._nav_canvas.yview_scroll(int(-event.delta / 120), "units")

    def report_callback_exception(self, exc_type, exc_value, exc_tb):
        if not self.winfo_exists():
            # برنامه در حال بسته شدن است — فقط لاگ، بدون پیام
            try:
                import logger
                logger.log.error("[shutdown] " + "".join(
                    traceback.format_exception(exc_type, exc_value, exc_tb)))
            except Exception:
                pass
            return
        _log_and_show_error(exc_type, exc_value, exc_tb)

    def _build_layout(self):
        self._main = tk.Frame(self, bg=COLORS["bg_dark"])
        self._main.pack(fill="both", expand=True)

        self._sidebar = tk.Frame(self._main, bg=COLORS["bg_sidebar"], width=220)
        self._sidebar.pack(side="right", fill="y")
        self._sidebar.pack_propagate(False)

        logo_frame = tk.Frame(self._sidebar, bg=COLORS["bg_sidebar"],
                              highlightbackground=COLORS["border"],
                              highlightthickness=0)
        logo_frame.pack(fill="x")

        # Accent top bar
        tk.Frame(logo_frame, bg=COLORS["accent"], height=3).pack(fill="x")

        logo_inner = tk.Frame(logo_frame, bg=COLORS["bg_sidebar"])
        logo_inner.pack(fill="x", padx=16, pady=14)
        tk.Label(logo_inner, text="⚙️", font=("Segoe UI Emoji", 28),
                 bg=COLORS["bg_sidebar"], fg=COLORS["accent"]).pack(side="right")
        title_f = tk.Frame(logo_inner, bg=COLORS["bg_sidebar"])
        title_f.pack(side="right", fill="x", expand=True, padx=(0, 8))
        tk.Label(title_f, text="CMMS", font=("Segoe UI", 18, "bold"),
                 bg=COLORS["bg_sidebar"], fg=COLORS["text_primary"]).pack(anchor="e")
        tk.Label(title_f, text="نگهداری و تعمیرات", font=("Tahoma", 11),
                 bg=COLORS["bg_sidebar"], fg=COLORS["text_muted"]).pack(anchor="e")

        # Separator
        tk.Frame(self._sidebar, bg=COLORS["border"], height=1).pack(fill="x")

        # Nav section label
        tk.Label(self._sidebar, text="  منوی اصلی", font=FONTS["small"],
                 bg=COLORS["bg_sidebar"], fg=COLORS["text_muted"],
                 anchor="e").pack(fill="x", pady=(10, 4), padx=8)

        # Nav container (اسکرول‌دار)
        nav_wrap = tk.Frame(self._sidebar, bg=COLORS["bg_sidebar"])
        nav_wrap.pack(fill="both", expand=True)

        self._nav_canvas = tk.Canvas(nav_wrap, bg=COLORS["bg_sidebar"],
                                     highlightthickness=0, bd=0)
        self._nav_scrollbar = tk.Scrollbar(nav_wrap, orient="vertical",
                                           command=self._nav_canvas.yview,
                                           bg=COLORS["bg_sidebar"],
                                           troughcolor=COLORS["bg_sidebar"],
                                           activebackground=COLORS["accent"],
                                           highlightthickness=0, bd=0,
                                           width=10)
        self._nav_canvas.configure(yscrollcommand=self._nav_scrollbar.set)
        self._nav_scrollbar.pack(side="left", fill="y")
        self._nav_canvas.pack(side="left", fill="both", expand=True)

        self._nav_frame = tk.Frame(self._nav_canvas, bg=COLORS["bg_sidebar"])
        self._nav_window = self._nav_canvas.create_window(
            (0, 0), window=self._nav_frame, anchor="nw")

        self._nav_frame.bind("<Configure>", self._on_nav_frame_configure)
        self._nav_canvas.bind("<Configure>", self._on_nav_canvas_configure)
        self._nav_canvas.bind("<Enter>", self._bind_nav_wheel)
        self._nav_canvas.bind("<Leave>", self._unbind_nav_wheel)

        # Operator status section at bottom
        tk.Frame(self._sidebar, bg=COLORS["border"], height=1).pack(fill="x", side="bottom")
        op_frame = tk.Frame(self._sidebar, bg=COLORS["bg_sidebar"])
        op_frame.pack(side="bottom", fill="x", padx=12, pady=8)
        tk.Label(op_frame, text="اپراتورها", font=FONTS["small"],
                 bg=COLORS["bg_sidebar"], fg=COLORS["text_muted"],
                 anchor="e").pack(fill="x")
        op_dots = tk.Frame(op_frame, bg=COLORS["bg_sidebar"])
        op_dots.pack(fill="x", pady=4)
        for op, color in OPERATOR_COLORS.items():
            sf = tk.Frame(op_dots, bg=COLORS["bg_sidebar"])
            sf.pack(side="right", fill="x", expand=True)
            tk.Label(sf, text="●", font=FONTS["small"],
                     bg=COLORS["bg_sidebar"], fg=color).pack()
            tk.Label(sf, text=op, font=("Tahoma", 8),
                     bg=COLORS["bg_sidebar"], fg=COLORS["text_muted"]).pack()

        # ── Content area ───────────────────────────────────────────────
        self._content = tk.Frame(self._main, bg=COLORS["bg_dark"])
        self._content.pack(side="right", fill="both", expand=True)

        # Top status bar
        self._statusbar = tk.Frame(self._content, bg=COLORS["bg_header"], height=32)
        self._statusbar.pack(fill="x", side="bottom")
        self._statusbar.pack_propagate(False)
        self._status_lbl = tk.Label(self._statusbar, text="آماده",
                                    font=FONTS["small"], bg=COLORS["bg_header"],
                                    fg=COLORS["text_muted"])
        self._status_lbl.pack(side="left", padx=12, pady=6)
                # ── نشانگر بروزرسانی خودکار (poll سه‌ثانیه‌ای) ──
        self._sync_lbl = tk.Label(self._statusbar, text="🔄 در حال اتصال...",
                                  font=FONTS["small"], bg=COLORS["bg_header"],
                                  fg=COLORS["text_muted"])
        self._sync_lbl.pack(side="left", padx=4, pady=6)
        factory_name = db.fetch_one("SELECT value FROM settings WHERE key='factory_name'")
        factory_str = factory_name["value"] if factory_name else "کارخانه"
        tk.Label(self._statusbar, text=f"🏭  {factory_str}",
                 font=FONTS["small"], bg=COLORS["bg_header"],
                 fg=COLORS["text_secondary"]).pack(side="right", padx=12, pady=6)

        # Page container
        self._page_container = tk.Frame(self._content, bg=COLORS["bg_dark"])
        self._page_container.pack(fill="both", expand=True)

    def _build_nav(self):
        items = list(SIDEBAR_MENU)
        # اگر «پیام‌ها» توی styles.py تعریف نشده بود، خودکار اضافه کن
        if not any(label == "پیام‌ها" for _, label in items):
            items.append(("📨", "پیام‌ها"))

        is_admin = (api_client.current_user or {}).get("role") == "admin"
        # منوی مدیریت کاربران فقط برای ادمین
        if is_admin and not any(label == "مدیریت کاربران" for _, label in items):
            items.append(("👥", "مدیریت کاربران"))
                    # ثبت دستور کار فقط برای مدیر
        if not is_admin:
            items = [it for it in items if it[1] != "دستور کار جدید"]

        

        for icon, label in items:
            btn = SidebarButton(
                self._nav_frame, icon, label,
                command=lambda lbl=label: self.show_page(lbl)
            )
            btn.pack(fill="x")
            self._nav_buttons[label] = btn
    def show_page(self, page_name: str):
        # Deactivate all buttons
        for lbl, btn in self._nav_buttons.items():
            btn.set_active(lbl == page_name)

        # Lazy-load pages
        if page_name not in self._pages:
            self._pages[page_name] = self._create_page(page_name)

        # Hide current
        if self._current_page:
            self._current_page.pack_forget()

        # Show new
        page = self._pages[page_name]
        page.pack(fill="both", expand=True)
        self._current_page = page
        self._current_page_name = page_name
        self._set_status(f"صفحه: {page_name}")

        # Refresh on navigation
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception:
                pass

        # ← جدید: هنگام ورود به «دستور کار جدید»، لیست تکنسین‌ها از سرور
        # تازه می‌شود — مستقیماً متدِ موجودِ خودِ صفحه صدا زده می‌شود،
        # پس به متد refresh وابسته نیست
        if page_name == "دستور کار جدید" and hasattr(page, "_load_tech_names"):
            try:
                page._load_tech_names()
            except Exception:
                pass

        # باز کردن لیست دستور کارها = همه را دیدم → بج صفر می‌شود
        if page_name == "لیست دستور کارها":
            self.on_wo_list_viewed()
    def _badge_me(self):
        return ((api_client.current_user or {}).get("username") or "").strip()

    def _settings_get(self, key, default=""):
        try:
            row = db.fetch_one("SELECT value FROM settings WHERE key=?", (key,))
            return row["value"] if row else default
        except Exception:
            return default

    def _settings_set(self, key, value):
        try:
            db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                       (key, str(value)))
        except Exception:
            pass

    def _ensure_badge_tables(self):
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS wo_seen (
                username TEXT NOT NULL,
                order_number TEXT NOT NULL,
                PRIMARY KEY (username, order_number))""", ())
        except Exception:
            pass

    def _badge_ready(self, me):
        """بعد از اولین همگام‌سازیِ موفق این کاربر فعال می‌شود"""
        return self._settings_get(f"wo_badge_ready_{me}", "") == "1"

    def _mark_wo_seen(self):
        """همهٔ دستور کارهای فعلیِ این کاربر «دیده‌شده» (مثل باز کردن چت)"""
        me = self._badge_me()
        if not me:
            return
        self._ensure_badge_tables()
        try:
            import wo_sync
            wo_sync.ensure_local()
        except Exception:
            pass
        try:
            conn = db.get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""INSERT OR IGNORE INTO wo_seen (username, order_number)
                               SELECT ?, order_number FROM work_orders
                               WHERE technician_username=?
                                 AND (created_by IS NULL OR created_by != ?)
                                 AND order_number IS NOT NULL""", (me, me, me))
                # پاکسازی ردیف‌های کهنه (دستور کارهایی که دیگر وجود ندارند)
                cur.execute("""DELETE FROM wo_seen WHERE username=?
                               AND order_number NOT IN
                                   (SELECT order_number FROM work_orders
                                    WHERE order_number IS NOT NULL)""", (me,))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    def on_wo_list_viewed(self):
        """باز کردن/بروزرسانی لیست → همه دیده‌شده → بج صفر"""
        self._mark_wo_seen()
        self.update_wo_badges(initial=True)

    def update_wo_badges(self, initial=False):
        me = self._badge_me()
        is_admin = (api_client.current_user or {}).get("role") == "admin"
        count = 0
        try:
            import wo_sync
            wo_sync.ensure_local()
        except Exception:
            pass
        self._ensure_badge_tables()

        try:
            if is_admin:
                row = db.fetch_one(
                    "SELECT COUNT(*) n FROM work_orders WHERE report_status='ارسال شده'")
                count = int(row["n"] or 0) if row else 0
            elif me and self._badge_ready(me):
                row = db.fetch_one("""
                    SELECT COUNT(*) n FROM work_orders wo
                    WHERE wo.technician_username=?
                      AND (wo.created_by IS NULL OR wo.created_by != ?)
                      AND wo.order_number IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM wo_seen s
                                      WHERE s.username=? AND s.order_number=wo.order_number)""",
                    (me, me, me))
                count = int(row["n"] or 0) if row else 0
        except Exception:
            count = 0

        btn = self._nav_buttons.get("لیست دستور کارها")
        if btn is not None:
            try:
                btn.set_badge(count)
            except Exception:
                pass

        prev = getattr(self, "_badge_count_prev", None)
        viewing_list = (getattr(self, "_current_page_name", "") == "لیست دستور کارها")
        if not initial and prev is not None and count > prev and not viewing_list:
            try:
                from widgets import ToastNotification
                logger.log.info(f"بج جدید: {count} (قبلی: {prev}) — "
                    f"{'مدیر/گزارش' if is_admin else 'تکنسین/دستور کار'}")
                if is_admin:
                    ToastNotification(self, f"📨 {count - prev} گزارش کار جدید در انتظار بررسی شماست", "info")
                else:
                    ToastNotification(self, f"📋 {count - prev} دستور کار جدید برای شما ثبت شد", "info")
            except Exception:
                pass
        self._badge_count_prev = count
    def _create_page(self, name: str) -> tk.Frame:
        from page_dashboard import DashboardPage
        from page_workorders import NewWorkOrderPage, WorkOrderListPage
        from page_equipment import EquipmentPage
        from page_pm_parts import PMSchedulePage, SparePartsPage
        from page_reports import ReportsPage
        from page_settings import SettingsPage
        from page_analysis import DataAnalysisPage
        from page_users import UsersPage
        # --- افزوده شد: OEE / DCC / ثبت تجربیات ---
        from page_oee import OEEPage
        from page_dcc import DCCPage
        from page_knowledge import KnowledgePage
        creators = {
            "داشبورد":          lambda: DashboardPage(self._page_container, self),
            "دستور کار جدید":   lambda: NewWorkOrderPage(self._page_container, self),
            "لیست دستور کارها": lambda: WorkOrderListPage(self._page_container, self),
            "تجهیزات":          lambda: EquipmentPage(self._page_container, self),
            "برنامه PM":        lambda: PMSchedulePage(self._page_container, self),
            "قطعات یدکی":       lambda: SparePartsPage(self._page_container, self),
            "گزارش‌ها":          lambda: ReportsPage(self._page_container, self),
            "تحلیل داده ها":    lambda: DataAnalysisPage(self._page_container, self),
            "پیام‌ها":           lambda: MessagesPage(self._page_container, self),
            "مدیریت کاربران":   lambda: UsersPage(self._page_container, self),
            # --- افزوده شد: OEE / DCC / ثبت تجربیات ---
            "OEE":              lambda: OEEPage(self._page_container, self),
            "DCC":              lambda: DCCPage(self._page_container, self),
            "ثبت تجربیات":      lambda: KnowledgePage(self._page_container, self),
            "تنظیمات":          lambda: SettingsPage(self._page_container, self),
        }
        creator = creators.get(name)
        if creator:
            return creator()
        # Fallback
        frame = tk.Frame(self._page_container, bg=COLORS["bg_dark"])
        tk.Label(frame, text=f"صفحه «{name}» در دست توسعه لطفا صبر کنید تا صفحه ساخته شود",
                 font=FONTS["heading"], bg=COLORS["bg_dark"],
                 fg=COLORS["text_muted"]).pack(expand=True)
        return frame

    def refresh_dashboard(self):
        """Called after any data change to update dashboard KPIs."""
        if "داشبورد" in self._pages:
            self._pages["داشبورد"].refresh()

    def refresh_all(self):
        """Full refresh of all loaded pages."""
        for name, page in self._pages.items():
            if hasattr(page, "refresh"):
                try:
                    page.refresh()
                except Exception:
                    pass
        
    def _set_status(self, msg: str):
        self._status_lbl.configure(text=msg)
    def destroy(self):
        # لغو تایمر همگام‌سازی تا بعد از بسته شدن اجرا نشود
        try:
            if getattr(self, "_sync_job", None):
                self.after_cancel(self._sync_job)
        except Exception:
            pass
        super().destroy()

    def _auto_sync(self):
        if not self.winfo_exists():
            return

        # ۱) تجهیزات / PM / قطعات — فقط امضای تغییرات چک می‌شود
        if not getattr(self, "_equip_polling", False):
            self._equip_polling = True
            def eq_done(status, result):
                def _ui():
                    self._equip_polling = False
                    try:
                        if status == "error":
                            self._sync_lbl.configure(text="⚠️ بدون اتصال", fg=COLORS["red"])
                        else:
                            self._sync_lbl.configure(text=f"🔄 {time.strftime('%H:%M:%S')}",
                                                     fg=COLORS["text_muted"])
                    except Exception:
                        pass
                    if status == "changed" and result:
                        try:
                            self._on_equip_data_changed(result)
                        except Exception:
                            pass
                try:
                    self.after(0, _ui)
                except Exception:
                    self._equip_polling = False
            try:
                import equip_sync
                equip_sync.pull_if_changed_async(eq_done)
            except Exception:
                self._equip_polling = False

        # ۲) دستور کارها — همان poll سبک
        if not getattr(self, "_wo_polling", False):
            self._wo_polling = True
            def wo_done(status):
                def _ui():
                    self._wo_polling = False
                    if status == "changed":
                        try:
                            self._on_wo_data_changed()
                        except Exception:
                            pass
                try:
                    self.after(0, _ui)
                except Exception:
                    self._wo_polling = False
            try:
                import wo_sync
                wo_sync.pull_if_changed_async(wo_done)
            except Exception:
                self._wo_polling = False

        # ۳) فال‌بک ۶۰ ثانیه‌ای: pull کامل (برای تغییراتی که در امضا نمی‌آیند
        #    یا سرورِ قدیمی که /sync/meta ندارد)
        self._full_tick = getattr(self, "_full_tick", 0) + 1
        if self._full_tick >= 20:          # 20 × 3s ≈ 60s
            self._full_tick = 0
            def eq_fb(result):
                def _ui():
                    if result:
                        try:
                            self._on_equip_data_changed(result)
                        except Exception:
                            pass
                try:
                    self.after(0, _ui)
                except Exception:
                    pass
            def wo_fb(ok):
                if not ok:
                    return
                try:
                    self.after(0, self._on_wo_data_changed)
                except Exception:
                    pass
            try:
                import equip_sync
                equip_sync.pull_async(eq_fb)
            except Exception:
                pass
            try:
                import wo_sync
                wo_sync.pull_async(wo_fb)
            except Exception:
                pass

        self._sync_job = self.after(3000, self._auto_sync)

    def _on_equip_data_changed(self, result):
        """وقتی تجهیزات / برنامه‌های PM / قطعات روی سرور تغییر کنند"""
        try:
            import equip_sync
            from widgets import ToastNotification
            me = (api_client.current_user or {}).get("username") or "-"
            equip_sync.notify_new_items(self, result, me, ToastNotification)
        except Exception:
            pass
        for name in ("تجهیزات", "برنامه PM", "قطعات یدکی"):
            pg = self._pages.get(name)
            if pg is not None and hasattr(pg, "refresh"):
                try:
                    pg.refresh()
                except Exception:
                    pass

    def _on_wo_data_changed(self):
        """وقتی دستور کارها روی سرور تغییر کنند"""
        try:
            self.refresh_dashboard()
        except Exception:
            pass
        try:
            me = self._badge_me()
            if getattr(self, "_current_page_name", "") == "لیست دستور کارها":
                # کاربر همین الان لیست را باز دارد → مثل چتِ باز، دیده‌شده
                self._mark_wo_seen()
                if me:
                    self._settings_set(f"wo_badge_ready_{me}", "1")
            elif me and not self._badge_ready(me):
                # اولین همگام‌سازی موفق: موجودی فعلی «دیده‌شده» فرض می‌شود
                # (تا ۴۵ دستور کار قدیمی seed، بج عجیب نسازند)
                self._mark_wo_seen()
                self._settings_set(f"wo_badge_ready_{me}", "1")
            self.update_wo_badges()
        except Exception:
            pass
        # داده‌ها همین الان با pull_if_changed آپدیت شده‌اند؛ پس فقط جدولِ
        # صفحه را دوباره پر می‌کنیم — pull دوباره لازم نیست
        # (pull دوباره → _after_pull → پاک‌شدن ناگهانی بج!)
        lp = self._pages.get("لیست دستور کارها")
        if lp is not None:
            try:
                lp._reload_local()
            except Exception:
                pass
            try:
                lp._load_users()
            except Exception:
                pass
# ─── Splash screen ─────────────────────────────────────────────────────────────

class SplashScreen(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(bg=COLORS["bg_dark"])

        w, h = 480, 300
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.attributes("-topmost", True)

        # Top accent
        tk.Frame(self, bg=COLORS["accent"], height=4).pack(fill="x")

        content = tk.Frame(self, bg=COLORS["bg_dark"])
        content.pack(fill="both", expand=True, padx=40, pady=30)

        tk.Label(content, text="⚙️", font=("Segoe UI Emoji", 48),
                 bg=COLORS["bg_dark"], fg=COLORS["accent"]).pack(pady=(0, 8))
        tk.Label(content, text="CMMS", font=("Segoe UI", 32, "bold"),
                 bg=COLORS["bg_dark"], fg=COLORS["text_primary"]).pack()
        tk.Label(content, text="سیستم مدیریت نگهداری و تعمیرات",
                 font=("Tahoma", 12), bg=COLORS["bg_dark"],
                 fg=COLORS["text_secondary"]).pack(pady=4)
        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x", padx=40)

        self._progress_bg = tk.Frame(self, bg=COLORS["border"], height=4)
        self._progress_bg.pack(fill="x", padx=40, pady=12)
        self._progress_bar = tk.Frame(self._progress_bg, bg=COLORS["accent"], height=4, width=0)
        self._progress_bar.place(x=0, y=0)

        self._status = tk.Label(self, text="در حال بارگذاری...",
                                font=FONTS["small"], bg=COLORS["bg_dark"],
                                fg=COLORS["text_muted"])
        self._status.pack()

        tk.Frame(self, bg=COLORS["accent"], height=2).pack(fill="x", side="bottom")
        self._animate(0)

    def _animate(self, pct):
        if pct > 100:
            return
        total_w = self._progress_bg.winfo_width()
        bar_w = int(total_w * pct / 100)
        self._progress_bar.configure(width=max(bar_w, 0))

        msgs = {0: "راه‌اندازی...", 30: "اتصال به پایگاه داده...",
                60: "بارگذاری تجهیزات...", 85: "آماده‌سازی رابط...", 100: "آماده!"}
        if pct in msgs:
            self._status.configure(text=msgs[pct])

        if pct < 100:
            self.after(18, lambda: self._animate(pct + 2))


# ─── اتصال به سرور ─────────────────────────────────────────────────────────────

def ensure_connection(cfg):
    """چک اتصال به سرور — اگه نشد، دیالوگ تلاش مجدد نشون بده"""
    import requests
    while True:
        try:
            requests.get(f"{api_client.SERVER}/health", timeout=3)
            return True
        except Exception:
            pass
        # اگه کلاینتی، دوباره سرور رو توی شبکه پیدا کن (مثلاً بعد از ری‌استارت مودم)
        if cfg.get("role") == "client":
            ip = discovery.discover_server(timeout=6)
            if ip:
                api_client.set_server(f"http://{ip}:8000")
                try:
                    requests.get(f"{api_client.SERVER}/health", timeout=3)
                    return True
                except Exception:
                    pass
        if not messagebox.askretrycancel(
                "خطای اتصال",
                "ارتباط با سرور برقرار نشد!\n"
                "مطمئن شو کامپیوتر سرور روشن است و وای‌فای/کابل وصل است.\n\n"
                "دوباره تلاش کنم؟"):
            return False


# ─── راه‌اندازی ────────────────────────────────────────────────────────────────

def launch_app():
    """اسپلش + پنجره اصلی"""
    root = tk.Tk()
    root.withdraw()

    splash = SplashScreen(root)
    splash.update()

    def _launch():
        splash.destroy()
        root.destroy()
        try:
            app = CMMSApp()
            # Center window
            app.update_idletasks()
            sw = app.winfo_screenwidth()
            sh = app.winfo_screenheight()
            w, h = 1280, 780
            app.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            app.mainloop()
        except Exception:
            _log_and_show_error(*sys.exc_info())

    root.after(2200, _launch)
    root.mainloop()


def main():
    # ۱) بار اول: ویزارد انتخاب سرور/کلاینت
    cfg = startup.ensure_config()
    if cfg is None:
        sys.exit()

    # ۲) راه‌اندازی سرویس‌ها (سرور: دیتابیس + API + discovery)
    startup.start_services(cfg)

    # ۳) چک اتصال (اگه نشد، دیالوگ تلاش مجدد)
    if not ensure_connection(cfg):
        sys.exit()

    # ۴) صفحه ورود
    user = startup.ensure_login()
    if user is None:
        sys.exit()

    # ۵) اسپلش + پنجره اصلی
    launch_app()


if __name__ == "__main__":
    main()