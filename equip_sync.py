# equip_sync.py
"""
همگام‌سازی محلی «دسته‌بندی‌ها / تجهیزات / برنامه‌های PM / قطعات یدکی»
با سرور — دقیقاً همان الگوی wo_sync.py برای دستور کارها:
سرور مرجع اصلی است؛ pull() کل جدول محلی را با نسخه‌ی سرور جایگزین
می‌کند تا هر تغییری که مدیر (روی هر سیستمی) انجام دهد، روی همه‌ی
کلاینت‌ها دیده شود.

نکته‌ی مهم دربارهٔ کلیدهای خارجی: چون equipment_id در pm_schedules
و در work_orders به equipment اشاره می‌کند و ممکن است بین اجرای
جایگزینی، آی‌دی‌های محلی موقتاً با آی‌دی‌های سرور هم‌خوان نباشند،
این ماژول قبل از حذف/درج، PRAGMA foreign_keys را برای همان یک
اتصال خاموش می‌کند (fetch/insert در یک تراکنش). دستور کارهای محلی
(work_orders) دست نمی‌خورند؛ اگر equipment_id آن‌ها موقتاً نامعتبر
شود، wo_sync.pull() با تطبیق بر اساس eq_name آن را خودش اصلاح می‌کند
(رفتاری که از قبل در wo_sync.py وجود دارد).
"""
import threading
import database as db
import api_client_ext as apx
from logger import sync as synclog

_lock = threading.Lock()

# ─── بروزرسانی خودکار: poll سبک برای UI (هر ۳ ثانیه) ────────────────
_last_equip_sig = None   # امضای آخرین snapshot ای که از سرور داریم
_pulled_once = False     # اولین pull هر اجرا → نوتیف نده که اسپم نشود


def pull_if_changed():
    """فقط امضای سبک سرور چک می‌شود؛ اگر تغییر کرده بود pull کامل انجام می‌شود.
    خروجی: (status, result) که status یکی از 'changed' / 'ok' / 'error' است."""
    try:
        meta = apx.sync_meta()
    except Exception as e:
        synclog.error(f"equip: sync_meta failed: {e}")
        return "error", None
    sig = meta.get("equip")
    if sig is not None and sig == _last_equip_sig:
        return "ok", None
    result = pull()          # pull() خودش امضای همین snapshot را ذخیره می‌کند
    return "changed", result


def pull_if_changed_async(callback=None):
    """نسخه‌ی پس‌زمینه — callback(status, result) بعد از پایان صدا زده می‌شود."""
    def work():
        status, result = "error", None
        try:
            status, result = pull_if_changed()
        except Exception as e:
            synclog.error(f"equip: pull_if_changed failed: {e}")
            status, result = "error", None
        if callback:
            try:
                callback(status, result)
            except Exception:
                pass
    threading.Thread(target=work, daemon=True).start()

def ensure_local():
    """ستون‌های لازم را روی جدول‌های محلیِ قدیمی اضافه می‌کند (اگر نبودند)."""
    for tbl, col, typ in [
        ("equipment", "created_by", "TEXT"),
        ("equipment", "updated_at", "TEXT"),
        ("pm_schedules", "created_by", "TEXT"),
        ("pm_schedules", "updated_at", "TEXT"),
        ("spare_parts", "created_by", "TEXT"),
        ("spare_parts", "updated_at", "TEXT"),
    ]:
        try:
            db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}", ())
        except Exception:
            pass
    _drop_equipment_code_unique_if_present()


