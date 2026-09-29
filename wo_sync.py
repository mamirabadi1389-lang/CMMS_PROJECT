import threading
import database as db
import api_client
from logger import sync as synclog

_lock = threading.Lock()
_last_wo_sig = None


def _to_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def ensure_local():
    for col, typ in [("created_by","TEXT"),("eq_name","TEXT"),("location","TEXT"),
                     ("technician_username","TEXT"),("report_text","TEXT"),
                     ("report_submitted_at","TEXT"),("report_status","TEXT"),
                     ("report_rating","REAL"),("report_comment","TEXT")]:
        try:
            db.execute(f"ALTER TABLE work_orders ADD COLUMN {col} {typ}", ())
        except Exception:
            pass


def pull():
    global _last_wo_sig
    with _lock:
        ensure_local()
        sig = None
        try:
            import api_client_ext as _apx
            sig = _apx.sync_meta().get("wo")
        except Exception:
            pass
        server_rows = api_client.wo_list()

        have = {(r.get("order_number") or "") for r in server_rows}
        local_rows = db.fetch_all("SELECT * FROM work_orders")
        missing = [r for r in local_rows
                   if (r.get("order_number") or "") and r["order_number"] not in have]
        if missing:
            api_client.wo_migrate(missing)
            synclog.info(f"wo: migrate_up → {len(missing)} دستور کار محلی به سرور منتقل شد")
            server_rows = api_client.wo_list()

        eq_rows = db.fetch_all("SELECT id, name FROM equipment")
        valid_ids = {r["id"] for r in eq_rows}
        name_to_id = {r["name"]: r["id"] for r in eq_rows}

        db.execute("DELETE FROM work_orders", ())
        for r in server_rows:
            if not r.get("order_number"):
                continue
            eq_id = r.get("equipment_id")
            if eq_id not in valid_ids:
                eq_id = name_to_id.get(r.get("eq_name"))
            db.execute("""
                INSERT INTO work_orders
                (id, order_number, order_type, equipment_id, eq_name, location,
                 operator, description, work_date, start_time, end_time,
                 downtime_minutes, priority, status, root_cause, action_taken,
                 parts_used, technician_name, technician_username,
                 report_text, report_submitted_at, report_status,
                 report_rating, report_comment,
                 created_at, updated_at, created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r.get("id"), r.get("order_number"), r.get("order_type"),
                 eq_id, r.get("eq_name"), r.get("location"),
                 r.get("operator"), r.get("description"), r.get("work_date"),
                 r.get("start_time"), r.get("end_time"),
                 _to_int(r.get("downtime_minutes")),
                 r.get("priority") or "متوسط", r.get("status") or "باز",
                 r.get("root_cause"), r.get("action_taken"), r.get("parts_used"),
                 r.get("technician_name"), r.get("technician_username"),
                 r.get("report_text"), r.get("report_submitted_at"),
                 r.get("report_status"), r.get("report_rating"),
                 r.get("report_comment"),
                 r.get("created_at"), r.get("updated_at"), r.get("created_by")))
        if sig is not None:
            _last_wo_sig = sig
        synclog.info(f"wo: pull ok — {len(server_rows)} دستور کار دریافت شد")
        return len(server_rows)


def pull_quiet():
    try:
        return pull()
    except Exception as e:
        synclog.error(f"wo: pull failed: {e}")
        return None


def pull_if_changed():
    """فقط امضای سبک سرور را چک می‌کند؛ اگر تغییر کرده بود pull کامل انجام
    می‌شود. خروجی یکی از رشته‌های 'changed' / 'ok' / 'error' است.
    main.py این تابع را با یک آرگومان status صدا می‌زند (نه tuple)."""
    global _last_wo_sig
    sig = None
    try:
        import api_client_ext as _apx
        sig = _apx.sync_meta().get("wo")
    except Exception as e:
        synclog.error(f"wo: sync_meta failed: {e}")
        return "error"
    if sig is not None and sig == _last_wo_sig:
        return "ok"
    try:
        pull()
    except Exception as e:
        synclog.error(f"wo: pull_if_changed failed: {e}")
        return "error"
    return "changed"


def pull_if_changed_async(callback=None):
    """نسخه‌ی پس‌زمینه — callback(status) بعد از پایان صدا زده می‌شود."""
    def work():
        status = "error"
        try:
            status = pull_if_changed()
        except Exception as e:
            synclog.error(f"wo: pull_if_changed_async failed: {e}")
            status = "error"
        if callback:
            try:
                callback(status)
            except Exception:
                pass
    threading.Thread(target=work, daemon=True).start()


def pull_async(callback=None):
    """همگام‌سازی در پس‌زمینه؛ callback(ok) بعد از پایان صدا زده می‌شود."""
    def work():
        ok = True
        try:
            pull()
        except Exception as e:
            synclog.error(f"wo: pull_async failed: {e}")
            ok = False
        if callback:
            try:
                callback(ok)
            except Exception:
                pass
    threading.Thread(target=work, daemon=True).start()


def create(data):
    res = api_client.wo_create(data)
    synclog.info(f"wo: دستور کار ایجاد شد → «{data.get('description', '')[:50]}»")
    try:
        pull()
    except Exception:
        pass
    return res


def update(wo_id, data):
    api_client.wo_update(wo_id, data)
    synclog.info(f"wo: دستور کار #{wo_id} ویرایش شد")
    try:
        pull()
    except Exception:
        pass


def delete(wo_id):
    api_client.wo_delete(wo_id)
    synclog.info(f"wo: دستور کار #{wo_id} حذف شد")
    try:
        pull()
    except Exception:
        pass
