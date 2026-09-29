# server.py
import sys, os, hashlib, secrets, sqlite3
import time
from datetime import date
from flask import Flask, request, jsonify
from waitress import serve
from werkzeug.security import generate_password_hash, check_password_hash

if getattr(sys, "frozen", False) or "__compiled__" in globals():
    # مهم: در حالت onefile نانیوکا، sys.executable به یک پوشه‌ی موقتِ
    # استخراج‌شده اشاره می‌کند که بعد از هر اجرا پاک می‌شود — استفاده از آن
    # برای مسیر دیتابیس باعث می‌شد cmms.db و dcc_files هر بار از نو ساخته
    # و داده‌های قبلی گم شوند. به‌جایش از %LOCALAPPDATA% (همیشه قابل نوشتن
    # و پایدار بین اجراها) استفاده می‌کنیم — دقیقاً همان الگوی database.py/styles.py
    BASE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CMMS")
    os.makedirs(BASE_DIR, exist_ok=True)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "cmms.db")
API_PORT = 8000

app = Flask(__name__)
TOKENS = {}   # token -> {"username":..., "role":..., "unit_id":..., "expires":...}


def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def init_db():
    with db() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS units(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER REFERENCES units(id)
            );
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'user',
                unit_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS work_orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                order_number TEXT,
                order_type TEXT,
                equipment_id INTEGER,
                eq_name TEXT,
                location TEXT,
                operator TEXT,
                description TEXT,
                work_date TEXT,
                start_time TEXT,
                end_time TEXT,
                downtime_minutes INTEGER DEFAULT 0,
                priority TEXT DEFAULT 'متوسط',
                status TEXT DEFAULT 'باز',
                root_cause TEXT,
                action_taken TEXT,
                parts_used TEXT,
                technician_name TEXT,
                created_by TEXT,
                unit_id INTEGER,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                unit_id INTEGER,
                subject TEXT NOT NULL,
                body TEXT,
                kind TEXT DEFAULT 'درخواست',
                status TEXT DEFAULT 'جدید',
                reply TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS tokens(
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                expires REAL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
                # جدول شماره‌های حذف‌شده — جلوی زنده‌شدن مجدد توسط migrate کلاینت‌ها
        c.execute("""CREATE TABLE IF NOT EXISTS deleted_work_orders(
            order_number TEXT PRIMARY KEY,
            deleted_at TEXT DEFAULT (datetime('now','localtime')))""")
                # ── پاکسازی شماره‌های تکراری + جلوگیری از تکرار در آینده ──
        # (تداخل هم‌زمان migrate/ثبت بین چند کلاینت می‌توانست دو رکورد با
        #  یک شماره بسازد؛ نتیجه‌اش شکستن pull کلاینت‌ها و «غیب‌شدن» ردیف‌ها بود)
        try:
            c.execute("""DELETE FROM work_orders
                         WHERE order_number IS NOT NULL AND id NOT IN
                           (SELECT MIN(id) FROM work_orders
                            WHERE order_number IS NOT NULL
                            GROUP BY order_number)""")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_wo_ordernum "
                      "ON work_orders(order_number)")
        except Exception:
            pass
        # برای دیتابیس‌های قدیمی: ستون‌های جدید work_orders اضافه شوند
        for col, typ in [("order_number","TEXT"),("order_type","TEXT"),
                         ("equipment_id","INTEGER"),("eq_name","TEXT"),
                         ("location","TEXT"),("work_date","TEXT"),
                         ("start_time","TEXT"),("end_time","TEXT"),
                         ("downtime_minutes","INTEGER DEFAULT 0"),
                         ("priority","TEXT"),("status","TEXT"),
                         ("root_cause","TEXT"),("action_taken","TEXT"),
                         ("parts_used","TEXT"),("technician_name","TEXT"),
                         ("created_by","TEXT"),("updated_at","TEXT")]:
            try:
                c.execute(f"ALTER TABLE work_orders ADD COLUMN {col} {typ}")
            except Exception:
                pass  # از قبل وجود دارد
        for col, typ in [("technician_username","TEXT"),("report_text","TEXT"),
                         ("report_submitted_at","TEXT"),("report_status","TEXT"),
                         ("report_rating","REAL"),("report_comment","TEXT")]:
            try:
                c.execute(f"ALTER TABLE work_orders ADD COLUMN {col} {typ}")
            except Exception:
                pass
        # یک‌بار: تطبیق تکنسین‌های قدیمی با کاربران تا فیلتر دسترسی کار کند
        try:
            old = c.execute("""SELECT id, technician_name FROM work_orders
                WHERE (technician_username IS NULL OR technician_username='')
                  AND technician_name IS NOT NULL AND technician_name != ''""").fetchall()
            for r in old:
                urow = c.execute("SELECT username FROM users WHERE full_name=? OR username=?",
                                 (r["technician_name"], r["technician_name"])).fetchone()
                if urow:
                    c.execute("UPDATE work_orders SET technician_username=? WHERE id=?",
                              (urow["username"], r["id"]))
        except Exception:
            pass            
        # پاکسازی توکن‌های منقضی‌شده
        c.execute("DELETE FROM tokens WHERE expires < ?", (time.time(),))
        if not c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            c.execute("INSERT INTO users(username,password,full_name,role) VALUES(?,?,?,?)",
                      ("admin", generate_password_hash("MoiAM!#@$1324"), "مدیر سیستم", "admin"))