def _drop_equipment_code_unique_if_present():
    """
    نصب‌های قدیمی جدول equipment را با قید UNIQUE روی code ساخته بودند،
    درصورتی‌که سرور همچین قیدی ندارد. این تفاوت باعث می‌شد pull() به محض
    برخورد با دو تجهیز هم‌کد (یا هر دو کد خالی) با خطای UNIQUE constraint
    شکست بخورد و کل عملیات (حذف/افزودن/ویرایش) بی‌صدا rollback شود.
    این تابع یک‌بار، بدون از دست رفتن داده، جدول را بدون آن قید بازسازی می‌کند.
    """
    conn = db.get_connection()
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='equipment'"
        ).fetchone()
        if not row or not row["sql"] or "UNIQUE" not in row["sql"].upper():
            return  # از قبل درست است یا جدول وجود ندارد
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("""
            CREATE TABLE equipment_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER,
                name TEXT NOT NULL, code TEXT, location TEXT,
                brand TEXT, model TEXT, serial_number TEXT, install_date TEXT,
                status TEXT DEFAULT 'فعال', notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                created_by TEXT, updated_at TEXT)
        """)
        conn.execute("""
            INSERT INTO equipment_new
            SELECT id, category_id, name, code, location, brand, model,
                   serial_number, install_date, status, notes, created_at,
                   created_by, updated_at FROM equipment
        """)
        conn.execute("DROP TABLE equipment")
        conn.execute("ALTER TABLE equipment_new RENAME TO equipment")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def _to_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _migrate_up_once():
    """
    _migrate_up() فقط باید یک‌بار در طول عمر نصب اجرا شود (انتقال داده‌های
    محلیِ قدیمی که قبل از فعال شدن سینک ساخته شده بودند). قبلاً این تابع
    داخل هر pull() اجرا می‌شد، یعنی بعد از هر حذف، چون کش محلی هنوز آیتم
    حذف‌شده را داشت، migrate_up آن را «گمشده» تشخیص می‌داد و دوباره به
    سرور آپلود می‌کرد — یعنی حذف عملاً بلافاصله خنثی می‌شد. با ذخیره‌ی
    یک پرچم دائمی در جدول settings، این اتفاق دیگر نمی‌افتد.
    """
    row = db.fetch_one("SELECT value FROM settings WHERE key='equip_migrated_up'")
    if row and row.get("value") == "1":
        return
    _migrate_up()
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('equip_migrated_up', '1')")


def _migrate_up():
    """رکوردهای محلیِ از قبل موجود (مثلاً از seed اولیه) که هنوز روی
    سرور نیستند را یک‌بار به سرور آپلود می‌کند تا در جایگزینی بعدی گم نشوند."""
    # ---- تجهیزات ----
    local_cats = {c["id"]: c for c in db.fetch_all("SELECT * FROM equipment_categories")}
    local_equip = db.fetch_all("SELECT * FROM equipment")
    try:
        server_equip = apx.equip_list()
    except Exception:
        return  # سرور در دسترس نیست؛ همگام‌سازی را ادامه نده
    have_codes = {e["code"] for e in server_equip if e.get("code")}
    have_names = {e["name"] for e in server_equip}
    missing_eq = []
    for e in local_equip:
        code = e.get("code") or ""
        if code and code in have_codes:
            continue
        if not code and e.get("name") in have_names:
            continue
        cat = local_cats.get(e.get("category_id")) or {}
        missing_eq.append({**e, "category_name": cat.get("name"), "category_icon": cat.get("icon")})
    if missing_eq:
        try:
            apx.equip_migrate(missing_eq)
            synclog.info(f"equip: migrate_up → {len(missing_eq)} تجهیز محلی به سرور منتقل شد")
        except Exception as e:
            synclog.error(f"equip: migrate_up equipment failed: {e}")

    # ---- برنامه‌های PM ----
    local_pm = db.fetch_all("""
        SELECT p.*, e.name as eq_name FROM pm_schedules p
        LEFT JOIN equipment e ON p.equipment_id=e.id""")
    try:
        server_pm = apx.pm_list()
    except Exception:
        server_pm = []
    have_pm = {(p.get("task_name"), p.get("eq_name")) for p in server_pm}
    missing_pm = [p for p in local_pm if (p.get("task_name"), p.get("eq_name")) not in have_pm]
    if missing_pm:
        try:
            apx.pm_migrate(missing_pm)
            synclog.info(f"equip: migrate_up → {len(missing_pm)} برنامه PM محلی به سرور منتقل شد")
        except Exception as e:
            synclog.error(f"equip: migrate_up pm_schedules failed: {e}")

    # ---- قطعات یدکی ----
    local_parts = db.fetch_all("SELECT * FROM spare_parts")
    try:
        server_parts = apx.parts_list()
    except Exception:
        server_parts = []
    have_pn = {p["part_number"] for p in server_parts if p.get("part_number")}
    have_pnames = {p["name"] for p in server_parts}
    missing_parts = []
    for p in local_parts:
        pn = p.get("part_number") or ""
        if pn and pn in have_pn:
            continue
        if not pn and p.get("name") in have_pnames:
            continue
        missing_parts.append(p)
    if missing_parts:
        try:
            apx.parts_migrate(missing_parts)
            synclog.info(f"equip: migrate_up → {len(missing_parts)} قطعه محلی به سرور منتقل شد")
        except Exception as e:
            synclog.error(f"equip: migrate_up spare_parts failed: {e}")


