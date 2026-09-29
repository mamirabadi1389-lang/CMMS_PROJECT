# startup.py
import sys, os, json, threading
import tkinter as tk
from tkinter import messagebox

import discovery
import server as srv
import api_client
import logger

if getattr(sys, "frozen", False) or "__compiled__" in globals():
    # زیر Nuitka onefile نباید به sys.executable تکیه کرد (به پوشه‌ی موقت
    # استخراج‌شده اشاره می‌کند که بعد از هر اجرا پاک می‌شود)
    BASE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CMMS")
    os.makedirs(BASE_DIR, exist_ok=True)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
API_PORT = 8000

from styles import COLORS
BG, CARD, ACCENT, GREEN = (COLORS["bg_dark"], COLORS["bg_card"],
                           COLORS["accent"], COLORS["green"])
TXT, MUTED = COLORS["text_primary"], COLORS["text_muted"]


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class SetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("راه‌اندازی CMMS")
        self.geometry("520x420")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        self._found_ip = None
        self._page_role()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _page_role(self):
        self._clear()
        tk.Label(self, text="راه‌اندازی اولیه", font=("Tahoma", 18, "bold"),
                 bg=BG, fg=TXT).pack(pady=(40, 6))
        tk.Label(self, text="این سیستم چه نقشی دارد؟", font=("Tahoma", 11),
                 bg=BG, fg=MUTED).pack(pady=(0, 30))

        def role_btn(text, sub, color, cmd):
            f = tk.Frame(self, bg=color, cursor="hand2")
            f.pack(pady=10, ipadx=20)
            tk.Label(f, text=text, font=("Tahoma", 13, "bold"),
                     bg=color, fg="#fff").pack(padx=30, pady=(8, 0))
            tk.Label(f, text=sub, font=("Tahoma", 9),
                     bg=color, fg="#e6e6e6").pack(padx=30, pady=(0, 8))
            for w in [f] + list(f.winfo_children()):
                w.bind("<Button-1>", lambda e: cmd())

        role_btn("🖥  این سیستم، سرور اصلی است",
                 "دیتابیس اینجا ذخیره می‌شود (کامپیوتر ادمین)", GREEN,
                 lambda: self._finish({"role": "server"}))
        role_btn("💻  این سیستم، کلاینت است",
                 "به سرور وصل می‌شود (کاربر عادی)", ACCENT, self._page_client)

    def _page_client(self):
        self._clear()
        tk.Label(self, text="در حال جستجوی سرور...", font=("Tahoma", 14, "bold"),
                 bg=BG, fg=TXT).pack(pady=(80, 10))
        lbl = tk.Label(self, text="لطفاً چند لحظه صبر کنید",
                       font=("Tahoma", 10), bg=BG, fg=MUTED, justify="center")
        lbl.pack()

        mf = tk.Frame(self, bg=BG)
        mf.pack(pady=25)
        entry = tk.Entry(mf, font=("Tahoma", 11), width=16, bg=CARD, fg=TXT,
                         insertbackground=TXT, relief="flat", justify="center")
        entry.grid(row=0, column=1, padx=4, ipady=4)
        entry.insert(0, "192.168.1.")
        tk.Button(mf, text="اتصال دستی به این IP", font=("Tahoma", 10, "bold"),
                  bg=ACCENT, fg="#fff", relief="flat", cursor="hand2",
                  command=lambda: self._try_connect(entry.get().strip())
                  ).grid(row=0, column=0)

        back = tk.Label(self, text="→ بازگشت", font=("Tahoma", 9),
                        bg=BG, fg=MUTED, cursor="hand2")
        back.pack(side="bottom", pady=10)
        back.bind("<Button-1>", lambda e: self._page_role())

        import time
        threading.Thread(target=self._do_discover, daemon=True).start()
        self._poll(lbl, time.time())

    def _do_discover(self):
        self._found_ip = discovery.discover_server(timeout=6)

    def _poll(self, lbl, t0):
        import time
        if self._found_ip:
            self._found(self._found_ip)
        elif time.time() - t0 < 8 and not self.result:
            self.after(300, lambda: self._poll(lbl, t0))
        else:
            lbl.configure(text="سرور پیدا نشد!\nمطمئن شو سرور روشن است و کابل وصل است.\nمی‌توانی IP را دستی وارد کنی.",
                          fg="#ff6b6b")

    def _found(self, ip):
        if messagebox.askyesno("سرور پیدا شد",
                               f"سرور در این آدرس پیدا شد:\n{ip}\n\nاتصال برقرار شود؟",
                               parent=self):
            self._try_connect(ip)

    def _try_connect(self, ip):
        if not ip:
            return
        try:
            import requests
            r = requests.get(f"http://{ip}:{API_PORT}/health", timeout=3)
            if r.ok:
                self._finish({"role": "client", "server_ip": ip})
                return
        except Exception:
            pass
        messagebox.showerror("خطا", f"اتصال به {ip} ممکن نشد.", parent=self)

    def _finish(self, cfg):
        save_config(cfg)
        self.result = cfg
        self.destroy()


class LoginDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("ورود به سیستم")
        self.geometry("340x260")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        self.grab_set()

        tk.Label(self, text="🔐  ورود", font=("Tahoma", 16, "bold"),
                 bg=BG, fg=TXT).pack(pady=(24, 4))
        tk.Label(self, text="نام کاربری و رمز خود را وارد کنید",
                 font=("Tahoma", 9), bg=BG, fg=MUTED).pack(pady=(0, 14))

        self.u = tk.Entry(self, font=("Tahoma", 11), justify="center",
                          bg=CARD, fg=TXT, insertbackground=TXT, relief="flat")
        self.u.pack(ipady=5, ipadx=8)
        self.u.insert(0, "admin")

        self.p = tk.Entry(self, font=("Tahoma", 11), justify="center", show="●",
                          bg=CARD, fg=TXT, insertbackground=TXT, relief="flat")
        self.p.pack(ipady=5, ipadx=8, pady=(10, 0))

        tk.Button(self, text="ورود", font=("Tahoma", 11, "bold"),
                  bg=GREEN, fg="#fff", relief="flat", cursor="hand2",
                  command=self._do_login).pack(ipadx=30, ipady=4, pady=16)
        self.bind("<Return>", lambda e: self._do_login())
        self.u.focus_set()

    def _do_login(self):
        try:
            api_client.login(self.u.get().strip(), self.p.get())
            self.result = api_client.current_user
            self.destroy()
        except Exception:
            messagebox.showerror("خطا", "نام کاربری یا رمز عبور اشتباه است", parent=self)


def ensure_config():
    cfg = load_config()
    if cfg is not None:
        return cfg
    wiz = SetupWizard()
    wiz.mainloop()
    return wiz.result


def start_services(cfg):
    if cfg["role"] == "server":
        logger.log.info("راه‌اندازی به‌عنوان سرور اصلی")
        srv.init_db()
        import server_extra  # ثبت روت‌های DCC / تجربیات / equip / pm / spare-parts / sync-meta
        discovery.start_discovery_server()
        threading.Thread(target=srv.run_server, daemon=True).start()
        api_client.set_server(f"http://127.0.0.1:{API_PORT}")
    else:
        logger.log.info(f"راه‌اندازی به‌عنوان کلاینت — سرور: {cfg.get('server_ip')}")
        api_client.set_server(f"http://{cfg['server_ip']}:{API_PORT}")
    # نکته: equip_sync و wo_sync دیگر نیازی به راه‌اندازی جدا در استارتاپ ندارند —
    # خودشان از حلقه‌ی _auto_sync در main.py (هر ۳ ثانیه با poll سبک) صدا زده می‌شوند.


def ensure_login():
    if api_client.current_user:
        return api_client.current_user
    root = tk.Tk()
    root.withdraw()
    dlg = LoginDialog(root)
    root.wait_window(dlg)
    root.destroy()
    return dlg.result