def current_user():
    token = request.headers.get("token", "")
    entry = TOKENS.get(token)
    if entry:
        if entry.get("expires", 0) < time.time():
            TOKENS.pop(token, None)
            return None
        return entry
    # توکن از دیتابیس بازیابی می‌شود (بعد از ری‌استارت سرور) تا وقتی منقضی نشده
    if token:
        try:
            with db() as c:
                r = c.execute("""SELECT t.expires, u.username, u.role, u.unit_id
                                 FROM tokens t JOIN users u ON t.username = u.username
                                 WHERE t.token = ?""", (token,)).fetchone()
            if r and (r["expires"] or 0) > time.time():
                entry = {"username": r["username"], "role": r["role"],
                         "unit_id": r["unit_id"], "expires": r["expires"]}
                TOKENS[token] = entry
                return entry
        except Exception:
            pass
    return None


def _gen_order_number(order_type):
    prefix = "PM" if order_type == "PM" else "EM"
    ym = date.today().strftime("%Y%m")
    seq = 1
    with db() as c:
        row = c.execute("SELECT order_number FROM work_orders WHERE order_number LIKE ? "
                        "ORDER BY id DESC LIMIT 1", (f"{prefix}-{ym}%",)).fetchone()
        if row:
            seq = int(row["order_number"].split("-")[-1]) + 1
        # رد کردن شماره‌های حذف‌شده و موجود — جلوی تضاد با migrate
        def _taken(num):
            return (c.execute("SELECT 1 FROM work_orders WHERE order_number=?", (num,)).fetchone()
                    or c.execute("SELECT 1 FROM deleted_work_orders WHERE order_number=?",
                                 (num,)).fetchone())
        onum = f"{prefix}-{ym}-{seq:04d}"
        while _taken(onum):
            seq += 1
            onum = f"{prefix}-{ym}-{seq:04d}"
    return onum# ---------------- احراز هویت ----------------
@app.get("/health")
def health():
    return jsonify({"ok": True})


LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
TOKEN_LIFETIME = 8 * 3600


@app.post("/login")
def login():
    ip = request.remote_addr
    now = time.time()
    attempt = LOGIN_ATTEMPTS.get(ip)
    if attempt and attempt["locked_until"] > now:
        wait = int(attempt["locked_until"] - now)
        return jsonify({"error": f"تعداد تلاش ناموفق زیاد بود. {wait} ثانیه دیگر امتحان کنید"}), 429

    d = request.get_json(silent=True) or {}
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE username=?",
                        (d.get("username"),)).fetchone()

    if not row or not check_password_hash(row["password"], d.get("password") or ""):
        attempt = LOGIN_ATTEMPTS.setdefault(ip, {"count": 0, "locked_until": 0})
        attempt["count"] += 1
        if attempt["count"] >= MAX_ATTEMPTS:
            attempt["locked_until"] = now + LOCKOUT_SECONDS
            attempt["count"] = 0
        return jsonify({"error": "نام کاربری یا رمز اشتباه است"}), 401

    LOGIN_ATTEMPTS.pop(ip, None)
    token = secrets.token_hex(16)
    expires = now + TOKEN_LIFETIME
    TOKENS[token] = {"username": row["username"], "role": row["role"],
                     "unit_id": row["unit_id"], "expires": expires}
    # ذخیره توکن در دیتابیس تا بعد از ری‌استارت سرور هم معتبر بماند
    try:
        with db() as c:
            c.execute("INSERT OR REPLACE INTO tokens(token, username, expires) VALUES(?,?,?)",
                      (token, row["username"], expires))
    except Exception:
        pass
    return jsonify({"token": token, "full_name": row["full_name"],
                    "role": row["role"], "username": row["username"]})


