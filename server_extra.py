# server_extra.py
"""
روت‌های جدید API برای:
  1) DCC — منبع اطلاعاتی/اسناد فنی تجهیزات سازمان
  2) ثبت تجربیات — دانشنامه‌ی فنی سازمان (Knowledge Base)

این فایل کاملاً جدید است و هیچ خطی از server.py را تغییر نمی‌دهد؛
فقط روت‌های جدید را روی همان app موجود در server.py ثبت می‌کند و از
همان تابع db()/current_user() برای اتصال به دیتابیس و احراز هویت استفاده می‌کند.

برای فعال شدن، فقط کافیست این ماژول import شود (این کار در startup.py،
داخل شرط role=='server'، با یک خط import انجام شده است) تا قبل از بالا
آمدن سرور، روت‌ها روی app ثبت شوند.
"""
import os
import uuid

from flask import request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from server import app, db, current_user, BASE_DIR

DCC_DIR = os.path.join(BASE_DIR, "dcc_files")
os.makedirs(DCC_DIR, exist_ok=True)


def _init_extra_tables():
    with db() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS dcc_documents(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'سایر',
                eq_name TEXT,
                description TEXT,
                file_name TEXT,
                stored_name TEXT,
                uploaded_by TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS experience_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'سایر',
                eq_name TEXT,
                work_order_ref TEXT,
                problem TEXT NOT NULL,
                solution TEXT,
                tips TEXT,
                tags TEXT,
                author TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS equipment_categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '⚙️',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS equipment(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                name TEXT NOT NULL,
                code TEXT,
                location TEXT,
                brand TEXT,
                model TEXT,
                serial_number TEXT,
                install_date TEXT,
                status TEXT DEFAULT 'فعال',
                notes TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS pm_schedules(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER,
                task_name TEXT NOT NULL,
                frequency_days INTEGER NOT NULL,
                last_done TEXT,
                next_due TEXT,
                operator TEXT,
                estimated_hours REAL DEFAULT 1.0,
                checklist TEXT,
                active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS spare_parts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                part_number TEXT,
                category TEXT,
                quantity INTEGER DEFAULT 0,
                unit TEXT DEFAULT 'عدد',
                min_stock INTEGER DEFAULT 2,
                location TEXT,
                supplier TEXT,
                unit_price REAL DEFAULT 0,
                notes TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT
            );
        """)
        for tbl in ("equipment", "pm_schedules", "spare_parts"):
            for col, typ in [("created_by", "TEXT"), ("updated_at", "TEXT")]:
                try:
                    c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
                except Exception:
                    pass

_init_extra_tables()


# ============================================================
#  DCC — مخزن اسناد فنی تجهیزات
# ============================================================
@app.get("/dcc/documents")
def dcc_list():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    q = "SELECT * FROM dcc_documents"
    filters, args = [], []
    eq_name = request.args.get("eq_name")
    category = request.args.get("category")
    search = request.args.get("q")
    if eq_name:
        filters.append("eq_name=?")
        args.append(eq_name)
    if category:
        filters.append("category=?")
        args.append(category)
    if search:
        filters.append("(title LIKE ? OR description LIKE ?)")
        args.extend([f"%{search}%", f"%{search}%"])
    if filters:
        q += " WHERE " + " AND ".join(filters)
    q += " ORDER BY id DESC"
    with db() as c:
        rows = c.execute(q, args).fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/dcc/documents")
def dcc_upload():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    title = (request.form.get("title") or "").strip()
    if not title:
        return jsonify({"error": "عنوان سند الزامی است"}), 400

    f = request.files.get("file")
    stored_name, orig_name = None, None
    if f and f.filename:
        orig_name = secure_filename(f.filename)
        stored_name = f"{uuid.uuid4().hex}_{orig_name}"
        f.save(os.path.join(DCC_DIR, stored_name))

    with db() as c:
        cur = c.execute("""INSERT INTO dcc_documents
            (title, category, eq_name, description, file_name, stored_name, uploaded_by)
            VALUES (?,?,?,?,?,?,?)""",
            (title, request.form.get("category") or "سایر",
             request.form.get("eq_name"), request.form.get("description"),
             orig_name, stored_name, u["username"]))
    return jsonify({"id": cur.lastrowid})


@app.get("/dcc/documents/<int:doc_id>/download")
def dcc_download(doc_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        row = c.execute("SELECT * FROM dcc_documents WHERE id=?", (doc_id,)).fetchone()
    if not row or not row["stored_name"]:
        return jsonify({"error": "فایلی برای این سند ثبت نشده"}), 404
    try:
        return send_from_directory(DCC_DIR, row["stored_name"], as_attachment=True,
                                   download_name=row["file_name"] or row["stored_name"])
    except TypeError:
        # سازگاری با نسخه‌های قدیمی‌تر فلسک که پارامتر متفاوتی دارند
        return send_from_directory(DCC_DIR, row["stored_name"], as_attachment=True,
                                   attachment_filename=row["file_name"] or row["stored_name"])


@app.delete("/dcc/documents/<int:doc_id>")
def dcc_delete(doc_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        row = c.execute("SELECT uploaded_by, stored_name FROM dcc_documents WHERE id=?",
                        (doc_id,)).fetchone()
        if not row:
            return jsonify({"error": "سند پیدا نشد"}), 404
        if u["role"] != "admin" and row["uploaded_by"] != u["username"]:
            return jsonify({"error": "فقط آپلودکننده یا مدیر مجاز است"}), 403
        c.execute("DELETE FROM dcc_documents WHERE id=?", (doc_id,))
    if row["stored_name"]:
        try:
            os.remove(os.path.join(DCC_DIR, row["stored_name"]))
        except OSError:
            pass
    return jsonify({"ok": True})


# ============================================================
#  ثبت تجربیات — دانشنامه‌ی فنی سازمان
# ============================================================
@app.get("/experience")
def exp_list():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    q = "SELECT * FROM experience_logs"
    filters, args = [], []
    category = request.args.get("category")
    eq_name = request.args.get("eq_name")
    search = request.args.get("q")
    if category:
        filters.append("category=?")
        args.append(category)
    if eq_name:
        filters.append("eq_name=?")
        args.append(eq_name)
    if search:
        filters.append("(title LIKE ? OR problem LIKE ? OR solution LIKE ? OR tags LIKE ?)")
        args.extend([f"%{search}%"] * 4)
    if filters:
        q += " WHERE " + " AND ".join(filters)
    q += " ORDER BY id DESC"
    with db() as c:
        rows = c.execute(q, args).fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/experience")
def exp_create():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    if not (d.get("title") or "").strip() or not (d.get("problem") or "").strip():
        return jsonify({"error": "عنوان و شرح مشکل الزامی است"}), 400
    with db() as c:
        cur = c.execute("""INSERT INTO experience_logs
            (title, category, eq_name, work_order_ref, problem, solution, tips, tags, author)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (d.get("title"), d.get("category") or "سایر", d.get("eq_name"),
             d.get("work_order_ref"), d.get("problem"), d.get("solution"),
             d.get("tips"), d.get("tags"), u["username"]))
    return jsonify({"id": cur.lastrowid})


@app.patch("/experience/<int:exp_id>")
def exp_update(exp_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        row = c.execute("SELECT author FROM experience_logs WHERE id=?", (exp_id,)).fetchone()
        if not row:
            return jsonify({"error": "مورد پیدا نشد"}), 404
        if u["role"] != "admin" and row["author"] != u["username"]:
            return jsonify({"error": "فقط نویسنده یا مدیر مجاز است"}), 403
        d = request.get_json(silent=True) or {}
        fields, args = [], []
        for k in ("title", "category", "eq_name", "work_order_ref",
                  "problem", "solution", "tips", "tags"):
            if k in d:
                fields.append(f"{k}=?")
                args.append(d[k])
        if fields:
            fields.append("updated_at=datetime('now','localtime')")
            args.append(exp_id)
            c.execute(f"UPDATE experience_logs SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})


@app.delete("/experience/<int:exp_id>")
def exp_delete(exp_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        row = c.execute("SELECT author FROM experience_logs WHERE id=?", (exp_id,)).fetchone()
        if not row:
            return jsonify({"error": "مورد پیدا نشد"}), 404
        if u["role"] != "admin" and row["author"] != u["username"]:
            return jsonify({"error": "فقط نویسنده یا مدیر مجاز است"}), 403
        c.execute("DELETE FROM experience_logs WHERE id=?", (exp_id,))
    return jsonify({"ok": True})


# ============================================================
#  تجهیزات — دسته‌بندی‌ها و تجهیزات (مشترک بین سرور و کلاینت‌ها)
#  همان الگوی work-orders/full: سرور مرجع اصلی است، کلاینت‌ها با
#  equip_sync.py کل جدول محلی را با سرور جایگزین می‌کنند.
# ============================================================
def _resolve_category(c, name, icon=None):
    """دسته‌بندی را با نام پیدا می‌کند یا در صورت نبود می‌سازد و id آن را برمی‌گرداند."""
    name = (name or "سایر").strip() or "سایر"
    row = c.execute("SELECT id FROM equipment_categories WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = c.execute("INSERT INTO equipment_categories (name, icon) VALUES (?,?)",
                    (name, icon or "⚙️"))
    return cur.lastrowid


@app.get("/equip/categories")
def eqcat_list():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        rows = c.execute("SELECT * FROM equipment_categories ORDER BY id").fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/equip/categories")
def eqcat_create():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"error": "نام دسته‌بندی الزامی است"}), 400
    with db() as c:
        cat_id = _resolve_category(c, name, d.get("icon"))
    return jsonify({"id": cat_id})


@app.patch("/equip/categories/<int:cat_id>")
def eqcat_update(cat_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    d = request.get_json(silent=True) or {}
    fields, args = [], []
    for k in ("name", "icon"):
        if k in d:
            fields.append(f"{k}=?")
            args.append(d[k])
    if fields:
        args.append(cat_id)
        with db() as c:
            c.execute(f"UPDATE equipment_categories SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})


@app.delete("/equip/categories/<int:cat_id>")
def eqcat_delete(cat_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    with db() as c:
        used = c.execute("SELECT COUNT(*) n FROM equipment WHERE category_id=?", (cat_id,)).fetchone()["n"]
        if used:
            return jsonify({"error": f"این دسته {used} تجهیز دارد. ابتدا تجهیزات را حذف کنید."}), 400
        c.execute("DELETE FROM equipment_categories WHERE id=?", (cat_id,))
    return jsonify({"ok": True})


@app.get("/equip/full")
def equip_list():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        rows = c.execute("""
            SELECT e.*, ec.name as category_name, ec.icon as category_icon
            FROM equipment e LEFT JOIN equipment_categories ec ON e.category_id=ec.id
            ORDER BY e.id DESC""").fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/equip/full")
def equip_create():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify({"error": "نام تجهیز الزامی است"}), 400
    with db() as c:
        cat_id = _resolve_category(c, d.get("category_name"), d.get("category_icon"))
        cur = c.execute("""INSERT INTO equipment
            (category_id, name, code, location, brand, model, serial_number,
             install_date, status, notes, created_by, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))""",
            (cat_id, name, d.get("code"), d.get("location"), d.get("brand"),
             d.get("model"), d.get("serial_number"), d.get("install_date"),
             d.get("status") or "فعال", d.get("notes"), u["username"]))
    return jsonify({"id": cur.lastrowid})


@app.patch("/equip/full/<int:eq_id>")
def equip_update(eq_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    with db() as c:
        row = c.execute("SELECT created_by FROM equipment WHERE id=?", (eq_id,)).fetchone()
        if not row:
            return jsonify({"error": "تجهیز پیدا نشد"}), 404
        
        d = request.get_json(silent=True) or {}
        fields, args = [], []
        if "category_name" in d:
            fields.append("category_id=?")
            args.append(_resolve_category(c, d.get("category_name"), d.get("category_icon")))
        for k in ("name", "code", "location", "brand", "model", "serial_number",
                  "install_date", "status", "notes"):
            if k in d:
                fields.append(f"{k}=?")
                args.append(d[k])
        if fields:
            fields.append("updated_at=datetime('now','localtime')")
            args.append(eq_id)
            c.execute(f"UPDATE equipment SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})


@app.delete("/equip/full/<int:eq_id>")
def equip_delete(eq_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    with db() as c:
        row = c.execute("SELECT created_by FROM equipment WHERE id=?", (eq_id,)).fetchone()
        if not row:
            return jsonify({"error": "تجهیز پیدا نشد"}), 404
        c.execute("DELETE FROM equipment WHERE id=?", (eq_id,))
    return jsonify({"ok": True})


@app.post("/equip/migrate")
def equip_migrate():
    """آپلود اولیه‌ی تجهیزات محلیِ از قبل موجود (که هنوز روی سرور نیستند)."""
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    rows = request.get_json(silent=True) or []
    added = 0
    with db() as c:
        for d in rows:
            name = (d.get("name") or "").strip()
            if not name:
                continue
            code = d.get("code")
            exists = None
            if code:
                exists = c.execute("SELECT 1 FROM equipment WHERE code=?", (code,)).fetchone()
            if not exists:
                exists = c.execute("SELECT 1 FROM equipment WHERE name=? AND (code IS ? OR code='')",
                                   (name, code)).fetchone()
            if exists:
                continue
            cat_id = _resolve_category(c, d.get("category_name"), d.get("category_icon"))
            c.execute("""INSERT INTO equipment
                (category_id, name, code, location, brand, model, serial_number,
                 install_date, status, notes, created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (cat_id, name, code, d.get("location"), d.get("brand"), d.get("model"),
                 d.get("serial_number"), d.get("install_date"), d.get("status") or "فعال",
                 d.get("notes"), d.get("created_by")))
            added += 1
    return jsonify({"ok": True, "added": added})


# ============================================================
#  برنامه‌های PM (نگهداری پیشگیرانه) — مشترک بین سرور و کلاینت‌ها
#  equipment_id محلی هر سیستم لزوماً با سرور یکی نیست، پس eq_name
#  هم همراه هر رکورد فرستاده می‌شود تا equip_sync بتواند تطبیق بدهد
#  (دقیقاً همان ترفندی که wo_sync برای equipment_id در دستور کارها دارد).
# ============================================================
@app.get("/pm/schedules")
def pm_list():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        rows = c.execute("""
            SELECT p.*, e.name as eq_name FROM pm_schedules p
            LEFT JOIN equipment e ON p.equipment_id=e.id
            ORDER BY p.id DESC""").fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/pm/schedules")
def pm_create():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    d = request.get_json(silent=True) or {}
    if not (d.get("task_name") or "").strip():
        return jsonify({"error": "نام کار الزامی است"}), 400
    with db() as c:
        eq_id = d.get("equipment_id")
        eq_name = d.get("eq_name")
        if eq_name:
            row = c.execute("SELECT id FROM equipment WHERE name=?", (eq_name,)).fetchone()
            if row:
                eq_id = row["id"]
        cur = c.execute("""INSERT INTO pm_schedules
            (equipment_id, task_name, frequency_days, last_done, next_due,
             operator, estimated_hours, checklist, active, created_by, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))""",
            (eq_id, d.get("task_name"), d.get("frequency_days") or 30,
             d.get("last_done"), d.get("next_due"), d.get("operator"),
             d.get("estimated_hours") or 1.0, d.get("checklist"),
             1 if d.get("active", True) else 0, u["username"]))
    return jsonify({"id": cur.lastrowid})


@app.patch("/pm/schedules/<int:pm_id>")
def pm_update(pm_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    with db() as c:
        row = c.execute("SELECT created_by FROM pm_schedules WHERE id=?", (pm_id,)).fetchone()
        if not row:
            return jsonify({"error": "برنامه پیدا نشد"}), 404
        
        d = request.get_json(silent=True) or {}
        fields, args = [], []
        if "eq_name" in d and d.get("eq_name"):
            eqrow = c.execute("SELECT id FROM equipment WHERE name=?", (d["eq_name"],)).fetchone()
            if eqrow:
                fields.append("equipment_id=?")
                args.append(eqrow["id"])
        for k in ("task_name", "frequency_days", "last_done", "next_due",
                  "operator", "estimated_hours", "checklist", "active"):
            if k in d:
                fields.append(f"{k}=?")
                args.append(d[k])
        if fields:
            fields.append("updated_at=datetime('now','localtime')")
            args.append(pm_id)
            c.execute(f"UPDATE pm_schedules SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})


@app.delete("/pm/schedules/<int:pm_id>")
def pm_delete(pm_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    with db() as c:
        row = c.execute("SELECT created_by FROM pm_schedules WHERE id=?", (pm_id,)).fetchone()
        if not row:
            return jsonify({"error": "برنامه پیدا نشد"}), 404
        c.execute("DELETE FROM pm_schedules WHERE id=?", (pm_id,))
    return jsonify({"ok": True})


@app.post("/pm/migrate")
def pm_migrate():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    rows = request.get_json(silent=True) or []
    added = 0
    with db() as c:
        for d in rows:
            task_name = (d.get("task_name") or "").strip()
            eq_name = d.get("eq_name")
            if not task_name:
                continue
            exists = c.execute(
                """SELECT 1 FROM pm_schedules p LEFT JOIN equipment e ON p.equipment_id=e.id
                   WHERE p.task_name=? AND (e.name=? OR (e.name IS NULL AND ? IS NULL))""",
                (task_name, eq_name, eq_name)).fetchone()
            if exists:
                continue
            eq_id = None
            if eq_name:
                eqrow = c.execute("SELECT id FROM equipment WHERE name=?", (eq_name,)).fetchone()
                eq_id = eqrow["id"] if eqrow else None
            c.execute("""INSERT INTO pm_schedules
                (equipment_id, task_name, frequency_days, last_done, next_due,
                 operator, estimated_hours, checklist, active, created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (eq_id, task_name, d.get("frequency_days") or 30, d.get("last_done"),
                 d.get("next_due"), d.get("operator"), d.get("estimated_hours") or 1.0,
                 d.get("checklist"), 1 if d.get("active", True) else 0, d.get("created_by")))
            added += 1
    return jsonify({"ok": True, "added": added})


# ============================================================
#  قطعات یدکی — مشترک بین سرور و کلاینت‌ها
# ============================================================
@app.get("/spare-parts")
def parts_list():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        rows = c.execute("SELECT * FROM spare_parts ORDER BY id DESC").fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/spare-parts")
def parts_create():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    d = request.get_json(silent=True) or {}
    if not (d.get("name") or "").strip():
        return jsonify({"error": "نام قطعه الزامی است"}), 400
    with db() as c:
        cur = c.execute("""INSERT INTO spare_parts
            (name, part_number, category, quantity, unit, min_stock,
             location, supplier, unit_price, notes, created_by, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))""",
            (d.get("name"), d.get("part_number"), d.get("category"),
             d.get("quantity") or 0, d.get("unit") or "عدد", d.get("min_stock") or 2,
             d.get("location"), d.get("supplier"), d.get("unit_price") or 0,
             d.get("notes"), u["username"]))
    return jsonify({"id": cur.lastrowid})


@app.patch("/spare-parts/<int:part_id>")
def parts_update(part_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    with db() as c:
        row = c.execute("SELECT created_by FROM spare_parts WHERE id=?", (part_id,)).fetchone()
        if not row:
            return jsonify({"error": "قطعه پیدا نشد"}), 404
        
        d = request.get_json(silent=True) or {}
        fields, args = [], []
        for k in ("name", "part_number", "category", "quantity", "unit",
                  "min_stock", "location", "supplier", "unit_price", "notes"):
            if k in d:
                fields.append(f"{k}=?")
                args.append(d[k])
        if fields:
            fields.append("updated_at=datetime('now','localtime')")
            args.append(part_id)
            c.execute(f"UPDATE spare_parts SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})


@app.delete("/spare-parts/<int:part_id>")
def parts_delete(part_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    with db() as c:
        row = c.execute("SELECT created_by FROM spare_parts WHERE id=?", (part_id,)).fetchone()
        if not row:
            return jsonify({"error": "قطعه پیدا نشد"}), 404
        c.execute("DELETE FROM spare_parts WHERE id=?", (part_id,))
    return jsonify({"ok": True})


@app.post("/spare-parts/migrate")
def parts_migrate():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    rows = request.get_json(silent=True) or []
    added = 0
    with db() as c:
        for d in rows:
            name = (d.get("name") or "").strip()
            if not name:
                continue
            pn = d.get("part_number")
            exists = None
            if pn:
                exists = c.execute("SELECT 1 FROM spare_parts WHERE part_number=?", (pn,)).fetchone()
            if not exists:
                exists = c.execute("SELECT 1 FROM spare_parts WHERE name=? AND (part_number IS ? OR part_number='')",
                                   (name, pn)).fetchone()
            if exists:
                continue
            c.execute("""INSERT INTO spare_parts
                (name, part_number, category, quantity, unit, min_stock,
                 location, supplier, unit_price, notes, created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (name, pn, d.get("category"), d.get("quantity") or 0,
                 d.get("unit") or "عدد", d.get("min_stock") or 2, d.get("location"),
                 d.get("supplier"), d.get("unit_price") or 0, d.get("notes"),
                 d.get("created_by")))
            added += 1
    return jsonify({"ok": True, "added": added})
# ============================================================
#  متادیتای همگام‌سازی — برای بروزرسانی خودکارِ ۳ ثانیه‌ای کلاینت‌ها
#  کلاینت به‌جای گرفتن کل جداول، فقط این امضای سبک را چک می‌کند و
#  فقط وقتی عوض شده pull کامل انجام می‌دهد.
# ============================================================
@app.get("/sync/meta")
def sync_meta():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401

    def _sig(c, table, has_updated=True):
        if has_updated:
            expr = "COALESCE(MAX(COALESCE(updated_at, created_at)), '')"
        else:
            expr = "COALESCE(MAX(created_at), '')"
        r = c.execute(f"SELECT COUNT(*) n, {expr} m FROM {table}").fetchone()
        return f"{r['n']}:{r['m']}"

    with db() as c:
        return jsonify({
            "equip": "|".join([
                _sig(c, "equipment_categories", has_updated=False),
                _sig(c, "equipment"),
                _sig(c, "pm_schedules"),
                _sig(c, "spare_parts"),
            ]),
            "wo": _sig(c, "work_orders"),
        })