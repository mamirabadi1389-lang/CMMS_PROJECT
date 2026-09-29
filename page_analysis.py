"""
CMMS Data Analysis Page — AI-Powered Predictive Maintenance
پیش‌بینی خرابی، تحلیل ریسک، و آنالیز پیشرفته داده‌ها
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime, timedelta
import csv, os, tempfile, webbrowser, threading, json
from collections import Counter, defaultdict

# ── ML / Data libs (optional but recommended) ───────────────────────────
try:
    import numpy as np
    import pandas as pd
    NP_PD_OK = True
    _NP_PD_ERROR = None
except ImportError as e:
    NP_PD_OK = False
    _NP_PD_ERROR = str(e)
    print(f"[DATA WARNING] Import failed: {e}")
    print("[DATA WARNING] Run: pip install pandas numpy")

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, IsolationForest
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    SKLEARN_OK = True
    _SKLEARN_ERROR = None
except ImportError as e:
    SKLEARN_OK = False
    _SKLEARN_ERROR = str(e)
    print(f"[ML WARNING] Import failed: {e}")
    print("[ML WARNING] Run: pip install scikit-learn")

ML_OK = NP_PD_OK and SKLEARN_OK
_ML_ERROR = " / ".join([m for m in (_NP_PD_ERROR, _SKLEARN_ERROR) if m]) or None

# ── Excel export (optional) ──────────────────────────────────────────────
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False

# ── Persian/Arabic text shaping for Matplotlib ───────────────────────────
# Matplotlib does not apply Arabic/Persian glyph joining or the bidi
# algorithm itself, so Persian strings render as disconnected, reversed
# letters. arabic_reshaper joins the letters correctly and python-bidi
# reorders them into correct visual (right-to-left) order.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display as _bidi_display
    BIDI_OK = True
except ImportError:
    BIDI_OK = False
    print("[RTL WARNING] Run: pip install arabic-reshaper python-bidi")


def fa(text):
    """Reshape a Persian/mixed string so it displays correctly inside
    Matplotlib (titles, axis labels, legends, tick labels, pie labels...).
    Safe to call on any string, including pure-English/numeric ones."""
    if text is None:
        return text
    text = str(text)
    if not BIDI_OK:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return _bidi_display(reshaped)
    except Exception:
        return text


def rtl(text):
    """Prefix a Persian sentence with a Right-to-Left Mark (U+200F).
    Tk's built-in bidi handling is minimal: when a sentence *starts* with
    a number, a Latin word, or punctuation like «, it can misjudge the
    paragraph's base direction and scramble the first word. The RLM is
    invisible but tells Tk "this line is RTL", which fixes it. Use this
    for any dynamically-built Persian string shown in a tk.Label,
    especially ones built with f-strings that interpolate numbers."""
    return "\u200f" + text

# ── Visualization ───────────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    matplotlib.rcParams["axes.unicode_minus"] = False
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# ── Bundled Persian font for charts ──────────────────────────────────────
# IMPORTANT: setting matplotlib.rcParams["font.family"] to a *fallback list*
# (e.g. ["Tahoma","Vazirmatn","Arial"]) does NOT reliably render reshaped
# Persian text — matplotlib can pick glyphs for individual characters from
# whichever font in the list happens to have them, which breaks the joined
# letter-forms produced by arabic_reshaper back apart. That is exactly why
# the charts were showing disconnected/reversed Farsi.
#
# The fix is to ship one known-good Persian font with the app and force it
# explicitly on every chart text element (title/labels/ticks/legend), so
# there is no ambiguity about which font renders the reshaped glyphs.
#
# Put a Vazirmatn-Regular.ttf (or any Persian TTF you like) in a "fonts"
# folder next to this file, and make sure PyInstaller/Inno Setup bundles
# that folder too (add it to the .spec `datas` list).
PERSIAN_FONT = None
if MATPLOTLIB_OK:
    _FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Vazirmatn-Regular.ttf")
    if os.path.exists(_FONT_PATH):
        try:
            fm.fontManager.addfont(_FONT_PATH)
            PERSIAN_FONT = fm.FontProperties(fname=_FONT_PATH)
        except Exception as e:
            print(f"[FONT WARNING] Could not load bundled Persian font: {e}")
    else:
        print(f"[FONT WARNING] Persian font not found at {_FONT_PATH} — "
              "Farsi chart text may render incorrectly. Place a TTF there.")


def _apply_fa_font(ax):
    """Force every text artist on this Axes (title, axis labels, tick
    labels, legend, in-plot annotations, pie-chart labels) onto the
    bundled Persian font. Call this right before embedding the figure,
    after all set_title/set_xlabel/legend/text calls are done."""
    if PERSIAN_FONT is None:
        return
    texts = [ax.title, ax.xaxis.label, ax.yaxis.label]
    texts += list(ax.get_xticklabels()) + list(ax.get_yticklabels())
    texts += list(ax.texts)
    leg = ax.get_legend()
    if leg is not None:
        texts += list(leg.get_texts())
    for t in texts:
        try:
            t.set_fontproperties(PERSIAN_FONT)
        except Exception:
            pass

import database as db
from styles import COLORS, FONTS, OPERATOR_COLORS
from widgets import SectionTitle, IconButton, StyledTreeview


class DataAnalysisPage(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.app = app
        self._charts = []
        self._chart_widgets = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        hdr = tk.Frame(self, bg=COLORS["bg_header"])
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text="تحلیل داده‌ها و پیش‌بینی هوشمند",
                 font=FONTS["title"], bg=COLORS["bg_header"],
                 fg=COLORS["text_primary"]).pack(side="right", pady=12)

        # نوار ابزار رو از عنوان جدا کردیم و توی یه ردیف کامل و مستقل
        # زیرش گذاشتیم. قبلا هر دو توی یه ردیف افقی بودن و وقتی پنجره
        # باریک می‌شد، عنوان بلند فضای دکمه‌ها (از جمله «پرینت گزارش») رو
        # می‌گرفت و اونا کاملا از عرض پنجره بیرون می‌زدن (نه فقط مخفی -
        # واقعا خارج از ناحیه‌ی قابل نمایش بودن).
        toolbar = tk.Frame(self, bg=COLORS["bg_header"])
        toolbar.pack(fill="x", padx=20, pady=(4, 8))

        self.months_var = tk.StringVar(value="6")
        tk.Label(toolbar, text="ماه گذشته:", font=FONTS["body"],
                 bg=COLORS["bg_header"], fg=COLORS["text_secondary"]).pack(side="right", padx=4)
        ttk.Combobox(toolbar, textvariable=self.months_var,
                     values=["3", "6", "12", "24"], width=6, state="readonly",
                     font=FONTS["body"]).pack(side="right", padx=4)

        IconButton(toolbar, "بروزرسانی", "🔄", self.refresh,
                   color=COLORS["accent"]).pack(side="left", padx=8)
        IconButton(toolbar, "خروجی CSV کامل", "📥", self._export_full_csv,
                   color=COLORS["green"]).pack(side="left", padx=4)
        IconButton(toolbar, "خروجی Excel کامل", "📊", self._export_full_excel,
                   color=COLORS["green"]).pack(side="left", padx=4)
        IconButton(toolbar, "پرینت گزارش", "🖨️", self._print_report,
                   color=COLORS["blue"]).pack(side="left", padx=4)

        canvas = tk.Canvas(self, bg=COLORS["bg_dark"], highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                          bg=COLORS["bg_dark"], troughcolor=COLORS["bg_card"])
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        self.content = tk.Frame(canvas, bg=COLORS["bg_dark"])
        win = canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))


    def refresh(self):
        months = int(self.months_var.get())
        start_date = (date.today() - timedelta(days=30*months)).isoformat()

        def load():
            wo_rows = db.fetch_all("""
                SELECT wo.*, e.name as eq_name, e.code as eq_code,
                       e.install_date, e.status as eq_status, e.category_id
                FROM work_orders wo
                LEFT JOIN equipment e ON wo.equipment_id=e.id
                WHERE wo.work_date >= ?
                ORDER BY wo.work_date
            """, (start_date,))

            all_wo = db.fetch_all("""
                SELECT wo.*, e.name as eq_name, e.install_date
                FROM work_orders wo
                LEFT JOIN equipment e ON wo.equipment_id=e.id
                ORDER BY wo.work_date
            """)

            eq_rows = db.fetch_all("SELECT * FROM equipment")
            cat_rows = db.fetch_all("SELECT * FROM equipment_categories")
            pm_rows = db.fetch_all("SELECT * FROM pm_schedules WHERE active=1")

            self.after(0, lambda: self._render(wo_rows, all_wo, eq_rows, cat_rows, pm_rows, months))

        threading.Thread(target=load, daemon=True).start()

    def _render(self, wo_rows, all_wo, eq_rows, cat_rows, pm_rows, months):
        for c in self._charts:
            try: plt.close(c)
            except: pass
        self._charts.clear()
        self._chart_widgets.clear()
        for w in self.content.winfo_children():
            w.destroy()

        # Auto-generated Persian narrative first — gives a quick read of
        # the whole page before anyone scrolls into the charts.
        self._smart_insights_card(wo_rows, eq_rows, months)

        # AI Section
        if ML_OK:
            self._predictive_maintenance_card(all_wo, eq_rows, months)
            self._anomaly_detection_card(all_wo, eq_rows)
            self._equipment_risk_card(all_wo, eq_rows)
            self._forecast_card(all_wo, months)
        else:
            self._ml_warning_card()

        self._pareto_card(wo_rows)
        self._trend_card(wo_rows, months)
        self._operator_card(wo_rows)
        self._technician_card(wo_rows)
        self._failure_card(wo_rows)
        self._category_card(wo_rows, eq_rows, cat_rows)
        self._cost_card(wo_rows)
        self._pm_em_ratio_card(wo_rows, months)
        self._stats_table_card(wo_rows, eq_rows, cat_rows)

    # ═══════════════════════════════════════════════════════════════════════
    #  🤖 1. PREDICTIVE MAINTENANCE — Failure Prediction
    # ═══════════════════════════════════════════════════════════════════════
    def _predictive_maintenance_card(self, all_wo, eq_rows, months):
        card = self._analysis_card("🤖  پیش‌بینی خرابی (Predictive Maintenance)",
                                   "احتمال خرابی تجهیزات در ۳۰ روز آینده — مدل Random Forest")

        # Build dataset per equipment
        today = date.today()
        features = []
        predictions = []

        for eq in eq_rows:
            eq_id = eq["id"]
            eq_wo = [w for w in all_wo if w["equipment_id"] == eq_id]
            em_wo = [w for w in eq_wo if w["order_type"] == "EM"]

            # Feature 1: Days since install
            try:
                install = datetime.strptime(eq["install_date"] or "1400-01-01", "%Y-%m-%d").date()
                days_old = (today - install).days
            except:
                days_old = 365

            # Feature 2: Total EM count (last 12 months)
            em_count = len(em_wo)

            # Feature 3: Total downtime (hours)
            total_down = sum(w["downtime_minutes"] or 0 for w in em_wo) / 60

            # Feature 4: Days since last EM
            if em_wo:
                last_em = max(datetime.strptime(w["work_date"], "%Y-%m-%d").date() for w in em_wo)
                days_since_last = (today - last_em).days
            else:
                days_since_last = 999

            # Feature 5: PM completion rate
            pm_done = len([w for w in eq_wo if w["order_type"] == "PM" and w["status"] == "بسته"])
            pm_total = len([w for w in eq_wo if w["order_type"] == "PM"])
            pm_rate = pm_done / max(pm_total, 1)

            # Target: Did it fail in last 3 months? (proxy for risk)
            recent_em = len([w for w in em_wo if w["work_date"] >= (today - timedelta(days=90)).isoformat()])

            features.append([days_old, em_count, total_down, days_since_last, pm_rate])
            predictions.append({
                "eq_id": eq_id, "name": eq["name"] or "نامشخص", "code": eq["code"] or "-",
                "days_old": days_old, "em_count": em_count, "total_down": round(total_down, 1),
                "days_since_last": days_since_last, "pm_rate": round(pm_rate, 2),
                "recent_em": recent_em
            })

        if len(features) < 5:
            tk.Label(card, text="داده کافی برای مدل‌سازی وجود ندارد (حداقل ۵ تجهیز)",
                     font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=20)
            return

        # Train model
        X = np.array(features)
        y = np.array([1 if p["recent_em"] > 0 else 0 for p in predictions])  # 1 = high risk

        # اگه داده فقط یک کلاس داشته باشه (مثلا هیچ تجهیزی اخیرا EM نداشته یا
        # برعکس همه داشتن)، RandomForest قابل آموزش معنادار نیست و
        # predict_proba فقط یک ستون برمی‌گردونه (نه دو ستون برای کلاس ۰ و ۱)
        # که باعث IndexError میشد. این حالت رو جدا مدیریت می‌کنیم.
        clf = None
        if len(np.unique(y)) < 2:
            only_class = int(y[0])
            for i, p in enumerate(predictions):
                p["risk_score"] = 100.0 if only_class == 1 else 0.0
                p["risk_level"] = "🔴 بحرانی" if only_class == 1 else "🟢 کم"
            tk.Label(card, text="⚠️ همه‌ی تجهیزات در یک وضعیت ریسک مشابه‌اند؛ "
                                 "برای امتیازدهی دقیق‌تر داده‌ی متنوع‌تری لازم است.",
                     font=FONTS["small"], bg=COLORS["bg_card"],
                     fg=COLORS["text_muted"]).pack(padx=8, pady=(0, 4), anchor="e")
        else:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            clf = RandomForestClassifier(n_estimators=100, random_state=42)
            clf.fit(X_scaled, y)

            # Predict risk score (probability of class 1) - امن در برابر اینکه
            # ترتیب کلاس‌ها همیشه [0, 1] نباشه
            proba_all = clf.predict_proba(X_scaled)
            classes = list(clf.classes_)
            if 1 in classes:
                proba = proba_all[:, classes.index(1)]
            else:
                proba = np.zeros(len(predictions))

            for i, p in enumerate(predictions):
                p["risk_score"] = round(proba[i] * 100, 1)
                p["risk_level"] = "🔴 بحرانی" if proba[i] > 0.6 else ("🟡 متوسط" if proba[i] > 0.3 else "🟢 کم")

        predictions.sort(key=lambda x: x["risk_score"], reverse=True)

        # Top risky equipment table
        tree = StyledTreeview(card, columns=(
            "تجهیز", "کد", "ریسک", "امتیاز", "تعداد EM", "توقف(h)", "آخرین EM(روز)", "عمر(روز)"
        ))
        tree.pack(fill="x", padx=8, pady=8)

        for p in predictions[:15]:
            tag = "critical" if p["risk_score"] > 60 else ("warn" if p["risk_score"] > 30 else "ok")
            tree.insert((
                p["name"], p["code"], p["risk_level"], str(p["risk_score"]) + "%",
                p["em_count"], p["total_down"], p["days_since_last"], p["days_old"]
            ), tags=(tag,))
        tree.tree.tag_configure("critical", foreground=COLORS["red"])
        tree.tree.tag_configure("warn", foreground=COLORS["yellow"])

        # Feature importance chart - فقط وقتی مدل واقعی آموزش دیده (clf موجوده)
        if MATPLOTLIB_OK and clf is not None:
            fig, ax = plt.subplots(figsize=(4.5, 2.2), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax.set_facecolor(COLORS["bg_card"])

            feat_names = [fa(n) for n in ["عمر تجهیز", "تعداد EM", "توقف(h)", "فاصله از EM", "نرخ PM"]]
            importances = clf.feature_importances_
            colors = [COLORS["red"] if i == np.argmax(importances) else COLORS["accent"] for i in range(len(importances))]

            ax.barh(feat_names, importances, color=colors, edgecolor=COLORS["bg_card"])
            ax.set_xlabel(fa("اهمیت"), color=COLORS["text_secondary"], fontsize=8)
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=7)
            for spine in ["top", "right"]: 
                ax.spines[spine].set_visible(False)
            for spine in ["bottom", "left"]: 
                ax.spines[spine].set_color(COLORS["border"])
            _apply_fa_font(ax)
            self._embed_chart(card, fig)

        IconButton(card, "خروجی CSV پیش‌بینی", "📄",
                   lambda: self._export_csv("prediction", predictions),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  🎯 2. EQUIPMENT RISK CLUSTERING
    # ═══════════════════════════════════════════════════════════════════════
    def _equipment_risk_card(self, all_wo, eq_rows):
        card = self._analysis_card("🎯  خوشه‌بندی ریسک تجهیزات",
                                   "دسته‌بندی تجهیزات با K-Means: پرخطر / متوسط / کم‌خطر")

        today = date.today()
        data = []
        for eq in eq_rows:
            eq_id = eq["id"]
            em_wo = [w for w in all_wo if w["equipment_id"] == eq_id and w["order_type"] == "EM"]
            pm_wo = [w for w in all_wo if w["equipment_id"] == eq_id and w["order_type"] == "PM"]

            down = sum(w["downtime_minutes"] or 0 for w in em_wo)
            em_count = len(em_wo)
            pm_count = len(pm_wo)

            data.append([em_count, down / 60, pm_count])

        if len(data) < 3:
            tk.Label(card, text="داده کافی نیست", font=FONTS["body"],
                     bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=10)
            return

        X = np.array(data)
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10).fit(X)
        labels = kmeans.labels_

        cluster_names = {0: "🟢 کم‌خطر", 1: "🟡 متوسط", 2: "🔴 پرخطر"}
        # Sort clusters by risk (highest EM+down first)
        cluster_means = {i: np.mean(X[labels == i], axis=0) for i in range(3)}
        sorted_clusters = sorted(cluster_means.items(), key=lambda x: x[1][0] + x[1][1], reverse=True)
        risk_map = {sorted_clusters[0][0]: "🔴 پرخطر",
                    sorted_clusters[1][0]: "🟡 متوسط",
                    sorted_clusters[2][0]: "🟢 کم‌خطر"}

        results = []
        for i, eq in enumerate(eq_rows):
            results.append({
                "name": eq["name"] or "نامشخص",
                "cluster": risk_map[labels[i]],
                "em_count": int(data[i][0]),
                "down_hours": round(data[i][1], 1),
                "pm_count": int(data[i][2])
            })

        tree = StyledTreeview(card, columns=("تجهیز", "دسته ریسک", "EM", "توقف(h)", "PM"))
        tree.pack(fill="x", padx=8, pady=8)
        for r in results:
            tag = "critical" if "🔴" in r["cluster"] else ("warn" if "🟡" in r["cluster"] else "ok")
            tree.insert((r["name"], r["cluster"], r["em_count"], r["down_hours"], r["pm_count"]), tags=(tag,))
        tree.tree.tag_configure("critical", foreground=COLORS["red"])

        IconButton(card, "خروجی CSV ریسک", "📄",
                   lambda: self._export_csv("risk_clusters", results),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  📈 3. TIME SERIES FORECAST
    # ═══════════════════════════════════════════════════════════════════════
    def _forecast_card(self, all_wo, months):
        card = self._analysis_card("📈  پیش‌بینی ماه آینده",
                                   "تخمین تعداد EM و downtime ماه آینده با رگرسیون خطی")

        # Monthly aggregation
        monthly = defaultdict(lambda: {"em": 0,"pm":0,"down": 0})
        for r in all_wo:
            m = r["work_date"][:7] if r["work_date"] else ""
            if m:
                monthly[m]["em" if r["order_type"] == "EM" else "pm"] += 1
                monthly[m]["down"] += r["downtime_minutes"] or 0

        if len(monthly) < 3:
            tk.Label(card, text="حداقل ۳ ماه داده نیاز است", font=FONTS["body"],
                     bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=10)
            return

        sorted_months = sorted(monthly.keys())
        X = np.arange(len(sorted_months)).reshape(-1, 1)
        y_em = np.array([monthly[m]["em"] for m in sorted_months])
        y_down = np.array([monthly[m]["down"] for m in sorted_months])

        model_em = LinearRegression().fit(X, y_em)
        model_down = LinearRegression().fit(X, y_down)

        next_month_idx = len(sorted_months)
        pred_em = max(0, round(model_em.predict([[next_month_idx]])[0], 1))
        pred_down = max(0, round(model_down.predict([[next_month_idx]])[0], 1))

        # Display predictions
        pred_frame = tk.Frame(card, bg=COLORS["bg_card"])
        pred_frame.pack(fill="x", padx=12, pady=8)
        for val, lbl, color in [
            (pred_em, "EM پیش‌بینی‌شده ماه آینده", COLORS["red"]),
            (round(pred_down/60, 1), "توقف پیش‌بینی‌شده (ساعت)", COLORS["yellow"])
        ]:
            sf = tk.Frame(pred_frame, bg=COLORS["bg_input"], padx=20, pady=10)
            sf.pack(side="right", fill="x", expand=True, padx=6)
            tk.Label(sf, text=str(val), font=FONTS["heading"],
                     bg=COLORS["bg_input"], fg=color).pack()
            tk.Label(sf, text=lbl, font=FONTS["small"],
                     bg=COLORS["bg_input"], fg=COLORS["text_muted"]).pack()

        # Chart
        if MATPLOTLIB_OK:
            fig, ax = plt.subplots(figsize=(5, 2.2), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax.set_facecolor(COLORS["bg_card"])

            x_labels = [fa(m) for m in sorted_months] + [fa("پیش‌بینی")]
            em_vals = list(y_em) + [pred_em]
            down_vals = list(y_down/60) + [pred_down/60]

            ax.plot(x_labels[:-1], y_em, color=COLORS["red"], marker="o", label=fa("EM واقعی"))
            ax.plot(x_labels, em_vals, color=COLORS["red"], linestyle="--", alpha=0.7, marker="x")
            ax.axvline(x=len(sorted_months)-0.5, color=COLORS["text_muted"], linestyle=":", alpha=0.5)

            ax.set_ylabel(fa("تعداد EM"), color=COLORS["text_secondary"], fontsize=8)
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=7)
            ax.legend(fontsize=7, facecolor=COLORS["bg_card"], edgecolor=COLORS["border"],
                     labelcolor=COLORS["text_primary"])
            for side in ["top", "right"]:
                ax.spines[side].set_visible(False)
            for side in ["bottom", "left"]:
                ax.spines[side].set_color(COLORS["border"])
            fig.tight_layout()
            _apply_fa_font(ax)
            self._embed_chart(card, fig)

    def _ml_warning_card(self):
        card = self._analysis_card("⚠️  هوش مصنوعی غیرفعال",
                                   "کتابخانه‌های ML شناسایی نشدند")
        detail = _ML_ERROR or "نامشخص"
        tk.Label(card, text="برای فعال‌سازی: pip install scikit-learn pandas numpy",
                 font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["yellow"]).pack(pady=(12, 4))
        tk.Label(card, text=f"خطای شناسایی‌شده: {detail}",
                 font=FONTS["small"], bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                 wraplength=600, justify="center").pack(pady=(0, 12))
    # ═══════════════════════════════════════════════════════════════════════
    #  📊 4. PARETO ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════
    def _pareto_card(self, rows):
        card = self._analysis_card("📊  تحلیل پارتو (قانون ۸۰/۲۰)",
                                   "تجهیزاتی که ۸۰٪ توقفات را ایجاد می‌کنند")

        eq_down = defaultdict(int)
        eq_em = defaultdict(int)
        for r in rows:
            if r["order_type"] == "EM" and r["downtime_minutes"]:
                eq_down[r["eq_name"] or "نامشخص"] += r["downtime_minutes"]
                eq_em[r["eq_name"] or "نامشخص"] += 1

        if not eq_down:
            tk.Label(card, text="داده EM کافی برای تحلیل پارتو وجود ندارد",
                     font=FONTS["body"], bg=COLORS["bg_card"],
                     fg=COLORS["text_muted"]).pack(pady=20)
            return

        sorted_eq = sorted(eq_down.items(), key=lambda x: x[1], reverse=True)
        total = sum(v for _, v in sorted_eq)
        cumsum = 0
        pareto_data = []
        for name, down in sorted_eq[:10]:
            cumsum += down
            pareto_data.append({
                "name": name, "down_minutes": down,
                "down_hours": round(down/60, 1),
                "pct": round(down/total*100, 1),
                "cum_pct": round(cumsum/total*100, 1),
                "em_count": eq_em[name]
            })

        if MATPLOTLIB_OK:
            fig, ax1 = plt.subplots(figsize=(5.5, 2.4), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax1.set_facecolor(COLORS["bg_card"])

            names = [fa(d["name"][:12]) for d in pareto_data]
            downs = [d["down_hours"] for d in pareto_data]
            cum_pcts = [d["cum_pct"] for d in pareto_data]

            ax1.bar(names, downs, color=COLORS["red"], edgecolor=COLORS["bg_card"], linewidth=1.5)
            ax1.set_ylabel(fa("توقف (ساعت)"), color=COLORS["text_secondary"], fontsize=8)
            ax1.tick_params(axis="y", colors=COLORS["text_secondary"], labelsize=7)
            ax1.tick_params(axis="x", colors=COLORS["text_primary"], labelsize=7, rotation=30)

            ax2 = ax1.twinx()
            ax2.plot(names, cum_pcts, color=COLORS["yellow"], marker="o", linewidth=2, markersize=5)
            ax2.axhline(y=80, color=COLORS["green"], linestyle="--", alpha=0.7)
            ax2.set_ylabel(fa("درصد تجمعی"), color=COLORS["text_secondary"], fontsize=8)
            ax2.tick_params(axis="y", colors=COLORS["text_secondary"], labelsize=7)
            ax2.set_ylim(0, 105)

            ax1.spines["top"].set_visible(False)
            for side in ["bottom", "left", "right"]:
                ax1.spines[side].set_color(COLORS["border"])

            fig.tight_layout()
            _apply_fa_font(ax1)
            _apply_fa_font(ax2)
            self._embed_chart(card, fig)

        tree = StyledTreeview(card, columns=("رتبه", "تجهیز", "توقف(ساعت)", "تعداد EM", "سهم", "تجمعی"))
        tree.pack(fill="x", padx=8, pady=8)
        for i, d in enumerate(pareto_data, 1):
            tag = "critical" if d["cum_pct"] <= 80 else "normal"
            tree.insert((i, d["name"], d["down_hours"], d["em_count"],
                        str(d["pct"]) + "%", str(d["cum_pct"]) + "%"), tags=(tag,))
        tree.tree.tag_configure("critical", foreground=COLORS["red"])

        IconButton(card, "خروجی CSV پارتو", "📄",
                   lambda: self._export_csv("pareto", pareto_data),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  📈 5. MONTHLY TREND
    # ═══════════════════════════════════════════════════════════════════════
    def _trend_card(self, rows, months):
        card = self._analysis_card("📈  روند ماهانه توقفات",
                                   "مقایسه توقفات اضطراری در ماه‌های اخیر")

        monthly = defaultdict(lambda: {"em": 0, "pm": 0, "down": 0})
        for r in rows:
            m = r["work_date"][:7] if r["work_date"] else ""
            if m:
                key = "em" if r["order_type"] == "EM" else "pm"
                monthly[m][key] += 1
                if r["downtime_minutes"]:
                    monthly[m]["down"] += r["downtime_minutes"]

        if not monthly:
            tk.Label(card, text="داده کافی وجود ندارد", font=FONTS["body"],
                     bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=20)
            return

        sorted_months = sorted(monthly.keys())
        trend_data = []
        for m in sorted_months:
            trend_data.append({
                "month": m, "em": monthly[m]["em"],
                "pm": monthly[m]["pm"], "down": monthly[m]["down"]
            })

        if MATPLOTLIB_OK:
            fig, ax = plt.subplots(figsize=(5.5, 2.2), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax.set_facecolor(COLORS["bg_card"])

            x = [fa(d["month"]) for d in trend_data]
            em_vals = [d["em"] for d in trend_data]
            pm_vals = [d["pm"] for d in trend_data]

            ax.plot(x, em_vals, color=COLORS["red"], marker="o", linewidth=2, label="EM")
            ax.plot(x, pm_vals, color=COLORS["blue"], marker="s", linewidth=2, label="PM")
            ax.fill_between(x, em_vals, alpha=0.15, color=COLORS["red"])

            ax.set_ylabel(fa("تعداد"), color=COLORS["text_secondary"], fontsize=8)
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=7)
            ax.legend(facecolor=COLORS["bg_card"], edgecolor=COLORS["border"],
                     labelcolor=COLORS["text_primary"], fontsize=8)
            for side in ["top", "right"]:
                ax.spines[side].set_visible(False)
            for side in ["bottom", "left"]:
                ax.spines[side].set_color(COLORS["border"])
            fig.tight_layout()
            _apply_fa_font(ax)
            self._embed_chart(card, fig)

        tree = StyledTreeview(card, columns=("ماه", "EM", "PM", "توقف(ساعت)"))
        tree.pack(fill="x", padx=8, pady=8)
        for d in trend_data:
            tree.insert((d["month"], d["em"], d["pm"], round(d["down"]/60, 1)))

        IconButton(card, "خروجی CSV روند", "📄",
                   lambda: self._export_csv("trend", trend_data),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  👷 6. OPERATOR PERFORMANCE
    # ═══════════════════════════════════════════════════════════════════════
    def _operator_card(self, rows):
        card = self._analysis_card("👷  تحلیل عملکرد اپراتورها",
                                   "کارایی، توقف و زمان تعمیر به تفکیک اپراتور")

        op_data = defaultdict(lambda: {"total": 0, "em": 0, "down": 0, "closed": 0})
        for r in rows:
            op = r["operator"] or "نامشخص"
            op_data[op]["total"] += 1
            if r["order_type"] == "EM": op_data[op]["em"] += 1
            if r["downtime_minutes"]: op_data[op]["down"] += r["downtime_minutes"]
            if r["status"] == "بسته": op_data[op]["closed"] += 1

        analysis = []
        for op, d in op_data.items():
            analysis.append({
                "operator": op, "total": d["total"], "em": d["em"],
                "down": d["down"], "closed": d["closed"],
                "completion": round(d["closed"]/d["total"]*100, 1) if d["total"] else 0,
                "avg_down": round(d["down"]/max(d["em"],1), 1)
            })

        if MATPLOTLIB_OK:
            fig, ax = plt.subplots(figsize=(4, 2.2), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax.set_facecolor(COLORS["bg_card"])

            ops_raw = [d["operator"] for d in analysis]
            comps = [d["completion"] for d in analysis]
            colors = [OPERATOR_COLORS.get(o, COLORS["accent"]) for o in ops_raw]
            ops = [fa(o) for o in ops_raw]

            bars = ax.barh(ops, comps, color=colors, edgecolor=COLORS["bg_card"], height=0.5)
            for bar, val in zip(bars, comps):
                ax.text(val + 2, bar.get_y() + bar.get_height()/2,
                       f"{val:.0f}%", va="center", color=COLORS["text_primary"], fontsize=8)

            ax.set_xlim(0, 110)
            ax.set_xlabel(fa("درصد تکمیل"), color=COLORS["text_secondary"], fontsize=8)
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=7)
            for side in ["top", "right"]:
                ax.spines[side].set_visible(False)
            for side in ["bottom", "left"]:
                ax.spines[side].set_color(COLORS["border"])
            fig.tight_layout()
            _apply_fa_font(ax)
            self._embed_chart(card, fig)

        tree = StyledTreeview(card, columns=("اپراتور", "کل", "EM", "تکمیل", "توقف(ساعت)", "میانگین(دق)"))
        tree.pack(fill="x", padx=8, pady=8)
        for d in analysis:
            tag = "op_" + d["operator"]
            tree.insert((d["operator"], d["total"], d["em"],
                        str(d["completion"]) + "%", round(d["down"]/60, 1),
                        d["avg_down"]), tags=(tag,))

        IconButton(card, "خروجی CSV اپراتور", "📄",
                   lambda: self._export_csv("operators", analysis),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  🔍 7. FAILURE ROOT CAUSE
    # ═══════════════════════════════════════════════════════════════════════
    def _failure_card(self, rows):
        card = self._analysis_card("🔍  تحلیل علت خرابی",
                                   "علل ریشه‌ای و تکرارشونده توقفات")

        causes = Counter()
        cause_down = defaultdict(int)
        for r in rows:
            if r["order_type"] == "EM":
                cause = r["root_cause"] or "نامشخص"
                causes[cause] += 1
                cause_down[cause] += r["downtime_minutes"] or 0

        if not causes:
            tk.Label(card, text="داده EM با علت خرابی ثبت نشده",
                     font=FONTS["body"], bg=COLORS["bg_card"],
                     fg=COLORS["text_muted"]).pack(pady=20)
            return

        cause_data = []
        total_em = sum(causes.values())
        for cause, count in causes.most_common(8):
            cause_data.append({
                "cause": cause, "count": count,
                "down": cause_down[cause],
                "pct": round(count/total_em*100, 1)
            })

        if MATPLOTLIB_OK and len(cause_data) >= 2:
            fig, ax = plt.subplots(figsize=(4, 2.2), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax.set_facecolor(COLORS["bg_card"])

            labels = [fa(d["cause"][:10]) for d in cause_data]
            sizes = [d["count"] for d in cause_data]
            colors_pie = plt.cm.Reds([0.4 + i*0.07 for i in range(len(sizes))])

            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct="%1.0f%%", colors=colors_pie,
                textprops={"color": COLORS["text_primary"], "fontsize": 7},
                wedgeprops={"edgecolor": COLORS["bg_card"], "linewidth": 2}
            )
            for at in autotexts:
                at.set_color("white")
                at.set_fontweight("bold")
                at.set_fontsize(6)
            fig.tight_layout()
            _apply_fa_font(ax)
            self._embed_chart(card, fig)

        tree = StyledTreeview(card, columns=("علت", "تعداد", "سهم", "توقف(ساعت)"))
        tree.pack(fill="x", padx=8, pady=8)
        for d in cause_data:
            tree.insert((d["cause"], d["count"], str(d["pct"]) + "%", round(d["down"]/60, 1)))

        IconButton(card, "خروجی CSV علل خرابی", "📄",
                   lambda: self._export_csv("causes", cause_data),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  ⚙️ 8. PM/EM RATIO & OEE
    # ═══════════════════════════════════════════════════════════════════════
    def _pm_em_ratio_card(self, rows, months):
        card = self._analysis_card("⚙️  نسبت PM/EM و شاخص‌های کلیدی",
                                   "ارزیابی اثربخشی نگهداری پیشگیرانه")

        total_em = sum(1 for r in rows if r["order_type"] == "EM")
        total_pm = sum(1 for r in rows if r["order_type"] == "PM")
        total_down = sum(r["downtime_minutes"] or 0 for r in rows if r["order_type"] == "EM")
        closed = sum(1 for r in rows if r["status"] == "بسته")

        working_hours = 16 * 30 * months
        availability = max(0, (working_hours*60 - total_down) / (working_hours*60)) * 100

        kpi_data = [
            {"indicator": "تعداد EM", "value": total_em, "unit": "عدد", "target": "< 5", "status": "bad" if total_em > 5 else "good"},
            {"indicator": "تعداد PM", "value": total_pm, "unit": "عدد", "target": "> 10", "status": "good" if total_pm > 10 else "warn"},
            {"indicator": "نسبت PM/EM", "value": round(total_pm/max(total_em,1), 2), "unit": "", "target": "> 2.0", "status": "good" if total_pm > 2*total_em else "warn"},
            {"indicator": "مجموع توقف", "value": round(total_down/60, 1), "unit": "ساعت", "target": "< 20", "status": "bad" if total_down > 1200 else "good"},
            {"indicator": "دستور کار بسته", "value": closed, "unit": "عدد", "target": "100%", "status": "good"},
            {"indicator": "OEE تخمینی", "value": round(availability, 1), "unit": "%", "target": "> 85%", "status": "good" if availability > 85 else "warn" if availability > 70 else "bad"},
        ]

        if MATPLOTLIB_OK:
            fig, ax = plt.subplots(figsize=(3, 1.8), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax.set_facecolor(COLORS["bg_card"])
            cats = ["EM", "PM"]
            vals = [total_em, total_pm]
            bar_colors = [COLORS["red"], COLORS["blue"]]
            bars = ax.bar(cats, vals, color=bar_colors, edgecolor=COLORS["bg_card"], width=0.5)
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                       str(val), ha="center", color=COLORS["text_primary"], fontsize=10, fontweight="bold")
            ax.set_ylabel(fa("تعداد"), color=COLORS["text_secondary"], fontsize=8)
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=8)
            for side in ["top", "right"]:
                ax.spines[side].set_visible(False)
            for side in ["bottom", "left"]:
                ax.spines[side].set_color(COLORS["border"])
            fig.tight_layout()
            _apply_fa_font(ax)
            self._embed_chart(card, fig)

        for d in kpi_data:
            row = tk.Frame(card, bg=COLORS["bg_card"])
            row.pack(fill="x", padx=12, pady=3)
            status_color = {"good": COLORS["green"], "warn": COLORS["yellow"], "bad": COLORS["red"]}.get(d["status"], COLORS["text_muted"])
            tk.Label(row, text="●", font=FONTS["small"], bg=COLORS["bg_card"], fg=status_color).pack(side="right")
            tk.Label(row, text=d["indicator"], font=FONTS["body_bold"], bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(side="right", padx=6)
            tk.Label(row, text=str(d["value"]) + " " + d["unit"], font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="right", padx=12)
            tk.Label(row, text="هدف: " + d["target"], font=FONTS["small"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(side="left")

        IconButton(card, "خروجی CSV شاخص‌ها", "📄",
                   lambda: self._export_csv("kpis", kpi_data),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=8)

    # ═══════════════════════════════════════════════════════════════════════
    #  📋 9. STATS TABLE
    # ═══════════════════════════════════════════════════════════════════════
    def _stats_table_card(self, wo_rows, eq_rows, cat_rows):
        card = self._analysis_card("📋  خلاصه آماری داده‌ها",
                                   "آمار کلی سیستم در بازه زمانی انتخاب‌شده")

        total_wo = len(wo_rows)
        em_rows = [r for r in wo_rows if r["order_type"] == "EM"]
        pm_rows = [r for r in wo_rows if r["order_type"] == "PM"]
        avg_down = sum(r["downtime_minutes"] or 0 for r in em_rows) / max(len(em_rows), 1)

        stats = [
            ("کل دستور کارها", total_wo),
            ("توقفات اضطراری (EM)", len(em_rows)),
            ("نگهداری پیشگیرانه (PM)", len(pm_rows)),
            ("تجهیزات فعال", len([e for e in eq_rows if e["status"] == "فعال"])),
            ("تجهیزات در تعمیر", len([e for e in eq_rows if e["status"] == "در تعمیر"])),
            ("دسته‌بندی تجهیزات", len(cat_rows)),
            ("میانگین توقف EM", str(int(avg_down)) + " دقیقه"),
            ("بیشترین توقف", str(max((r["downtime_minutes"] or 0) for r in wo_rows)) + " دقیقه" if wo_rows else "0"),
        ]

        grid = tk.Frame(card, bg=COLORS["bg_card"])
        grid.pack(fill="x", padx=12, pady=8)
        for i, (lbl, val) in enumerate(stats):
            bg_c = COLORS["bg_input"] if i % 2 == 0 else COLORS["bg_card"]
            row = tk.Frame(grid, bg=bg_c)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=str(val), font=FONTS["body_bold"],
                     bg=bg_c, fg=COLORS["accent"], padx=12, pady=5).pack(side="left")
            tk.Label(row, text=lbl, font=FONTS["body"],
                     bg=bg_c, fg=COLORS["text_secondary"], padx=12, pady=5).pack(side="right")

    # ═══════════════════════════════════════════════════════════════════════
    #  💡 10. SMART INSIGHTS — auto-generated Persian narrative summary
    # ═══════════════════════════════════════════════════════════════════════
    def _smart_insights_card(self, rows, eq_rows, months):
        card = self._analysis_card("💡  خلاصه هوشمند",
                                   "نکات کلیدی این بازه به‌صورت خودکار استخراج شده")

        em_rows = [r for r in rows if r["order_type"] == "EM"]
        pm_rows_ = [r for r in rows if r["order_type"] == "PM"]

        insights = []

        if not rows:
            tk.Label(card, text="داده‌ای برای این بازه یافت نشد",
                     font=FONTS["body"], bg=COLORS["bg_card"],
                     fg=COLORS["text_muted"]).pack(pady=16)
            return

        # 1) EM vs PM balance
        ratio = len(pm_rows_) / max(len(em_rows), 1)
        if ratio < 1:
            insights.append(("⚠️", rtl(f"تعداد توقفات اضطراری ({len(em_rows)}) از نگهداری پیشگیرانه ({len(pm_rows_)}) بیشتر است — نشانه‌ی نگهداری واکنشی به‌جای پیشگیرانه."), COLORS["red"]))
        elif ratio > 3:
            insights.append(("✅", rtl(f"نسبت PM به EM عالی است ({round(ratio,1)} به ۱) — برنامه نگهداری پیشگیرانه به‌خوبی اجرا می‌شود."), COLORS["green"]))

        # 2) Worst equipment by downtime
        eq_down = defaultdict(int)
        for r in em_rows:
            eq_down[r["eq_name"] or "نامشخص"] += r["downtime_minutes"] or 0
        if eq_down:
            worst_name, worst_down = max(eq_down.items(), key=lambda x: x[1])
            share = worst_down / max(sum(eq_down.values()), 1) * 100
            insights.append(("🔴", rtl(f"«{worst_name}» به‌تنهایی {round(share,1)}٪ از کل توقفات اضطراری این بازه را ایجاد کرده ({round(worst_down/60,1)} ساعت) — اولویت اول برای بازرسی."), COLORS["red"]))

        # 3) Trend direction (first half vs second half of the window)
        sorted_rows = sorted(em_rows, key=lambda r: r["work_date"] or "")
        if len(sorted_rows) >= 6:
            half = len(sorted_rows) // 2
            first_half, second_half = sorted_rows[:half], sorted_rows[half:]
            if len(second_half) > len(first_half) * 1.3:
                insights.append(("📈", rtl("روند توقفات اضطراری در نیمه دوم این بازه نسبت به نیمه اول رو به افزایش بوده است."), COLORS["yellow"]))
            elif len(first_half) > len(second_half) * 1.3:
                insights.append(("📉", rtl("روند توقفات اضطراری در نیمه دوم این بازه نسبت به نیمه اول کاهش یافته — روند مثبت."), COLORS["green"]))

        # 4) Idle equipment (no work orders at all in this window)
        active_eq_ids = {r["equipment_id"] for r in rows if r["equipment_id"]}
        idle = [e for e in eq_rows if e["id"] not in active_eq_ids and (e["status"] or "") == "فعال"]
        if idle:
            insights.append(("ℹ️", rtl(f"{len(idle)} تجهیز فعال در این بازه هیچ دستور کاری نداشته‌اند — یا بدون خرابی بوده‌اند یا ثبت داده انجام نشده."), COLORS["blue"]))

        # 5) Top recurring root cause
        causes = Counter(r["root_cause"] for r in em_rows if r["root_cause"])
        if causes:
            top_cause, top_n = causes.most_common(1)[0]
            if top_n >= 3:
                insights.append(("🔁", rtl(f"علت «{top_cause}» {top_n} بار تکرار شده — بررسی ریشه‌ای این علت می‌تواند بیشترین اثر را در کاهش توقفات داشته باشد."), COLORS["yellow"]))

        # 6) Downtime per day average
        total_down_h = sum(r["downtime_minutes"] or 0 for r in em_rows) / 60
        days_span = max(months * 30, 1)
        insights.append(("📊", rtl(f"میانگین توقف روزانه در این بازه {round(total_down_h/days_span, 2)} ساعت است (مجموع {round(total_down_h,1)} ساعت طی {months} ماه)."), COLORS["text_secondary"]))

        if not insights:
            insights.append(("✅", rtl("نکته هشداردهنده‌ای در این بازه شناسایی نشد."), COLORS["green"]))

        for icon, text, color in insights:
            row = tk.Frame(card, bg=COLORS["bg_card"])
            row.pack(fill="x", padx=12, pady=4)
            tk.Label(row, text=icon, font=FONTS["body"], bg=COLORS["bg_card"]).pack(side="right", padx=(4, 8))
            lbl = tk.Label(row, text=text, font=FONTS["body"], bg=COLORS["bg_card"],
                           fg=color, justify="right", anchor="e")
            lbl.pack(side="right", fill="x", expand=True)
            # Responsive wraplength: fixed pixel wraplength only looks right
            # at one particular window size. Recompute it whenever the row
            # is resized so text wraps correctly whether the window/panel
            # is maximized or small.
            def _rewrap(event, lbl=lbl):
                lbl.config(wraplength=max(event.width - 20, 150))
            row.bind("<Configure>", _rewrap)

    # ═══════════════════════════════════════════════════════════════════════
    #  🚨 11. ANOMALY DETECTION — Isolation Forest
    # ═══════════════════════════════════════════════════════════════════════
    def _anomaly_detection_card(self, all_wo, eq_rows):
        card = self._analysis_card("🚨  تشخیص ناهنجاری تجهیزات",
                                   "تجهیزاتی که رفتارشان نسبت به بقیه غیرعادی است — مدل Isolation Forest")

        today = date.today()
        feats, meta = [], []
        for eq in eq_rows:
            eq_id = eq["id"]
            eq_wo = [w for w in all_wo if w["equipment_id"] == eq_id]
            em_wo = [w for w in eq_wo if w["order_type"] == "EM"]
            if not eq_wo:
                continue

            em_count = len(em_wo)
            total_down = sum(w["downtime_minutes"] or 0 for w in em_wo)
            avg_down = total_down / max(em_count, 1)
            durations = []
            dates_sorted = sorted(datetime.strptime(w["work_date"], "%Y-%m-%d").date() for w in em_wo) if em_wo else []
            for i in range(1, len(dates_sorted)):
                durations.append((dates_sorted[i] - dates_sorted[i-1]).days)
            avg_gap = (sum(durations) / len(durations)) if durations else 999

            feats.append([em_count, total_down, avg_down, avg_gap])
            meta.append({"name": eq["name"] or "نامشخص", "code": eq["code"] or "-",
                         "em_count": em_count, "down_h": round(total_down/60, 1),
                         "avg_down": round(avg_down, 1), "avg_gap": round(avg_gap, 1)})

        if len(feats) < 6:
            tk.Label(card, text="داده کافی برای تشخیص ناهنجاری وجود ندارد (حداقل ۶ تجهیز با سابقه)",
                     font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=16)
            return

        X = np.array(feats)
        iso = IsolationForest(contamination=0.15, random_state=42, n_estimators=150)
        preds = iso.fit_predict(X)          # -1 = anomaly, 1 = normal
        scores = -iso.score_samples(X)      # higher = more anomalous

        for i, m in enumerate(meta):
            m["anomaly"] = preds[i] == -1
            m["anomaly_score"] = round(float(scores[i]), 3)

        anomalies = sorted([m for m in meta if m["anomaly"]], key=lambda x: x["anomaly_score"], reverse=True)

        if not anomalies:
            tk.Label(card, text="ناهنجاری خاصی در رفتار تجهیزات شناسایی نشد ✓",
                     font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["green"]).pack(pady=16)
            return

        tree = StyledTreeview(card, columns=("تجهیز", "کد", "امتیاز ناهنجاری", "تعداد EM", "توقف کل(h)", "میانگین توقف(دق)", "فاصله میانگین(روز)"))
        tree.pack(fill="x", padx=8, pady=8)
        for m in anomalies:
            tree.insert((m["name"], m["code"], m["anomaly_score"], m["em_count"],
                        m["down_h"], m["avg_down"], m["avg_gap"]), tags=("critical",))
        tree.tree.tag_configure("critical", foreground=COLORS["red"])

        tk.Label(card, text=f"{len(anomalies)} تجهیز از {len(meta)} با الگوی رفتاری غیرعادی نسبت به سایرین شناسایی شد.",
                 font=FONTS["small"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(anchor="e", padx=12, pady=(0, 8))

        IconButton(card, "خروجی CSV ناهنجاری", "📄",
                   lambda: self._export_csv("anomalies", anomalies),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  🔧 12. TECHNICIAN PERFORMANCE
    # ═══════════════════════════════════════════════════════════════════════
    def _technician_card(self, rows):
        card = self._analysis_card("🔧  عملکرد تکنسین‌ها",
                                   "کارایی و بار کاری به تفکیک تکنسین انجام‌دهنده تعمیر")

        tech_data = defaultdict(lambda: {"total": 0, "em": 0, "pm": 0, "down": 0, "closed": 0})
        has_tech = False
        for r in rows:
            tech = None
            try:
                tech = r["technician_name"]
            except Exception:
                tech = None
            if not tech:
                continue
            has_tech = True
            tech_data[tech]["total"] += 1
            if r["order_type"] == "EM": tech_data[tech]["em"] += 1
            if r["order_type"] == "PM": tech_data[tech]["pm"] += 1
            if r["downtime_minutes"]: tech_data[tech]["down"] += r["downtime_minutes"]
            if r["status"] == "بسته": tech_data[tech]["closed"] += 1

        if not has_tech or not tech_data:
            tk.Label(card, text="داده تکنسین ثبت نشده است",
                     font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=16)
            return

        analysis = []
        for tech, d in tech_data.items():
            analysis.append({
                "technician": tech, "total": d["total"], "em": d["em"], "pm": d["pm"],
                "down_h": round(d["down"]/60, 1), "closed": d["closed"],
                "completion": round(d["closed"]/d["total"]*100, 1) if d["total"] else 0
            })
        analysis.sort(key=lambda x: x["total"], reverse=True)

        if MATPLOTLIB_OK and len(analysis) >= 2:
            fig, ax = plt.subplots(figsize=(4.5, 2.2), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax.set_facecolor(COLORS["bg_card"])

            names = [fa(d["technician"][:10]) for d in analysis]
            totals = [d["total"] for d in analysis]
            ax.bar(names, totals, color=COLORS["accent"], edgecolor=COLORS["bg_card"])
            ax.set_ylabel(fa("تعداد دستور کار"), color=COLORS["text_secondary"], fontsize=8)
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=7)
            for side in ["top", "right"]:
                ax.spines[side].set_visible(False)
            for side in ["bottom", "left"]:
                ax.spines[side].set_color(COLORS["border"])
            fig.tight_layout()
            _apply_fa_font(ax)
            self._embed_chart(card, fig)

        tree = StyledTreeview(card, columns=("تکنسین", "کل", "EM", "PM", "توقف(h)", "درصد تکمیل"))
        tree.pack(fill="x", padx=8, pady=8)
        for d in analysis:
            tree.insert((d["technician"], d["total"], d["em"], d["pm"],
                        d["down_h"], str(d["completion"]) + "%"))

        IconButton(card, "خروجی CSV تکنسین‌ها", "📄",
                   lambda: self._export_csv("technicians", analysis),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  🗂️ 13. CATEGORY ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════
    def _category_card(self, rows, eq_rows, cat_rows):
        card = self._analysis_card("🗂️  تحلیل بر اساس دسته‌بندی تجهیزات",
                                   "مقایسه توقفات و تعمیرات میان دسته‌های مختلف تجهیزات")

        try:
            cat_name = {c["id"]: (c["name"] or "نامشخص") for c in cat_rows}
        except Exception:
            tk.Label(card, text="اطلاعات دسته‌بندی در دسترس نیست",
                     font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=16)
            return

        try:
            eq_cat = {e["id"]: e["category_id"] for e in eq_rows}
        except Exception:
            tk.Label(card, text="اطلاعات دسته‌بندی تجهیزات در دسترس نیست",
                     font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=16)
            return

        cat_stats = defaultdict(lambda: {"em": 0, "pm": 0, "down": 0})
        for r in rows:
            cid = eq_cat.get(r["equipment_id"])
            name = cat_name.get(cid, "بدون دسته")
            if r["order_type"] == "EM":
                cat_stats[name]["em"] += 1
                cat_stats[name]["down"] += r["downtime_minutes"] or 0
            else:
                cat_stats[name]["pm"] += 1

        if not cat_stats:
            tk.Label(card, text="داده کافی برای این تحلیل وجود ندارد",
                     font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=16)
            return

        cat_list = sorted(cat_stats.items(), key=lambda x: x[1]["down"], reverse=True)

        if MATPLOTLIB_OK:
            fig, ax = plt.subplots(figsize=(5, 2.2), dpi=80)
            fig.patch.set_facecolor(COLORS["bg_card"])
            ax.set_facecolor(COLORS["bg_card"])

            names = [fa(n[:12]) for n, _ in cat_list]
            downs = [round(s["down"]/60, 1) for _, s in cat_list]
            ax.bar(names, downs, color=COLORS["blue"], edgecolor=COLORS["bg_card"])
            ax.set_ylabel(fa("توقف (ساعت)"), color=COLORS["text_secondary"], fontsize=8)
            ax.tick_params(colors=COLORS["text_secondary"], labelsize=7, rotation=20)
            for side in ["top", "right"]:
                ax.spines[side].set_visible(False)
            for side in ["bottom", "left"]:
                ax.spines[side].set_color(COLORS["border"])
            fig.tight_layout()
            _apply_fa_font(ax)
            self._embed_chart(card, fig)

        tree = StyledTreeview(card, columns=("دسته", "EM", "PM", "توقف(h)"))
        tree.pack(fill="x", padx=8, pady=8)
        cat_data = []
        for name, s in cat_list:
            row_d = {"category": name, "em": s["em"], "pm": s["pm"], "down_h": round(s["down"]/60, 1)}
            cat_data.append(row_d)
            tree.insert((name, s["em"], s["pm"], row_d["down_h"]))

        IconButton(card, "خروجی CSV دسته‌بندی", "📄",
                   lambda: self._export_csv("categories", cat_data),
                   color=COLORS["blue"]).pack(anchor="e", padx=8, pady=4)

    # ═══════════════════════════════════════════════════════════════════════
    #  💰 14. DOWNTIME COST ESTIMATION
    # ═══════════════════════════════════════════════════════════════════════
    def _cost_card(self, rows):
        card = self._analysis_card("💰  برآورد هزینه توقفات",
                                   "هزینه تخمینی توقف بر اساس نرخ ساعتی قابل‌تنظیم")

        em_rows = [r for r in rows if r["order_type"] == "EM"]
        if not em_rows:
            tk.Label(card, text="داده EM برای برآورد هزینه وجود ندارد",
                     font=FONTS["body"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=16)
            return

        rate_var = tk.StringVar(value="500000")  # تومان بر ساعت — قابل تغییر توسط کاربر

        ctrl = tk.Frame(card, bg=COLORS["bg_card"])
        ctrl.pack(fill="x", padx=12, pady=(8, 4))
        tk.Label(ctrl, text="نرخ هزینه توقف (تومان/ساعت):", font=FONTS["body"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="right", padx=4)
        rate_entry = tk.Entry(ctrl, textvariable=rate_var, width=12, font=FONTS["body"])
        rate_entry.pack(side="right", padx=4)

        result_frame = tk.Frame(card, bg=COLORS["bg_card"])
        result_frame.pack(fill="x", padx=12, pady=8)

        def render_cost(*_):
            for w in result_frame.winfo_children():
                w.destroy()
            try:
                rate = float(rate_var.get())
            except ValueError:
                rate = 0

            eq_down = defaultdict(int)
            for r in em_rows:
                eq_down[r["eq_name"] or "نامشخص"] += r["downtime_minutes"] or 0

            total_hours = sum(eq_down.values()) / 60
            total_cost = total_hours * rate

            tk.Label(result_frame, text=f"{int(total_cost):,} تومان", font=FONTS["heading"],
                     bg=COLORS["bg_card"], fg=COLORS["red"]).pack()
            tk.Label(result_frame, text=f"برآورد هزینه کل توقفات ({round(total_hours,1)} ساعت)",
                     font=FONTS["small"], bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(pady=(0, 8))

            top5 = sorted(eq_down.items(), key=lambda x: x[1], reverse=True)[:5]
            if MATPLOTLIB_OK and top5:
                fig, ax = plt.subplots(figsize=(5, 2), dpi=80)
                fig.patch.set_facecolor(COLORS["bg_card"])
                ax.set_facecolor(COLORS["bg_card"])
                names = [fa(n[:12]) for n, _ in top5]
                costs = [(mins/60)*rate for _, mins in top5]
                ax.barh(names, costs, color=COLORS["red"], edgecolor=COLORS["bg_card"])
                ax.set_xlabel(fa("هزینه تخمینی (تومان)"), color=COLORS["text_secondary"], fontsize=8)
                ax.tick_params(colors=COLORS["text_secondary"], labelsize=7)
                for side in ["top", "right"]:
                    ax.spines[side].set_visible(False)
                for side in ["bottom", "left"]:
                    ax.spines[side].set_color(COLORS["border"])
                fig.tight_layout()
                _apply_fa_font(ax)
                self._embed_chart(result_frame, fig)

        IconButton(ctrl, "محاسبه", "🔄", render_cost, color=COLORS["accent"]).pack(side="right", padx=4)
        render_cost()

    # ═══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════════════════
    def _analysis_card(self, title, subtitle):
        card = tk.Frame(self.content, bg=COLORS["bg_card"],
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="x", padx=20, pady=10)
        hdr = tk.Frame(card, bg=COLORS["bg_card"])
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        SectionTitle(hdr, title, icon="", accent=True).pack(side="right")
        tk.Label(hdr, text=subtitle, font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(side="left")
        tk.Frame(card, bg=COLORS["border"], height=1).pack(fill="x", padx=12, pady=(0, 4))
        return card

    def _embed_chart(self, parent, fig):
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(fill="x", padx=8, pady=4)
        self._charts.append(fig)
        self._chart_widgets.append(widget)

    def _export_csv(self, prefix, data):
        if not data:
            messagebox.showinfo("خروجی", "داده‌ای برای خروجی وجود ندارد")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="cmms_analysis_" + prefix + "_" + str(date.today().isoformat()) + ".csv"
        )
        if not path:
            return
        try:
            keys = list(data[0].keys())
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)
            from widgets import ToastNotification
            ToastNotification(self, "CSV ذخیره شد ✓", "success")
        except Exception as e:
            messagebox.showerror("خطا", str(e))

    def _export_full_csv(self):
        rows = db.fetch_all("""
            SELECT wo.order_number, wo.order_type, e.name as eq_name, e.code as eq_code,
                   e.location, wo.operator, wo.technician_name, wo.work_date,
                   wo.downtime_minutes, wo.priority, wo.status, wo.root_cause,
                   wo.action_taken, wo.parts_used, wo.description
            FROM work_orders wo
            LEFT JOIN equipment e ON wo.equipment_id=e.id
            ORDER BY wo.id DESC
        """)
        if not rows:
            messagebox.showinfo("خروجی", "داده‌ای برای خروجی وجود ندارد")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="cmms_full_export_" + str(date.today().isoformat()) + ".csv"
        )
        if not path:
            return
        try:
            keys = list(rows[0].keys())
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
            from widgets import ToastNotification
            ToastNotification(self, "خروجی CSV کامل ذخیره شد ✓", "success")
        except Exception as e:
            messagebox.showerror("خطا", str(e))

    def _export_full_excel(self):
        if not EXCEL_OK or not NP_PD_OK:
            messagebox.showwarning("خروجی Excel", "برای این قابلیت نصب کنید:\npip install pandas openpyxl")
            return

        wo_rows = db.fetch_all("""
            SELECT wo.order_number, wo.order_type, e.name as eq_name, e.code as eq_code,
                   e.location, wo.operator, wo.technician_name, wo.work_date,
                   wo.downtime_minutes, wo.priority, wo.status, wo.root_cause,
                   wo.action_taken, wo.parts_used, wo.description
            FROM work_orders wo
            LEFT JOIN equipment e ON wo.equipment_id=e.id
            ORDER BY wo.id DESC
        """)
        eq_rows = db.fetch_all("SELECT * FROM equipment")

        if not wo_rows:
            messagebox.showinfo("خروجی", "داده‌ای برای خروجی وجود ندارد")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="cmms_full_export_" + str(date.today().isoformat()) + ".xlsx"
        )
        if not path:
            return

        try:
            df_wo = pd.DataFrame([dict(r) for r in wo_rows])
            df_eq = pd.DataFrame([dict(r) for r in eq_rows]) if eq_rows else pd.DataFrame()

            em_df = df_wo[df_wo["order_type"] == "EM"] if not df_wo.empty else df_wo
            if not em_df.empty:
                summary = em_df.groupby("eq_name", dropna=False).agg(
                    تعداد_EM=("order_number", "count"),
                    مجموع_توقف_دقیقه=("downtime_minutes", "sum")
                ).reset_index().sort_values("مجموع_توقف_دقیقه", ascending=False)
            else:
                summary = pd.DataFrame()

            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df_wo.to_excel(writer, sheet_name="دستور کارها", index=False)
                if not df_eq.empty:
                    df_eq.to_excel(writer, sheet_name="تجهیزات", index=False)
                if not summary.empty:
                    summary.to_excel(writer, sheet_name="خلاصه توقفات", index=False)

                # Light header styling
                header_fill = PatternFill(start_color="F97316", end_color="F97316", fill_type="solid")
                for sheet in writer.sheets.values():
                    for cell in sheet[1]:
                        cell.font = Font(bold=True, color="FFFFFF")
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal="center")
                    for col in sheet.columns:
                        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
                        sheet.column_dimensions[col[0].column_letter].width = min(max_len + 3, 40)

            from widgets import ToastNotification
            ToastNotification(self, "خروجی Excel کامل ذخیره شد ✓", "success")
        except Exception as e:
            messagebox.showerror("خطا", str(e))
    
    def _print_report(self):
        months = int(self.months_var.get())
        start_date = (date.today() - timedelta(days=30*months)).isoformat()

        rows = db.fetch_all("""
            SELECT wo.*, e.name as eq_name FROM work_orders wo
            LEFT JOIN equipment e ON wo.equipment_id=e.id
            WHERE wo.work_date >= ?
        """, (start_date,))

        total_em = sum(1 for r in rows if r["order_type"] == "EM")
        total_pm = sum(1 for r in rows if r["order_type"] == "PM")
        total_down = sum(r["downtime_minutes"] or 0 for r in rows)
        avg_mttr = db.calc_mttr() if hasattr(db, 'calc_mttr') else 0
        avg_mtbf = db.calc_mtbf() if hasattr(db, 'calc_mtbf') else 0

        eq_down = defaultdict(int)
        for r in rows:
            if r["order_type"] == "EM" and r["downtime_minutes"]:
                eq_down[r["eq_name"] or "نامشخص"] += r["downtime_minutes"]
        top_eq = sorted(eq_down.items(), key=lambda x: x[1], reverse=True)[:5]

        op_stats = defaultdict(lambda: {"total": 0, "down": 0})
        for r in rows:
            op = r["operator"] or "نامشخص"
            op_stats[op]["total"] += 1
            op_stats[op]["down"] += r["downtime_minutes"] or 0

        today_str = date.today().isoformat()

        h = []
        h.append('<!DOCTYPE html>')
        h.append('<html dir="rtl" lang="fa">')
        h.append('<head><meta charset="UTF-8">')
        h.append('<title>گزارش تحلیلی CMMS — ' + today_str + '</title>')
        h.append('<style>')
        h.append('body{font-family:Tahoma,Arial;margin:40px;background:#fff;color:#111}')
        h.append('h1{color:#F97316;border-bottom:3px solid #F97316;padding-bottom:10px}')
        h.append('h2{color:#333;margin-top:30px}')
        h.append('table{width:100%;border-collapse:collapse;margin:15px 0}')
        h.append('th,td{border:1px solid #ddd;padding:10px;text-align:right}')
        h.append('th{background:#F97316;color:white}')
        h.append('tr:nth-child(even){background:#f9f9f9}')
        h.append('.kpi{display:inline-block;margin:10px;padding:15px 25px;background:#f5f5f5;border-radius:8px}')
        h.append('.kpi-val{font-size:24px;font-weight:bold;color:#F97316}')
        h.append('.footer{margin-top:40px;font-size:12px;color:#888;border-top:1px solid #ddd;padding-top:10px}')
        h.append('@media print{body{margin:20px}.no-print{display:none}}')
        h.append('</style></head><body>')

        h.append('<div class="no-print" style="text-align:left;margin-bottom:20px">')
        h.append('<button onclick="window.print()" style="padding:10px 20px;font-size:14px;cursor:pointer">🖨️ پرینت گزارش</button>')
        h.append('</div>')

        h.append('<h1>📊 گزارش تحلیلی سیستم نگهداری و تعمیرات (CMMS)</h1>')
        h.append('<p><strong>تاریخ گزارش:</strong> ' + today_str + ' | <strong>بازه:</strong> ' + str(months) + ' ماه گذشته</p>')

        h.append('<h2>شاخص‌های کلیدی (KPI)</h2><div>')
        h.append('<div class="kpi"><div class="kpi-val">' + str(total_em) + '</div><div>توقفات اضطراری</div></div>')
        h.append('<div class="kpi"><div class="kpi-val">' + str(total_pm) + '</div><div>دستور کار PM</div></div>')
        h.append('<div class="kpi"><div class="kpi-val">' + str(round(total_down/60, 1)) + '</div><div>مجموع توقف (ساعت)</div></div>')
        h.append('<div class="kpi"><div class="kpi-val">' + str(avg_mttr) + '</div><div>MTTR (ساعت)</div></div>')
        h.append('<div class="kpi"><div class="kpi-val">' + str(avg_mtbf) + '</div><div>MTBF (ساعت)</div></div>')
        h.append('</div>')

        h.append('<h2>🔴 تجهیزات با بیشترین توقف</h2>')
        h.append('<table><tr><th>رتبه</th><th>تجهیز</th><th>توقف (دقیقه)</th><th>توقف (ساعت)</th></tr>')
        for i, (name, down) in enumerate(top_eq, 1):
            h.append('<tr><td>' + str(i) + '</td><td>' + str(name) + '</td><td>' + str(down) + '</td><td>' + str(round(down/60, 1)) + '</td></tr>')
        h.append('</table>')

        h.append('<h2>👷 آمار اپراتورها</h2>')
        h.append('<table><tr><th>اپراتور</th><th>کل دستور کار</th><th>مجموع توقف (دقیقه)</th></tr>')
        for op, st in op_stats.items():
            h.append('<tr><td>' + str(op) + '</td><td>' + str(st["total"]) + '</td><td>' + str(st["down"]) + '</td></tr>')
        h.append('</table>')

        h.append('<div class="footer">تولید شده توسط سیستم CMMS | صفحه تحلیل داده‌ها</div>')
        h.append('</body></html>')

        html = '\n'.join(h)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8")
        tmp.write(html)
        tmp.close()
        webbrowser.open("file:///" + tmp.name.replace("\\", "/"))
        from widgets import ToastNotification
        ToastNotification(self, "گزارش HTML باز شد — Ctrl+P برای پرینت", "info")