@app.get("/me")
def me():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(u)


# ---------------- واحدها ----------------
@app.get("/units")
def get_units():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        return jsonify([dict(x) for x in c.execute("SELECT * FROM units ORDER BY id")])


@app.post("/units")
def add_unit():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    with db() as c:
        cur = c.execute("INSERT INTO units(name,parent_id) VALUES(?,?)",
                        (d.get("name"), d.get("parent_id")))
        return jsonify({"id": cur.lastrowid})


# ---------------- دستور کارها (قدیمی — دست نخورده) ----------------
@app.get("/work-orders")
def get_work_orders():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    q, args = "SELECT * FROM work_orders", []
    unit_id = request.args.get("unit_id", type=int)
    if unit_id:
        q += " WHERE unit_id=?"
        args.append(unit_id)
    with db() as c:
        return jsonify([dict(x) for x in c.execute(q + " ORDER BY id DESC", args)])


@app.post("/work-orders")
def add_work_order():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    with db() as c:
        cur = c.execute("""INSERT INTO work_orders(title,description,operator,priority,unit_id)
                           VALUES(?,?,?,?,?)""",
                        (d.get("title"), d.get("description"), d.get("operator"),
                         d.get("priority"), d.get("unit_id")))
        return jsonify({"id": cur.lastrowid})


