"""
CMMS Widgets - Fixed version
- GaugeMeter: deferred safe draw (fixes 0.0 display + crash)
- StyledTreeview: cached styles (fixes style leak)
- ToastNotification: safe auto-close
- FormField: scroll canvas fix for NewWorkOrderPage
"""
import tkinter as tk
from tkinter import ttk
from styles import COLORS, FONTS, OPERATOR_COLORS, PRIORITY_COLORS, STATUS_COLORS

_STYLE_CACHE = {}   # کش استایل‌های Treeview — جلوگیری از نشت حافظه


class DarkFrame(tk.Frame):
    def __init__(self, parent, bg=None, **kwargs):
        super().__init__(parent, bg=bg or COLORS["bg_card"], **kwargs)


class SectionTitle(tk.Frame):
    def __init__(self, parent, text, icon="", accent=True, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        if accent:
            tk.Frame(self, bg=COLORS["accent"], width=4).pack(side="left", fill="y", padx=(0, 10))
        tk.Label(self, text=f"{icon}  {text}" if icon else text,
                 font=FONTS["heading"], bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"]).pack(side="left", pady=8)


class KPICard(tk.Frame):
    def __init__(self, parent, title, value, unit="", color=None, icon="", **kwargs):
        color = color or COLORS["accent"]
        super().__init__(parent, bg=COLORS["bg_card"],
                         highlightbackground=color, highlightthickness=1, **kwargs)
        tk.Frame(self, bg=color, height=3).pack(fill="x")
        inner = tk.Frame(self, bg=COLORS["bg_card"])
        inner.pack(fill="both", expand=True, padx=16, pady=12)
        head = tk.Frame(inner, bg=COLORS["bg_card"])
        head.pack(fill="x")
        tk.Label(head, text=icon, font=("Segoe UI Emoji", 18),
                 bg=COLORS["bg_card"], fg=color).pack(side="left")
        tk.Label(head, text=title, font=FONTS["kpi_label"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="right")
        val_frame = tk.Frame(inner, bg=COLORS["bg_card"])
        val_frame.pack(fill="x", pady=(4, 0))
        self.val_lbl = tk.Label(val_frame, text=str(value),
                                font=FONTS["kpi"], bg=COLORS["bg_card"], fg=color)
        self.val_lbl.pack(side="left")
        if unit:
            tk.Label(val_frame, text=f" {unit}", font=FONTS["small"],
                     bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(side="left", padx=(2, 0), anchor="s")

    def update_value(self, value):
        self.val_lbl.configure(text=str(value))

_SCROLL_STYLES_READY = False


def _ensure_scrollbar_style():
    """اسکرول‌بار تخت و مدرن — تم clam لازم است تا رنگ‌ها در ویندوز هم اعمال شوند."""
    global _SCROLL_STYLES_READY
    if _SCROLL_STYLES_READY:
        return
    _SCROLL_STYLES_READY = True
    style = ttk.Style()
    try:
        if style.theme_use() != "clam":
            style.theme_use("clam")
    except Exception:
        pass
    # پایه‌ی تیره برای همه‌ی ویجت‌های ttk
    style.configure(".", background=COLORS["bg_card"],
                    foreground=COLORS["text_primary"],
                    fieldbackground=COLORS["bg_input"],
                    bordercolor=COLORS["border"],
                    troughcolor=COLORS["bg_dark"])
    # کمبوباکس (زیر تم جدید دوباره تنظیم می‌شود تا قبلی‌ها هم درست بمانند)
    style.configure("Dark.TCombobox",
                    fieldbackground=COLORS["bg_input"],
                    background=COLORS["bg_input"],
                    foreground=COLORS["text_primary"],
                    selectbackground=COLORS["accent_dim"],
                    selectforeground=COLORS["text_primary"],
                    arrowcolor=COLORS["text_secondary"])
    # اسکرول‌بار بدون فلش — کاملاً تخت
    style.layout("Dark.Vertical.TScrollbar",
                 [("Vertical.Scrollbar.trough", {"children":
                     [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
                   "sticky": "ns"})])
    style.layout("Dark.Horizontal.TScrollbar",
                 [("Horizontal.Scrollbar.trough", {"children":
                     [("Horizontal.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
                   "sticky": "ew"})])
    for name in ("Dark.Vertical.TScrollbar", "Dark.Horizontal.TScrollbar"):
        style.configure(name, troughcolor=COLORS["bg_dark"],
                        background=COLORS["bg_card"],
                        bordercolor=COLORS["bg_dark"],
                        lightcolor=COLORS["bg_card"],
                        darkcolor=COLORS["bg_card"],
                        gripcount=0, width=12)
        style.map(name,
                  background=[("pressed", COLORS["accent"]),
                              ("active", COLORS["accent_dim"])])

class StyledTreeview(tk.Frame):
    def __init__(self, parent, columns, headings=None, row_height=32, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        _ensure_scrollbar_style()
        headings = headings or columns
        if row_height not in _STYLE_CACHE:
            uid = f"TV{row_height}.Treeview"
            style = ttk.Style()
            style.configure(uid, background=COLORS["bg_table"], foreground=COLORS["text_primary"],
                            fieldbackground=COLORS["bg_table"], borderwidth=0, relief="flat",
                            rowheight=row_height, font=FONTS["body"])
            style.configure(f"{uid}.Heading", background=COLORS["bg_header"],
                            foreground=COLORS["accent"], font=FONTS["body_bold"],
                            relief="flat", borderwidth=0)
            style.map(uid, background=[("selected", COLORS["accent_dim"])],
                      foreground=[("selected", COLORS["text_primary"])])
            style.layout(uid, [('Treeview.treearea', {'sticky': 'nswe'})])
            _STYLE_CACHE[row_height] = uid
        uid = _STYLE_CACHE[row_height]
        self.tree = ttk.Treeview(self, columns=columns, show="headings",
                                 yscrollcommand=self._on_yscroll,
                                 xscrollcommand=self._on_xscroll, style=uid)
        self.vsb = ttk.Scrollbar(self, orient="vertical",
                                 style="Dark.Vertical.TScrollbar",
                                 command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self, orient="horizontal",
                                 style="Dark.Horizontal.TScrollbar",
                                 command=self.tree.xview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        # اسکرول افقی با Shift + چرخ ماوس (برای جدول‌های عریض)
        self.tree.bind("<Shift-MouseWheel>",
                       lambda e: self.tree.xview_scroll(-1 * (e.delta // 120), "units"))
        for col, head in zip(columns, headings):
            self.tree.heading(col, text=head, anchor="center")
            self.tree.column(col, anchor="center", minwidth=60)
        self.tree.tag_configure("odd", background=COLORS["bg_table"])
        self.tree.tag_configure("even", background=COLORS["bg_table_alt"])
        for op, clr in OPERATOR_COLORS.items():
            self.tree.tag_configure(f"op_{op}", foreground=clr)
        for pri, clr in PRIORITY_COLORS.items():
            self.tree.tag_configure(f"pri_{pri}", foreground=clr)

    def _on_yscroll(self, first, last):
        self.vsb.set(first, last)

    def _on_xscroll(self, first, last):
        self.hsb.set(first, last)

    def clear(self):
        self.tree.delete(*self.tree.get_children())

    def insert(self, values, tags=(), iid=None):
        row_count = len(self.tree.get_children())
        alt_tag = "even" if row_count % 2 == 0 else "odd"
        all_tags = (alt_tag,) + tuple(tags)
        if iid:
            return self.tree.insert("", "end", iid=iid, values=values, tags=all_tags)
        return self.tree.insert("", "end", values=values, tags=all_tags)

    def get_selected_values(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])["values"]

class GaugeMeter(tk.Canvas):
    """Semicircle gauge - safe deferred draw"""
    def __init__(self, parent, value=0, max_val=100, label="", color=None, size=160, **kwargs):
        self._size = size
        self._max = max_val
        self._color = color or COLORS["accent"]
        self._label = label
        self._value = value
        super().__init__(parent,
                         width=size, height=size // 2 + 36,
                         bg=COLORS["bg_card"], highlightthickness=0, **kwargs)
        self.after(10, self._safe_draw)

    def _safe_draw(self):
        if self.winfo_exists():
            self._draw(self._value)

    def _draw(self, value):
        self.delete("all")
        s = self._size
        cx = s // 2
        cy = s // 2
        r = s // 2 - 14
        pct = min(value / self._max, 1.0) if self._max else 0

        self.create_arc(cx - r, cy - r, cx + r, cy + r,
                        start=0, extent=180, style="arc",
                        outline=COLORS["border"], width=10)
        if pct > 0.01:
            extent = pct * 180
            self.create_arc(cx - r, cy - r, cx + r, cy + r,
                            start=180 - extent, extent=extent,
                            style="arc", outline=self._color, width=10)

        self.create_text(cx, cy + 4,
                         text=f"{value}",
                         font=("Segoe UI", 14, "bold"),
                         fill=self._color)
        self.create_text(cx, cy + 22,
                         text=self._label,
                         font=("Segoe UI", 8),
                         fill=COLORS["text_muted"])

    def update_value(self, value):
        self._value = value
        self._draw(value)


class IconButton(tk.Frame):
    def __init__(self, parent, text, icon="", command=None,
                 color=None, fg=None, width=120, **kwargs):
        color = color or COLORS["accent"]
        fg = fg or COLORS["bg_dark"]
        super().__init__(parent, bg=COLORS["bg_card"], cursor="hand2", **kwargs)
        self.btn = tk.Label(self, text=f"{icon}  {text}" if icon else text,
                            font=FONTS["body_bold"], bg=color, fg=fg,
                            padx=14, pady=7, cursor="hand2", width=width // 8)
        self.btn.pack()
        for w in [self, self.btn]:
            w.bind("<Button-1>", lambda e: command() if command else None)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
        self._color = color

    def _on_enter(self, e):
        glow = COLORS["accent_glow"] if self._color == COLORS["accent"] else self._color
        self.btn.configure(bg=glow)

    def _on_leave(self, e):
        self.btn.configure(bg=self._color)


class StatusBadge(tk.Label):
    def __init__(self, parent, text, **kwargs):
        color = STATUS_COLORS.get(text, COLORS["text_muted"])
        bg_map = {"باز": "#3D3000", "در حال انجام": "#1E3A5F",
                  "بسته": "#14532D", "معلق": "#3B0764"}
        bg = bg_map.get(text, COLORS["bg_card"])
        super().__init__(parent, text=f"● {text}", font=FONTS["small"],
                         fg=color, bg=bg, padx=8, pady=3, **kwargs)


class ToastNotification(tk.Toplevel):
    def __init__(self, parent, message, kind="success"):
        super().__init__(parent)
        self.overrideredirect(True)
        colors = {"success": COLORS["green"], "error": COLORS["red"], "info": COLORS["blue"]}
        icons = {"success": "✓", "error": "✗", "info": "ℹ"}
        c = colors.get(kind, COLORS["green"])
        i = icons.get(kind, "✓")
        self.configure(bg=COLORS["bg_card"])
        frame = tk.Frame(self, bg=COLORS["bg_card"],
                         highlightbackground=c, highlightthickness=1)
        frame.pack()
        tk.Label(frame, text=f"{i}  {message}", font=FONTS["body_bold"],
                 bg=COLORS["bg_card"], fg=c, padx=20, pady=12).pack()
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        w = self.winfo_reqwidth()
        self.geometry(f"+{sw - w - 40}+60")
        self.attributes("-topmost", True)
        self.after(2800, self._auto_close)

    def _auto_close(self):
        if self.winfo_exists():
            self.destroy()


class FormField(tk.Frame):
    """Labeled form input - entry / combobox / text area"""
    def __init__(self, parent, label, field_type="entry", options=None,
                 required=False, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        req_mark = " *" if required else ""
        tk.Label(self, text=f"{label}{req_mark}", font=FONTS["small"],
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                 anchor="w").pack(fill="x")
        self.var = tk.StringVar()
        if field_type == "entry":
            self.widget = tk.Entry(self, textvariable=self.var, font=FONTS["body"],
                                   bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                                   insertbackground=COLORS["accent"], relief="flat",
                                   highlightbackground=COLORS["border"],
                                   highlightthickness=1, bd=4)
            self.widget.pack(fill="x", ipady=5, pady=(2, 0))
        elif field_type == "combobox":
            style = ttk.Style()
            style.configure("Dark.TCombobox",
                            fieldbackground=COLORS["bg_input"],
                            background=COLORS["bg_input"],
                            foreground=COLORS["text_primary"],
                            selectbackground=COLORS["accent_dim"],
                            selectforeground=COLORS["text_primary"])
            self.widget = ttk.Combobox(self, textvariable=self.var,
                                       values=options or [], font=FONTS["body"],
                                       style="Dark.TCombobox", state="readonly")
            self.widget.pack(fill="x", pady=(2, 0))
        elif field_type == "text":
            self.widget = tk.Text(self, font=FONTS["body"],
                                  bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                                  insertbackground=COLORS["accent"], relief="flat",
                                  highlightbackground=COLORS["border"],
                                  highlightthickness=1, height=3, wrap="word")
            self.widget.pack(fill="x", pady=(2, 0))
            self.var = None
        if field_type in ("entry", "text"):
            self.widget.bind("<FocusIn>", lambda e: self.widget.configure(highlightbackground=COLORS["border_focus"]))
            self.widget.bind("<FocusOut>", lambda e: self.widget.configure(highlightbackground=COLORS["border"]))

    def get(self):
        if self.var:
            return self.var.get()
        if isinstance(self.widget, tk.Text):
            return self.widget.get("1.0", "end-1c")
        return ""

    def set(self, value):
        if self.var:
            self.var.set(value)
        elif isinstance(self.widget, tk.Text):
            self.widget.delete("1.0", "end")
            self.widget.insert("1.0", value)