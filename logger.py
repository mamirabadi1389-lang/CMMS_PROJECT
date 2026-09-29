# logger.py
"""
سیستم لاگ‌گیری مرکزی CMMS
────────────────────────────────────────────
فایل‌ها در %LOCALAPPDATA%\\CMMS\\logs :
  cmms.log  ← رخدادهای برنامه + خطاهای غیرمنتظره
  sync.log  ← عملیات همگام‌سازی (wo_sync / equip_sync)
  api.log   ← خطاهای ارتباط با سرور (فقط خطاها — شلوغ نمی‌شود)

برای عیب‌یابی، DEBUG_MODE را True کنید تا درخواست‌های موفق HTTP هم ثبت شوند.
هر فایل حداکثر ۲MB و ۵ نسخه‌ی قدیمی نگه داشته می‌شود (چرخش خودکار).
"""
import os
import logging
from logging.handlers import RotatingFileHandler

DEBUG_MODE = False
MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 5


def _logs_dir():
    base = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CMMS", "logs")
    os.makedirs(base, exist_ok=True)
    return base


def _make(name, filename, level):
    lg = logging.getLogger(name)
    if lg.handlers:
        return lg
    logging.raiseExceptions = False   # خطای خودِ لاگ، برنامه را نیندازد
    lg.setLevel(logging.DEBUG)
    try:
        h = RotatingFileHandler(os.path.join(_logs_dir(), filename),
                                maxBytes=MAX_BYTES, backupCount=BACKUPS,
                                encoding="utf-8")
        h.setLevel(level)
        h.setFormatter(logging.Formatter(
            "%(asctime)s  [%(levelname)s]  %(message)s", "%Y-%m-%d %H:%M:%S"))
        lg.addHandler(h)
        lg.propagate = False
    except Exception:
        pass
    return lg


log  = _make("cmms.app",  "cmms.log",  logging.INFO)                      # رخدادها
sync = _make("cmms.sync", "sync.log",  logging.INFO)                      # همگام‌سازی
api  = _make("cmms.api",  "api.log",
             logging.INFO if DEBUG_MODE else logging.ERROR)              # HTTP


def install_requests_logging():
    """ثبت خودکار همه‌ی خطاهای HTTP در api.log — بدون دست زدن به api_client.py"""
    try:
        import requests
        if getattr(requests.api.request, "_cmms_logged", False):
            return
        _orig = requests.api.request

        def _logged(method, url, *a, **kw):
            try:
                resp = _orig(method, url, *a, **kw)
                if resp.status_code >= 400:
                    api.error(f"{method.upper()} {url} → {resp.status_code} {resp.text[:200]}")
                elif DEBUG_MODE:
                    api.info(f"{method.upper()} {url} → {resp.status_code} "
                             f"({resp.elapsed.total_seconds():.2f}s)")
                return resp
            except Exception as e:
                api.error(f"{method.upper()} {url} → {type(e).__name__}: {e}")
                raise

        _logged._cmms_logged = True
        requests.api.request = _logged
    except Exception:
        pass