@app.patch("/work-orders/<int:wo_id>")
def update_work_order(wo_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    fields, args = [], []
    for k in ("status", "priority", "description"):
        if k in d:
            fields.append(f"{k}=?")
            args.append(d[k])
    if fields:
        args.append(wo_id)
        with db() as c:
            c.execute(f"UPDATE work_orders SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})


# ---------------- دستور کارهای مشترک (سرور-محور) ----------------
@app.get("/work-orders/full")
def get_work_orders_full():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        rows = c.execute("SELECT * FROM work_orders ORDER BY id DESC").fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/work-orders/full")
def add_work_order_full():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    otype = d.get("order_type") or "EM"
    # فقط مدیر می‌تواند دستور کار ثبت کند؛ استثنا: PMِ خودکار (ثبت انجام برنامه PM)
    if u["role"] != "admin" and otype != "PM":
        return jsonify({"error": "فقط مدیر سیستم می‌تواند دستور کار ثبت کند"}), 403
    onum = _gen_order_number(otype)
    with db() as c:
        # تطبیق تکنسین با کاربر سیستم → مبنای فیلتر دسترسی
        tech_un = (d.get("technician_username") or "").strip()
        if tech_un and not c.execute("SELECT 1 FROM users WHERE username=?",
                                     (tech_un,)).fetchone():
            tech_un = None
        if not tech_un and (d.get("technician_name") or "").strip():
            urow = c.execute("SELECT username FROM users WHERE full_name=? OR username=?",
                             (d["technician_name"], d["technician_name"])).fetchone()
            tech_un = urow["username"] if urow else None
        cur = c.execute("""INSERT INTO work_orders
            (title, order_number, order_type, equipment_id, eq_name, location,
             operator, description, work_date, start_time, end_time,
             downtime_minutes, priority, status, root_cause, action_taken,
             parts_used, technician_name, technician_username, created_by,
             created_at, updated_at)
            VALUES (?,?,?,?,?,?,
                    ?,?,?,?,?,
                    ?,?,?,?,?,
                    ?,?,?,?,
                    datetime('now','localtime'), datetime('now','localtime'))""",
            (onum, onum, otype, d.get("equipment_id"), d.get("eq_name"),
             d.get("location"), d.get("operator"), d.get("description"),
             d.get("work_date"), d.get("start_time"), d.get("end_time"),
             _safe_int(d.get("downtime_minutes")),
             d.get("priority") or "متوسط", d.get("status") or "باز",
             d.get("root_cause"), d.get("action_taken"), d.get("parts_used"),
             d.get("technician_name"), tech_un, u["username"]))
        return jsonify({"id": cur.lastrowid, "order_number": onum})


@app.patch("/work-orders/full/<int:wo_id>")
def update_work_order_full(wo_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        row = c.execute("SELECT created_by FROM work_orders WHERE id=?", (wo_id,)).fetchone()
        if not row:
            return jsonify({"error": "دستور کار پیدا نشد"}), 404
        if u["role"] != "admin" and (row["created_by"] or "") != u["username"]:
            return jsonify({"error": "فقط سازنده یا مدیر مجاز است"}), 403
        d = request.get_json(silent=True) or {}
        fields, args = [], []
        # اگر تکنسین عوض شد، نام کاربری او هم دوباره تطبیق شود
        if "technician_name" in d:
            fields.append("technician_name=?"); args.append(d["technician_name"])
            tech_un = (d.get("technician_username") or "").strip()
            if not tech_un and (d["technician_name"] or "").strip():
                urow = c.execute("SELECT username FROM users WHERE full_name=? OR username=?",
                                 (d["technician_name"], d["technician_name"])).fetchone()
                tech_un = urow["username"] if urow else None
            fields.append("technician_username=?"); args.append(tech_un)
        for k in ("operator", "technician_username", "work_date", "start_time",
                  "end_time", "downtime_minutes", "priority", "status",
                  "description", "action_taken", "root_cause", "parts_used"):
            if k in d and k != "technician_username":
                fields.append(f"{k}=?"); args.append(d[k])
        if fields:
            fields.append("updated_at=datetime('now','localtime')")
            args.append(wo_id)
            c.execute(f"UPDATE work_orders SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})

@app.delete("/work-orders/full/<int:wo_id>")
def delete_work_order_full(wo_id):
    """حذف دستور کار — فقط سازنده یا مدیر"""
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        row = c.execute("SELECT created_by, order_number FROM work_orders WHERE id=?",
                        (wo_id,)).fetchone()
        if not row:
            return jsonify({"error": "دستور کار پیدا نشد"}), 404
        if u["role"] != "admin" and (row["created_by"] or "") != u["username"]:
            return jsonify({"error": "فقط سازنده یا مدیر مجاز است"}), 403
        # شماره‌اش ثبت شود تا کلاینت‌های دیگر، دستور کارِ حذف‌شده را
        # از طریق migrate دوباره آپلود و زنده نکنند (باگ ۲ را ببین)
        if row["order_number"]:
            c.execute("INSERT OR IGNORE INTO deleted_work_orders(order_number) VALUES(?)",
                      (row["order_number"],))
        c.execute("DELETE FROM work_orders WHERE id=?", (wo_id,))
    return jsonify({"ok": True})

@app.post("/work-orders/migrate")
def migrate_work_orders():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    
    rows = request.get_json(silent=True) or []
    added = 0
    with db() as c:
        for d in rows:
            onum = d.get("order_number")
            if not onum:
                continue
            if c.execute("SELECT 1 FROM work_orders WHERE order_number=?", (onum,)).fetchone():
                continue
                        # ← جدید: دستور کارِ عمداً حذف‌شده را دوباره قبول نکن
            if c.execute("SELECT 1 FROM deleted_work_orders WHERE order_number=?", (onum,)).fetchone():
                continue

            tech_un = (d.get("technician_username") or "").strip() or None
            if not tech_un and (d.get("technician_name") or "").strip():
                urow = c.execute("SELECT username FROM users WHERE full_name=? OR username=?",
                                 (d["technician_name"], d["technician_name"])).fetchone()
                tech_un = urow["username"] if urow else None
            c.execute("""INSERT INTO work_orders
                (title, order_number, order_type, equipment_id, eq_name, location,
                 operator, description, work_date, start_time, end_time,
                 downtime_minutes, priority, status, root_cause, action_taken,
                 parts_used, technician_name, technician_username, created_by, created_at, updated_at)
                VALUES (?,?,?,?,?,?,
                        ?,?,?,?,?,
                        ?,?,?,?,?,
                        ?,?,?,?,
                        COALESCE(?, datetime('now','localtime')), ?)""",
                (onum, onum, d.get("order_type"), d.get("equipment_id"),
                 d.get("eq_name"), d.get("location"), d.get("operator"),
                 d.get("description"), d.get("work_date"), d.get("start_time"),
                 d.get("end_time"), _safe_int(d.get("downtime_minutes")),
                 d.get("priority") or "متوسط", d.get("status") or "باز",
                 d.get("root_cause"), d.get("action_taken"), d.get("parts_used"),
                 d.get("technician_name"), tech_un, d.get("created_by"),
                 d.get("created_at"), d.get("updated_at")))
            added += 1
    return jsonify({"ok": True, "added": added})

# ---------------- پیام‌ها و درخواست‌ها ----------------
@app.get("/messages")
def get_messages():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        if u["role"] == "admin":
            rows = c.execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
        else:
            rows = c.execute("SELECT * FROM messages WHERE sender=? ORDER BY id DESC",
                             (u["username"],)).fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/messages")
def add_message():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    if not d.get("subject"):
        return jsonify({"error": "موضوع الزامی است"}), 400
    with db() as c:
        cur = c.execute("""INSERT INTO messages(sender,unit_id,subject,body,kind)
                           VALUES(?,?,?,?,?)""",
                        (u["username"], u.get("unit_id"),
                         d.get("subject"), d.get("body"),
                         d.get("kind", "درخواست")))
        return jsonify({"id": cur.lastrowid})


@app.patch("/messages/<int:msg_id>")
def update_message(msg_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط ادمین مجاز است"}), 403
    d = request.get_json(silent=True) or {}
    fields, args = [], []
    for k in ("status", "reply"):
        if k in d:
            fields.append(f"{k}=?")
            args.append(d[k])
    if fields:
        args.append(msg_id)
        with db() as c:
            c.execute(f"UPDATE messages SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})


# ---------------- آمار ----------------
@app.get("/stats")
def stats():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    with db() as c:
        total = c.execute("SELECT COUNT(*) n FROM work_orders").fetchone()["n"]
        done = c.execute("SELECT COUNT(*) n FROM work_orders WHERE status='بسته'").fetchone()["n"]
        open_ = c.execute("SELECT COUNT(*) n FROM work_orders WHERE status='باز'").fetchone()["n"]
        new_msgs = c.execute("SELECT COUNT(*) n FROM messages WHERE status='جدید'").fetchone()["n"]
    return jsonify({"total": total, "open": open_, "done": done,
                    "done_pct": round(done * 100 / total) if total else 0,
                    "new_messages": new_msgs})


# ---------------- مدیریت کاربران ----------------
@app.get("/users")
def get_users():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    # خواندن لیست برای همه کاربران لاگین‌شده مجاز است (برای انتخاب تکنسین)
    # افزودن و حذف کاربر همچنان فقط ادمین مجاز است
    with db() as c:
        rows = c.execute("SELECT id, username, full_name, role FROM users ORDER BY id").fetchall()
    return jsonify([dict(x) for x in rows])


@app.post("/users")
def add_user():
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط ادمین مجاز است"}), 403
    d = request.get_json(silent=True) or {}
    username = (d.get("username") or "").strip()
    password = d.get("password") or ""
    if not username or not password:
        return jsonify({"error": "نام کاربری و رمز الزامی است"}), 400
    with db() as c:
        if c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return jsonify({"error": "این نام کاربری قبلاً ثبت شده"}), 400
        cur = c.execute(
            "INSERT INTO users(username,password,full_name,role) VALUES(?,?,?,?)",
            (username, generate_password_hash(password), d.get("full_name") or username,
             d.get("role", "user")))
        return jsonify({"id": cur.lastrowid})


@app.delete("/users/<int:user_id>")
def delete_user(user_id):
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط ادمین مجاز است"}), 403
    with db() as c:
        row = c.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return jsonify({"error": "کاربر پیدا نشد"}), 404
        if row["username"] == "admin":
            return jsonify({"error": "حساب اصلی ادمین قابل حذف نیست"}), 400
        c.execute("DELETE FROM users WHERE id=?", (user_id,))
        # توکن‌های کاربر حذف‌شده هم باطل شوند
        c.execute("DELETE FROM tokens WHERE username=?", (row["username"],))
    return jsonify({"ok": True})

# ---------------- گزارش‌دهی پرسنل ----------------
@app.post("/work-orders/full/<int:wo_id>/report")
def submit_wo_report(wo_id):
    """تکنسینِ تعیین‌شده گزارش کار را برای مدیر ارسال می‌کند"""
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    report = (d.get("report_text") or "").strip()
    if not report:
        return jsonify({"error": "متن گزارش الزامی است"}), 400
    with db() as c:
        row = c.execute("SELECT technician_username FROM work_orders WHERE id=?", (wo_id,)).fetchone()
        if not row:
            return jsonify({"error": "دستور کار پیدا نشد"}), 404
        if u["role"] != "admin" and (row["technician_username"] or "") != u["username"]:
            return jsonify({"error": "فقط تکنسینِ تعیین‌شده برای این دستور کار مجاز است"}), 403
        fields = ["report_text=?", "report_status='ارسال شده'",
                  "report_submitted_at=datetime('now','localtime')",
                  "updated_at=datetime('now','localtime')"]
        args = [report]
        for k in ("action_taken", "parts_used", "start_time", "end_time",
                  "downtime_minutes", "status"):
            if k in d:
                fields.append(f"{k}=?"); args.append(d[k])
        args.append(wo_id)
        c.execute(f"UPDATE work_orders SET {', '.join(fields)} WHERE id=?", args)
    return jsonify({"ok": True})


@app.patch("/work-orders/full/<int:wo_id>/rate")
def rate_wo_report(wo_id):
    """مدیر به گزارش کار امتیاز (۰ تا ۵) می‌دهد"""
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u["role"] != "admin":
        return jsonify({"error": "فقط مدیر مجاز است"}), 403
    d = request.get_json(silent=True) or {}
    try:
        rating = float(d.get("report_rating"))
    except (TypeError, ValueError):
        return jsonify({"error": "امتیاز نامعتبر است"}), 400
    if not (0 <= rating <= 5):
        return jsonify({"error": "امتیاز باید بین ۰ تا ۵ باشد"}), 400
    with db() as c:
        if not c.execute("SELECT 1 FROM work_orders WHERE id=?", (wo_id,)).fetchone():
            return jsonify({"error": "دستور کار پیدا نشد"}), 404
        c.execute("""UPDATE work_orders SET report_rating=?, report_comment=?,
                     report_status='تأیید شده', updated_at=datetime('now','localtime')
                     WHERE id=?""", (rating, d.get("report_comment"), wo_id))
    return jsonify({"ok": True})


@app.get("/performance")
def performance():
    """کارنامه عملکرد پرسنل — مدیر همه را می‌بیند، کاربر فقط خودش را"""
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    q = """SELECT technician_username, technician_name,
                  COUNT(*) as total,
                  SUM(CASE WHEN status='بسته' THEN 1 ELSE 0 END) as closed,
                  SUM(CASE WHEN report_status='ارسال شده' THEN 1 ELSE 0 END) as pending_reports,
                  SUM(CASE WHEN report_status='تأیید شده' THEN 1 ELSE 0 END) as confirmed,
                  AVG(report_rating) as avg_rating,
                  AVG(CASE WHEN order_type='EM' THEN downtime_minutes END) as avg_downtime
           FROM work_orders
           WHERE technician_username IS NOT NULL AND technician_username != ''"""
    args = []
    if u["role"] != "admin":
        q += " AND technician_username=?"; args.append(u["username"])
    q += " GROUP BY technician_username, technician_name ORDER BY avg_rating DESC"
    with db() as c:
        rows = c.execute(q, args).fetchall()
    return jsonify([dict(x) for x in rows])
def run_server():
    serve(app, host="0.0.0.0", port=API_PORT)