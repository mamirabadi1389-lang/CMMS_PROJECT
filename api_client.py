# api_client.py
import requests

SERVER = "http://127.0.0.1:8000"
token = None
current_user = None


def set_server(url):
    global SERVER
    SERVER = url


def _headers():
    return {"token": token or ""}


def login(username, password):
    global token, current_user
    r = requests.post(f"{SERVER}/login",
                      json={"username": username, "password": password}, timeout=5)
    r.raise_for_status()
    current_user = r.json()
    token = current_user["token"]
    return current_user


def whoami():
    r = requests.get(f"{SERVER}/me", headers=_headers(), timeout=5)
    r.raise_for_status()
    return r.json()


# ---------------- پیام‌ها ⭐ ----------------
def send_message(subject, body, kind="درخواست"):
    r = requests.post(f"{SERVER}/messages", headers=_headers(),
                      json={"subject": subject, "body": body, "kind": kind}, timeout=5)
    r.raise_for_status()
    return r.json()


def get_messages():
    r = requests.get(f"{SERVER}/messages", headers=_headers(), timeout=5)
    r.raise_for_status()
    return r.json()


def update_message(msg_id, **fields):
    r = requests.patch(f"{SERVER}/messages/{msg_id}", headers=_headers(),
                       json=fields, timeout=5)
    r.raise_for_status()
    return r.json()


# ---------------- بقیه ----------------
def get_work_orders(unit_id=None):
    params = {"unit_id": unit_id} if unit_id else {}
    r = requests.get(f"{SERVER}/work-orders", headers=_headers(),
                     params=params, timeout=5)
    r.raise_for_status()
    return r.json()


def add_work_order(**fields):
    r = requests.post(f"{SERVER}/work-orders", headers=_headers(), json=fields, timeout=5)
    r.raise_for_status()
    return r.json()


def update_work_order(wo_id, **fields):
    r = requests.patch(f"{SERVER}/work-orders/{wo_id}", headers=_headers(),
                       json=fields, timeout=5)
    r.raise_for_status()
    return r.json()


def get_stats():
    r = requests.get(f"{SERVER}/stats", headers=_headers(), timeout=5)
    r.raise_for_status()
    return r.json()


def get_units():
    r = requests.get(f"{SERVER}/units", headers=_headers(), timeout=5)
    r.raise_for_status()
    return r.json()

# ---------------- مدیریت کاربران ----------------
def get_users():
    r = requests.get(f"{SERVER}/users", headers=_headers(), timeout=5)
    r.raise_for_status()
    return r.json()


def add_user(username, password, full_name, role="user"):
    r = requests.post(f"{SERVER}/users", headers=_headers(),
                      json={"username": username, "password": password,
                            "full_name": full_name, "role": role}, timeout=5)
    r.raise_for_status()
    return r.json()


def delete_user(user_id):
    r = requests.delete(f"{SERVER}/users/{user_id}", headers=_headers(), timeout=5)
    r.raise_for_status()
    return r.json()

# ============ دستور کارهای مشترک (سرور) ============
import requests

def _wo_token():
    """پیدا کردن توکن لاگین (اسم متغیر در نسخه‌های مختلف فرق دارد)"""
    g = globals()
    for name in ("TOKEN", "token", "_token", "AUTH", "auth_token"):
        v = g.get(name)
        if isinstance(v, str) and v.strip():
            return v
    u = g.get("current_user")
    if isinstance(u, dict):
        for k in ("token", "TOKEN", "auth"):
            v = u.get(k)
            if isinstance(v, str) and v.strip():
                return v
    import re
    pat = re.compile(r"^[0-9a-f]{32}$")   # توکن‌ها ۳۲ کاراکتر hex هستند
    for v in list(g.values()):
        if isinstance(v, str) and pat.match(v):
            return v
        if isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, str) and pat.match(vv):
                    return vv
    return None

def _wo_headers():
    t = _wo_token()
    return {"token": t} if t else {}

def wo_list():
    r = requests.get(f"{SERVER}/work-orders/full", headers=_wo_headers(), timeout=30)
    r.raise_for_status(); return r.json()

def wo_create(data):
    r = requests.post(f"{SERVER}/work-orders/full", json=data, headers=_wo_headers(), timeout=30)
    r.raise_for_status(); return r.json()

def wo_update(wo_id, data):
    r = requests.patch(f"{SERVER}/work-orders/full/{wo_id}", json=data, headers=_wo_headers(), timeout=30)
    r.raise_for_status(); return r.json()

def wo_delete(wo_id):
    r = requests.delete(f"{SERVER}/work-orders/full/{wo_id}", headers=_wo_headers(), timeout=30)
    r.raise_for_status(); return r.json()

def wo_migrate(rows):
    r = requests.post(f"{SERVER}/work-orders/migrate", json=rows, headers=_wo_headers(), timeout=60)
    r.raise_for_status(); return r.json()