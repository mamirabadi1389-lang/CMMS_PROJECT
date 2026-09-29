"""
CMMS Database Module - SQLite backend
"""
import sqlite3, os, json, sys
from datetime import datetime, date, timedelta


def _resolve_db_path():
    """
    مسیر دیتابیس رو تعیین می‌کنه.
    - وقتی به صورت exe (PyInstaller) اجرا میشه: کنار خود اجرایی ننویس
      (معمولا Program Files هست و کاربر عادی اجازه‌ی نوشتن نداره)،
      به‌جاش توی %LOCALAPPDATA%\\CMMS بنویس که همیشه قابل نوشتنه.
    - وقتی مستقیم با پایتون اجرا میشه (توسعه): همون کنار فایل سورس بمونه.
    """
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        base = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CMMS"
        )
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "cmms_data.db")


DB_PATH = _resolve_db_path()

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_database():
    conn = get_connection(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS equipment_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        icon TEXT DEFAULT '⚙️', created_at TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER,
        name TEXT NOT NULL, code TEXT, location TEXT,
        brand TEXT, model TEXT, serial_number TEXT, install_date TEXT,
        status TEXT DEFAULT 'فعال', notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (category_id) REFERENCES equipment_categories(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS work_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, order_number TEXT UNIQUE,
        order_type TEXT NOT NULL CHECK(order_type IN ('PM','EM')),
        equipment_id INTEGER, operator TEXT NOT NULL,
        description TEXT NOT NULL, work_date TEXT NOT NULL,
        start_time TEXT, end_time TEXT, downtime_minutes INTEGER DEFAULT 0,
        priority TEXT DEFAULT 'متوسط', status TEXT DEFAULT 'باز',
        root_cause TEXT, action_taken TEXT, parts_used TEXT,
        technician_name TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (equipment_id) REFERENCES equipment(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS pm_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_id INTEGER,
        task_name TEXT NOT NULL, frequency_days INTEGER NOT NULL,
        last_done TEXT, next_due TEXT, operator TEXT,
        estimated_hours REAL DEFAULT 1.0, checklist TEXT, active INTEGER DEFAULT 1,
        FOREIGN KEY (equipment_id) REFERENCES equipment(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS spare_parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        part_number TEXT, category TEXT, quantity INTEGER DEFAULT 0,
        unit TEXT DEFAULT 'عدد', min_stock INTEGER DEFAULT 2,
        location TEXT, supplier TEXT, unit_price REAL DEFAULT 0,
        notes TEXT, created_at TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT)""")
    conn.commit(); conn.close()
    _seed_default_data()

def _seed_default_data():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM equipment_categories")
    if c.fetchone()[0] > 0:
        conn.close(); return
    categories = [("موتورها و درایوها","🔧"),("پمپ‌ها","💧"),("کمپرسورها","🌀"),
                  ("سیستم برق","⚡"),("سیستم تاسیسات","🏭"),("انتقال قدرت","⚙️"),
                  ("سیستم هیدرولیک","🛢️"),("سیستم پنوماتیک","💨"),
                  ("تجهیزات ایمنی","🛡️"),("سیستم خنک‌کاری","❄️")]
    for name, icon in categories:
        c.execute("INSERT INTO equipment_categories (name,icon) VALUES (?,?)",(name,icon))
    c.execute("SELECT id,name FROM equipment_categories")
    cat_map = {r["name"]:r["id"] for r in c.fetchall()}
    default_equipment = [
        (cat_map["موتورها و درایوها"],"الکتروموتور خط تولید ۱","EM-001","سالن تولید","ABB","M2BAX 160","","1401/01/01"),
        (cat_map["موتورها و درایوها"],"اینورتر دستگاه پرس","INV-001","خط پرس","Siemens","G120","","1401/06/01"),
        (cat_map["پمپ‌ها"],"پمپ آب سرد","PUMP-001","موتورخانه","Grundfos","CM5-6","","1400/03/15"),
        (cat_map["پمپ‌ها"],"پمپ هیدرولیک پرس ۱","PUMP-002","خط پرس","Bosch Rexroth","A10VS","","1400/05/20"),
        (cat_map["کمپرسورها"],"کمپرسور اسکرو ۱۵۰ کیلووات","COMP-001","اتاق کمپرسور","Atlas Copco","GA110","","1399/08/01"),
        (cat_map["سیستم برق"],"ترانسفورماتور اصلی ۱۰۰۰ KVA","TRANS-001","پست برق","Iran Transfo","IT-1000","","1398/01/01"),
        (cat_map["سیستم برق"],"تابلو برق اصلی MDB","MDB-001","اتاق برق","Schneider","Prisma","","1399/01/01"),
        (cat_map["سیستم برق"],"UPS اتاق کنترل","UPS-001","اتاق کنترل","APC","Smart-UPS 10K","","1401/01/01"),
        (cat_map["سیستم تاسیسات"],"بویلر بخار ۵ تن","BOIL-001","موتورخانه","Baltur","BTG-5","","1399/06/01"),
        (cat_map["سیستم تاسیسات"],"چیلر ۵۰۰ تن تبرید","CHIL-001","بام","Carrier","30XA-500","","1400/02/01"),
        (cat_map["سیستم تاسیسات"],"دیگ آبگرم","BOIL-002","موتورخانه","Irani","IR-200","","1400/08/01"),
        (cat_map["انتقال قدرت"],"گیربکس خط نوار نقاله","GEAR-001","انبار","SEW","SA77","","1401/01/01"),
        (cat_map["سیستم هیدرولیک"],"پاور پک هیدرولیک پرس ۲","HYD-001","خط پرس","Parker","PVP16","","1400/07/01"),
        (cat_map["سیستم پنوماتیک"],"واحد مراقبت هوای فشرده","PNEU-001","خط مونتاژ","SMC","AC40A","","1401/04/01"),
        (cat_map["تجهیزات ایمنی"],"سیستم اطفاء حریق","FIRE-001","سراسر کارخانه","Kidde","FM-200","","1400/01/01"),
        (cat_map["سیستم خنک‌کاری"],"برج خنک‌کن","CT-001","بام","Delta","CT-200","","1400/03/01"),
    ]
    for eq in default_equipment:
        c.execute("INSERT OR IGNORE INTO equipment (category_id,name,code,location,brand,model,serial_number,install_date,status) VALUES (?,?,?,?,?,?,?,?,'فعال')",eq)
    today = date.today().isoformat()
    pm_defaults = [(1,"روغنکاری بیرینگ‌ها",30,"مکانیک",2.0),(1,"بازرسی اتصالات برقی",90,"برق",1.0),
                   (3,"تعویض روغن",90,"مکانیک",3.0),(5,"بررسی فشار بویلر",7,"تاسیسات",1.0),
                   (6,"تمیزکاری چیلر",180,"تاسیسات",4.0),(7,"بازرسی ترانسفورماتور",365,"برق",2.0)]
    for eq_id,task,freq,op,hrs in pm_defaults:
        nxt = (date.today()+timedelta(days=freq)).isoformat()
        c.execute("INSERT INTO pm_schedules (equipment_id,task_name,frequency_days,last_done,next_due,operator,estimated_hours) VALUES (?,?,?,?,?,?,?)",(eq_id,task,freq,today,nxt,op,hrs))
    parts = [("بیرینگ SKF 6205","6205-2RS","بیرینگ",10,"عدد",3),
             ("بیرینگ SKF 6208","6208-2RS","بیرینگ",8,"عدد",2),
             ("تسمه V-Belt B80","B80","تسمه",5,"عدد",2),
             ("روغن هیدرولیک ISO 46","HLP46","روانکار",200,"لیتر",50),
             ("گریس چندمنظوره","NLGI-2","روانکار",20,"کیلو",5),
             ("فیلتر هوا کمپرسور","AF-001","فیلتر",4,"عدد",2),
             ("فیوز 63A","FUSE-63","برق",20,"عدد",5),
             ("کنتاکتور LS MC-40","MC-40","برق",5,"عدد",2),
             ("واشر تفلون ۱ اینچ","GAS-1","لوله‌کشی",30,"عدد",10),
             ("شیر برقی ۲۴V","SOL-24V","برق",4,"عدد",2)]
    for p in parts:
        c.execute("INSERT INTO spare_parts (name,part_number,category,quantity,unit,min_stock) VALUES (?,?,?,?,?,?)",p)
    for k,v in [("factory_name","کارخانه نمونه صنعتی"),("working_hours_per_day","16")]:
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)",(k,v))
    conn.commit(); conn.close()

def fetch_all(query, params=()):
    conn = get_connection(); c = conn.cursor()
    c.execute(query, params); rows = c.fetchall(); conn.close()
    return [dict(r) for r in rows]

def fetch_one(query, params=()):
    conn = get_connection(); c = conn.cursor()
    c.execute(query, params); row = c.fetchone(); conn.close()
    return dict(row) if row else None

def execute(query, params=()):
    conn = get_connection(); c = conn.cursor()
    c.execute(query, params); last_id = c.lastrowid
    conn.commit(); conn.close(); return last_id

def generate_order_number(order_type):
    prefix = "PM" if order_type=="PM" else "EM"
    ym = date.today().strftime("%Y%m")
    existing = fetch_all("SELECT order_number FROM work_orders WHERE order_number LIKE ? ORDER BY id DESC LIMIT 1",(f"{prefix}-{ym}%",))
    seq = int(existing[0]["order_number"].split("-")[-1])+1 if existing else 1
    return f"{prefix}-{ym}-{seq:04d}"

def calc_mttr(month=None, operator=None, since=None):
    q = "SELECT AVG(downtime_minutes) as avg_repair FROM work_orders WHERE order_type='EM' AND status='بسته' AND downtime_minutes>0"
    filters=[]; params=[]
    if month: filters.append("strftime('%Y-%m',work_date)=?"); params.append(month)
    if since: filters.append("work_date>=?"); params.append(since)
    if operator: filters.append("operator=?"); params.append(operator)
    if filters: q+=" AND "+" AND ".join(filters)
    row = fetch_one(q, params)
    return round(row["avg_repair"]/60,2) if row and row["avg_repair"] else 0

def calc_mtbf(equipment_id=None, month=None, since=None):
    q = "SELECT work_date,equipment_id FROM work_orders WHERE order_type='EM' AND status='بسته'"
    filters=[]; params=[]
    if equipment_id: filters.append("equipment_id=?"); params.append(equipment_id)
    if month: filters.append("strftime('%Y-%m',work_date)=?"); params.append(month)
    if since: filters.append("work_date>=?"); params.append(since)
    if filters: q+=" AND "+" AND ".join(filters)
    q+=" ORDER BY equipment_id,work_date"
    rows = fetch_all(q, params)
    if len(rows)<2: return 0
    gaps=[]; prev=None; prev_eq=None
    for r in rows:
        if prev and r["equipment_id"]==prev_eq:
            d1=datetime.strptime(prev,"%Y-%m-%d"); d2=datetime.strptime(r["work_date"],"%Y-%m-%d")
            gap=(d2-d1).days*24
            if gap>0: gaps.append(gap)
        prev=r["work_date"]; prev_eq=r["equipment_id"]
    return round(sum(gaps)/len(gaps),2) if gaps else 0

def get_monthly_summary(month):
    em=fetch_one("SELECT COUNT(*) as cnt,SUM(downtime_minutes) as total_down FROM work_orders WHERE order_type='EM' AND strftime('%Y-%m',work_date)=?",(month,))
    pm=fetch_one("SELECT COUNT(*) as cnt FROM work_orders WHERE order_type='PM' AND strftime('%Y-%m',work_date)=?",(month,))
    per_op=fetch_all("SELECT operator,COUNT(*) as cnt,SUM(downtime_minutes) as down FROM work_orders WHERE strftime('%Y-%m',work_date)=? GROUP BY operator",(month,))
    return {"em_count":em["cnt"] if em else 0,"pm_count":pm["cnt"] if pm else 0,
            "total_downtime_min":em["total_down"] or 0 if em else 0,
            "per_operator":per_op,"mttr":calc_mttr(month),"mtbf":calc_mtbf(month=month)}

def get_dashboard_summary(days=30):
    """
    خلاصه‌ی آماری داشبورد بر اساس یه بازه‌ی زمانیِ غلتان (مثلا ۳۰ روز اخیر)
    به‌جای «ماه تقویمی جاری». این‌طوری با شروع ماه جدید ناگهان صفر نمیشه و
    همیشه وضعیت واقعیِ اخیر رو نشون میده.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    em = fetch_one("SELECT COUNT(*) as cnt,SUM(downtime_minutes) as total_down FROM work_orders WHERE order_type='EM' AND work_date>=?", (since,))
    pm = fetch_one("SELECT COUNT(*) as cnt FROM work_orders WHERE order_type='PM' AND work_date>=?", (since,))
    per_op = fetch_all("SELECT operator,COUNT(*) as cnt,SUM(downtime_minutes) as down FROM work_orders WHERE work_date>=? GROUP BY operator", (since,))
    return {"em_count": em["cnt"] if em else 0, "pm_count": pm["cnt"] if pm else 0,
            "total_downtime_min": (em["total_down"] or 0) if em else 0,
            "per_operator": per_op, "mttr": calc_mttr(since=since), "mtbf": calc_mtbf(since=since),
            "days": days}