def pull():
    """کل جدول‌های محلی را با نسخه‌ی سرور جایگزین می‌کند.
    خروجی: دیکشنری شمارش‌ها + آیتم‌های تازه (برای نوتیف در UI)."""
    global _pulled_once, _last_equip_sig
    with _lock:
        ensure_local()
        _migrate_up_once()

        # امضای همین snapshot — «قبل از» خواندن جداول از سرور برداشته می‌شود
        # تا اگر وسط pull چیزی عوض شد، در تیک بعدی دوباره دیده شود
        sig = None
        try:
            sig = apx.sync_meta().get("equip")
        except Exception:
            pass

        categories = apx.eqcat_list()
        equipment = apx.equip_list()
        pm_rows = apx.pm_list()
        parts = apx.parts_list()

        old_equip_ids = {r["id"] for r in db.fetch_all("SELECT id FROM equipment")}
        old_part_ids = {r["id"] for r in db.fetch_all("SELECT id FROM spare_parts")}
        old_pm_ids = {r["id"] for r in db.fetch_all("SELECT id FROM pm_schedules")}

        conn = db.get_connection()
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            cur = conn.cursor()

            cur.execute("DELETE FROM equipment_categories")
            for cat in categories:
                cur.execute(
                    "INSERT INTO equipment_categories (id,name,icon,created_at) VALUES (?,?,?,?)",
                    (cat["id"], cat["name"], cat.get("icon") or "⚙️", cat.get("created_at")))

            cur.execute("DELETE FROM equipment")
            valid_eq_ids = set()
            for e in equipment:
                cur.execute("""INSERT INTO equipment
                    (id, category_id, name, code, location, brand, model, serial_number,
                     install_date, status, notes, created_by, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (e["id"], e.get("category_id"), e["name"], e.get("code"),
                     e.get("location"), e.get("brand"), e.get("model"), e.get("serial_number"),
                     e.get("install_date"), e.get("status") or "فعال", e.get("notes"),
                     e.get("created_by"), e.get("created_at")))
                valid_eq_ids.add(e["id"])
            eq_name_to_id = {e["name"]: e["id"] for e in equipment}

            cur.execute("DELETE FROM pm_schedules")
            for p in pm_rows:
                eq_id = p.get("equipment_id")
                if eq_id not in valid_eq_ids:
                    eq_id = eq_name_to_id.get(p.get("eq_name"))
                cur.execute("""INSERT INTO pm_schedules
                    (id, equipment_id, task_name, frequency_days, last_done, next_due,
                     operator, estimated_hours, checklist, active, created_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (p["id"], eq_id, p["task_name"], p.get("frequency_days") or 30,
                     p.get("last_done"), p.get("next_due"), p.get("operator"),
                     p.get("estimated_hours") or 1.0, p.get("checklist"),
                     1 if p.get("active", 1) else 0, p.get("created_by")))

            cur.execute("DELETE FROM spare_parts")
            for sp in parts:
                cur.execute("""INSERT INTO spare_parts
                    (id, name, part_number, category, quantity, unit, min_stock,
                     location, supplier, unit_price, notes, created_by, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sp["id"], sp["name"], sp.get("part_number"), sp.get("category"),
                     _to_int(sp.get("quantity")), sp.get("unit") or "عدد",
                     _to_int(sp.get("min_stock"), 2), sp.get("location"), sp.get("supplier"),
                     sp.get("unit_price") or 0, sp.get("notes"), sp.get("created_by"),
                     sp.get("created_at")))

            conn.commit()
        finally:
            conn.close()

        # آیتم‌های «جدید» فقط بعد از اولین pull گزارش می‌شوند تا در اولین
        # همگام‌سازیِ هر اجرا اسپم نوتیف نداشته باشیم
        first_pull = not _pulled_once
        _pulled_once = True

        new_equipment = [] if first_pull else [e for e in equipment if e["id"] not in old_equip_ids]
        new_parts = [] if first_pull else [p for p in parts if p["id"] not in old_part_ids]
        new_pm = [] if first_pull else [p for p in pm_rows if p["id"] not in old_pm_ids]

        if sig is not None:
            _last_equip_sig = sig

        synclog.info(f"equip: pull ok — دسته={len(categories)} تجهیز={len(equipment)} "
                    f"PM={len(pm_rows)} قطعه={len(parts)}")

        return {
            "categories": len(categories), "equipment": len(equipment),
            "pm": len(pm_rows), "parts": len(parts),
            "new_equipment": new_equipment, "new_parts": new_parts,
            "new_pm": new_pm,
        }
def pull_quiet():
    try:
        return pull()
    except Exception as e:
        synclog.error(f"equip: pull failed: {e}")
        return None


def pull_async(callback=None):
    """همگام‌سازی در پس‌زمینه؛ callback(result) بعد از پایان صدا زده می‌شود
    (result همان دیکشنری pull() یا None در صورت خطاست)."""
    def work():
        result = None
        try:
            result = pull()
        except Exception as e:
            synclog.error(f"equip: pull_async failed: {e}")
            result = None
        if callback:
            try:
                callback(result)
            except Exception:
                pass
    threading.Thread(target=work, daemon=True).start()


def notify_new_items(widget_parent, result, current_username, ToastNotification):
    if not result:
        return
    for eq in result.get("new_equipment", []):
        if (eq.get("created_by") or "") != current_username:
            ToastNotification(widget_parent, f"🆕 تجهیز «{eq['name']}» توسط {eq.get('created_by') or 'مدیر'} اضافه شد", "info")
    for p in result.get("new_pm", []):
        if (p.get("created_by") or "") != current_username:
            ToastNotification(widget_parent,
                f"📅 برنامه PM «{p.get('task_name') or ''}» برای «{p.get('eq_name') or '؟'}» توسط {p.get('created_by') or 'مدیر'} اضافه شد", "info")
    for p in result.get("new_parts", []):
        if (p.get("created_by") or "") != current_username:
            ToastNotification(widget_parent, f"🆕 قطعه «{p['name']}» توسط {p.get('created_by') or 'مدیر'} اضافه شد", "info")

# ---------------- عملیات نوشتن (از طریق سرور + همگام‌سازی مجدد) ----------------
def create_category(name, icon=None):
    res = apx.eqcat_create(name, icon)
    synclog.info(f"equip: دسته‌بندی ایجاد شد → «{name}»")
    try:
        pull()
    except Exception:
        pass
    return res


def update_category(cat_id, data):
    apx.eqcat_update(cat_id, data)
    synclog.info(f"equip: دسته‌بندی #{cat_id} ویرایش شد")
    try:
        pull()
    except Exception:
        pass


def delete_category(cat_id):
    apx.eqcat_delete(cat_id)
    synclog.info(f"equip: دسته‌بندی #{cat_id} حذف شد")
    try:
        pull()
    except Exception:
        pass


def create_equipment(data):
    res = apx.equip_create(data)
    synclog.info(f"equip: تجهیز ایجاد شد → «{data.get('name')}»")
    try:
        pull()
    except Exception:
        pass
    return res


def update_equipment(eq_id, data):
    apx.equip_update(eq_id, data)
    synclog.info(f"equip: تجهیز #{eq_id} ویرایش شد")
    try:
        pull()
    except Exception:
        pass


def delete_equipment(eq_id):
    apx.equip_delete(eq_id)
    synclog.info(f"equip: تجهیز #{eq_id} حذف شد")
    try:
        pull()
    except Exception:
        pass


def create_pm(data):
    res = apx.pm_create(data)
    synclog.info(f"equip: برنامه PM ایجاد شد → «{data.get('task_name')}»")
    try:
        pull()
    except Exception:
        pass
    return res


def update_pm(pm_id, data):
    apx.pm_update(pm_id, data)
    synclog.info(f"equip: برنامه PM #{pm_id} ویرایش شد")
    try:
        pull()
    except Exception:
        pass


def delete_pm(pm_id):
    apx.pm_delete(pm_id)
    synclog.info(f"equip: برنامه PM #{pm_id} حذف شد")
    try:
        pull()
    except Exception:
        pass


def create_part(data):
    res = apx.parts_create(data)
    synclog.info(f"equip: قطعه ایجاد شد → «{data.get('name')}»")
    try:
        pull()
    except Exception:
        pass
    return res


def update_part(part_id, data):
    apx.parts_update(part_id, data)
    synclog.info(f"equip: قطعه #{part_id} ویرایش شد")
    try:
        pull()
    except Exception:
        pass


def delete_part(part_id):
    apx.parts_delete(part_id)
    synclog.info(f"equip: قطعه #{part_id} حذف شد")
    try:
        pull()
    except Exception:
        pass
