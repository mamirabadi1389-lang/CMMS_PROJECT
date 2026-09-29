# api_client_ext.py
"""
توابع کلاینت برای DCC (مخزن اسناد تجهیزات) و ثبت تجربیات (دانشنامه‌ی فنی).
این فایل کاملاً جدید است و هیچ خط از api_client.py را تغییر نمی‌دهد؛
فقط از همان api_client.SERVER و api_client.token فعلی استفاده می‌کند.
"""
import os
import requests
import api_client


def _headers():
    return {"token": api_client.token or ""}


# ================= DCC =================
def dcc_list(eq_name=None, category=None, q=None):
    params = {}
    if eq_name:
        params["eq_name"] = eq_name
    if category:
        params["category"] = category
    if q:
        params["q"] = q
    r = requests.get(f"{api_client.SERVER}/dcc/documents", headers=_headers(),
                     params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def dcc_upload(file_path, title, category="سایر", eq_name="", description=""):
    data = {"title": title, "category": category,
            "eq_name": eq_name, "description": description}
    files = None
    fh = None
    try:
        if file_path:
            fh = open(file_path, "rb")
            files = {"file": (os.path.basename(file_path), fh)}
        r = requests.post(f"{api_client.SERVER}/dcc/documents", headers=_headers(),
                          data=data, files=files, timeout=60)
        r.raise_for_status()
        return r.json()
    finally:
        if fh:
            fh.close()


def dcc_download(doc_id, save_path):
    r = requests.get(f"{api_client.SERVER}/dcc/documents/{doc_id}/download",
                     headers=_headers(), timeout=60)
    r.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(r.content)
    return save_path


def dcc_delete(doc_id):
    r = requests.delete(f"{api_client.SERVER}/dcc/documents/{doc_id}",
                        headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


# ================= تجربیات =================
def exp_list(category=None, eq_name=None, q=None):
    params = {}
    if category:
        params["category"] = category
    if eq_name:
        params["eq_name"] = eq_name
    if q:
        params["q"] = q
    r = requests.get(f"{api_client.SERVER}/experience", headers=_headers(),
                     params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def exp_create(data):
    r = requests.post(f"{api_client.SERVER}/experience", headers=_headers(),
                      json=data, timeout=10)
    r.raise_for_status()
    return r.json()


def exp_update(exp_id, data):
    r = requests.patch(f"{api_client.SERVER}/experience/{exp_id}", headers=_headers(),
                       json=data, timeout=10)
    r.raise_for_status()
    return r.json()


def exp_delete(exp_id):
    r = requests.delete(f"{api_client.SERVER}/experience/{exp_id}",
                        headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


# ================= تجهیزات (دسته‌بندی + تجهیزات) =================
def eqcat_list():
    r = requests.get(f"{api_client.SERVER}/equip/categories", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def eqcat_create(name, icon=None):
    r = requests.post(f"{api_client.SERVER}/equip/categories", headers=_headers(),
                      json={"name": name, "icon": icon}, timeout=15)
    r.raise_for_status()
    return r.json()


def eqcat_update(cat_id, data):
    r = requests.patch(f"{api_client.SERVER}/equip/categories/{cat_id}", headers=_headers(),
                       json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def eqcat_delete(cat_id):
    r = requests.delete(f"{api_client.SERVER}/equip/categories/{cat_id}", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def equip_list():
    r = requests.get(f"{api_client.SERVER}/equip/full", headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


def equip_create(data):
    r = requests.post(f"{api_client.SERVER}/equip/full", headers=_headers(),
                      json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def equip_update(eq_id, data):
    r = requests.patch(f"{api_client.SERVER}/equip/full/{eq_id}", headers=_headers(),
                       json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def equip_delete(eq_id):
    r = requests.delete(f"{api_client.SERVER}/equip/full/{eq_id}", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def equip_migrate(rows):
    r = requests.post(f"{api_client.SERVER}/equip/migrate", headers=_headers(),
                      json=rows, timeout=30)
    r.raise_for_status()
    return r.json()


# ================= برنامه‌های PM =================
def pm_list():
    r = requests.get(f"{api_client.SERVER}/pm/schedules", headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


def pm_create(data):
    r = requests.post(f"{api_client.SERVER}/pm/schedules", headers=_headers(),
                      json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def pm_update(pm_id, data):
    r = requests.patch(f"{api_client.SERVER}/pm/schedules/{pm_id}", headers=_headers(),
                       json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def pm_delete(pm_id):
    r = requests.delete(f"{api_client.SERVER}/pm/schedules/{pm_id}", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def pm_migrate(rows):
    r = requests.post(f"{api_client.SERVER}/pm/migrate", headers=_headers(),
                      json=rows, timeout=30)
    r.raise_for_status()
    return r.json()


# ================= قطعات یدکی =================
def parts_list():
    r = requests.get(f"{api_client.SERVER}/spare-parts", headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


def parts_create(data):
    r = requests.post(f"{api_client.SERVER}/spare-parts", headers=_headers(),
                      json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def parts_update(part_id, data):
    r = requests.patch(f"{api_client.SERVER}/spare-parts/{part_id}", headers=_headers(),
                       json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def parts_delete(part_id):
    r = requests.delete(f"{api_client.SERVER}/spare-parts/{part_id}", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def parts_migrate(rows):
    r = requests.post(f"{api_client.SERVER}/spare-parts/migrate", headers=_headers(),
                      json=rows, timeout=30)
    r.raise_for_status()
    return r.json()
# ================= متادیتای همگام‌سازی =================
def sync_meta():
    """امضای سبکِ تغییرات سرور — برای poll سه‌ثانیه‌ای کلاینت"""
    r = requests.get(f"{api_client.SERVER}/sync/meta", headers=_headers(), timeout=4)
    r.raise_for_status()
    return r.json()
# ================= گزارش‌دهی پرسنل =================
def wo_submit_report(wo_id, data):
    r = requests.post(f"{api_client.SERVER}/work-orders/full/{wo_id}/report",
                      headers=_headers(), json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def wo_rate(wo_id, rating, comment=None):
    r = requests.patch(f"{api_client.SERVER}/work-orders/full/{wo_id}/rate",
                       headers=_headers(),
                       json={"report_rating": rating, "report_comment": comment},
                       timeout=15)
    r.raise_for_status()
    return r.json()


def performance_list():
    r = requests.get(f"{api_client.SERVER}/performance",
                     headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()