"""
oee_data.py — لایه‌ی داده‌ی OEE (کارایی کلی تجهیزات / زمان مفید کارکرد)

این فایل کاملاً جدید و مستقل است و به هیچ‌وجه database.py را تغییر نمی‌دهد.
فقط با استفاده از database.get_connection() یک جدول جدید (در صورت نبود)
می‌سازد تا داده‌های دستیِ کارایی/کیفیت را نگه دارد. بخش "در دسترس بودن"
(Availability) به‌صورت خودکار از روی جدول موجود work_orders محاسبه می‌شود
و نیازی به ورود دستی ندارد.
"""
from datetime import date, timedelta
import database as db

_TABLE_READY = False


def _ensure_table():
    global _TABLE_READY
    if _TABLE_READY:
        return
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS oee_manual_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id INTEGER NOT NULL,
        entry_date TEXT NOT NULL,
        performance_pct REAL,
        quality_pct REAL,
        good_qty INTEGER,
        total_qty INTEGER,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')))""")
    conn.commit()
    conn.close()
    _TABLE_READY = True


def add_entry(equipment_id, entry_date, performance_pct=None, quality_pct=None,
              good_qty=None, total_qty=None, notes=""):
    _ensure_table()
    if quality_pct is None and total_qty:
        try:
            quality_pct = round((good_qty or 0) / total_qty * 100, 1)
        except ZeroDivisionError:
            quality_pct = None
    return db.execute("""INSERT INTO oee_manual_entries
        (equipment_id, entry_date, performance_pct, quality_pct, good_qty, total_qty, notes)
        VALUES (?,?,?,?,?,?,?)""",
        (equipment_id, entry_date, performance_pct, quality_pct, good_qty, total_qty, notes))


def list_entries(equipment_id=None, since=None, limit=50):
    _ensure_table()
    q = "SELECT * FROM oee_manual_entries"
    filters, args = [], []
    if equipment_id:
        filters.append("equipment_id=?")
        args.append(equipment_id)
    if since:
        filters.append("entry_date>=?")
        args.append(since)
    if filters:
        q += " WHERE " + " AND ".join(filters)
    q += " ORDER BY entry_date DESC, id DESC LIMIT ?"
    args.append(limit)
    return db.fetch_all(q, args)


def delete_entry(entry_id):
    _ensure_table()
    db.execute("DELETE FROM oee_manual_entries WHERE id=?", (entry_id,))


def _working_hours_per_day():
    row = db.fetch_one("SELECT value FROM settings WHERE key='working_hours_per_day'")
    try:
        return float(row["value"]) if row and row["value"] else 16.0
    except (TypeError, ValueError):
        return 16.0


def calc_availability(equipment_id, days=30):
    """
    درصد در دسترس بودن = (زمان برنامه‌ریزی‌شده‌ی تولید - توقف اضطراری) / زمان برنامه‌ریزی‌شده
    زمان برنامه‌ریزی‌شده از «ساعت کاری روزانه» در تنظیمات محاسبه می‌شود.
    توقفات PM (برنامه‌ریزی‌شده) در این محاسبه لحاظ نمی‌شوند چون بخشی از برنامه‌ی
    نگهداری هستند، نه از دست‌رفتنِ ناخواسته‌ی زمان کارکرد.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    hours_per_day = _working_hours_per_day()
    planned_minutes = hours_per_day * 60 * days
    row = db.fetch_one("""SELECT SUM(downtime_minutes) as total_down
        FROM work_orders WHERE equipment_id=? AND order_type='EM' AND work_date>=?""",
        (equipment_id, since))
    downtime = (row["total_down"] or 0) if row else 0
    if planned_minutes <= 0:
        return 0.0, downtime
    pct = max(0.0, min(100.0, (planned_minutes - downtime) / planned_minutes * 100))
    return round(pct, 1), downtime


def calc_performance_quality(equipment_id, days=30):
    """
    میانگین کارایی/کیفیت از داده‌های دستیِ ثبت‌شده برای این تجهیز.
    اگر هیچ داده‌ای ثبت نشده باشد، ۱۰۰٪ فرض می‌شود (یعنی OEE برابر Availability خواهد بود).
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    entries = list_entries(equipment_id=equipment_id, since=since, limit=1000)
    perf_vals = [e["performance_pct"] for e in entries if e["performance_pct"] is not None]
    qual_vals = [e["quality_pct"] for e in entries if e["quality_pct"] is not None]
    perf = round(sum(perf_vals) / len(perf_vals), 1) if perf_vals else 100.0
    qual = round(sum(qual_vals) / len(qual_vals), 1) if qual_vals else 100.0
    return perf, qual


def calc_oee(equipment_id, days=30):
    availability, downtime = calc_availability(equipment_id, days)
    performance, quality = calc_performance_quality(equipment_id, days)
    oee = round(availability * performance * quality / 10000, 1)
    return {"availability": availability, "performance": performance,
            "quality": quality, "oee": oee, "downtime_minutes": downtime, "days": days}


def calc_oee_all(days=30):
    equipment = db.fetch_all("SELECT id, name, code, status FROM equipment ORDER BY name")
    results = []
    for eq in equipment:
        m = calc_oee(eq["id"], days)
        m["equipment_id"] = eq["id"]
        m["name"] = eq["name"]
        m["code"] = eq["code"]
        m["status"] = eq["status"]
        results.append(m)
    return results
