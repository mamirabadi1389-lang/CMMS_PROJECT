"""
CMMS Styles — Multi-Theme System (23 Themes)
8 Dark Industrial + 15 Light
"""
import json, os, sys


def _resolve_theme_config_path():
    """
    همون منطق database.py: وقتی به صورت exe اجرا میشه (Program Files و
    مشابه، که کاربر عادی اجازه‌ی نوشتن نداره)، فایل تنظیمات تم رو توی
    %LOCALAPPDATA%\\CMMS بنویس؛ توی حالت توسعه همون کنار سورس بمونه.
    """
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        base = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CMMS"
        )
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "theme_config.json")


THEME_CONFIG_PATH = _resolve_theme_config_path()

# ═════════════════════════════════════════════════════════════════════════════
#  ALL 23 THEMES — Standard format: label, type, preview, colors
# ═════════════════════════════════════════════════════════════════════════════
THEMES = {
    # ── DARK INDUSTRIAL (8) ─────────────────────────────────────────────────
    "dark_orange": {
        "label": "🟠 صنعتی نارنجی", "type": "dark",
        "preview": ["#0D1117", "#F97316", "#161B22"],
        "colors": {"bg_dark":"#0D1117","bg_card":"#161B22","bg_hover":"#1C2333","bg_sidebar":"#0A0F16","bg_header":"#111827","bg_input":"#1A2030","bg_table":"#0F1620","bg_table_alt":"#131A26","accent":"#F97316","accent_dim":"#7C3D12","accent_glow":"#FB923C","blue":"#3B82F6","blue_dim":"#1E3A5F","green":"#22C55E","green_dim":"#14532D","red":"#EF4444","red_dim":"#7F1D1D","yellow":"#EAB308","yellow_dim":"#713F12","purple":"#A855F7","cyan":"#06B6D4","text_primary":"#F0F6FC","text_secondary":"#8B949E","text_muted":"#6E7681","text_accent":"#F97316","border":"#21262D","border_focus":"#F97316","status_open":"#EAB308","status_closed":"#22C55E","status_pending":"#3B82F6","status_critical":"#EF4444"}
    },
    "dark_blue": {
        "label": "🔵 صنعتی آبی", "type": "dark",
        "preview": ["#0B1120", "#3B82F6", "#151E33"],
        "colors": {"bg_dark":"#0B1120","bg_card":"#151E33","bg_hover":"#1C2947","bg_sidebar":"#080D1A","bg_header":"#101A2E","bg_input":"#182238","bg_table":"#0E1830","bg_table_alt":"#121E38","accent":"#3B82F6","accent_dim":"#1E3A5F","accent_glow":"#60A5FA","blue":"#3B82F6","blue_dim":"#1E3A5F","green":"#22C55E","green_dim":"#14532D","red":"#EF4444","red_dim":"#7F1D1D","yellow":"#EAB308","yellow_dim":"#713F12","purple":"#A855F7","cyan":"#06B6D4","text_primary":"#EFF6FF","text_secondary":"#93A5C4","text_muted":"#5D7191","text_accent":"#3B82F6","border":"#1E2A45","border_focus":"#3B82F6","status_open":"#EAB308","status_closed":"#22C55E","status_pending":"#3B82F6","status_critical":"#EF4444"}
    },
    "dark_green": {
        "label": "🟢 صنعتی سبز (HMI)", "type": "dark",
        "preview": ["#0A130E", "#22C55E", "#131F19"],
        "colors": {"bg_dark":"#0A130E","bg_card":"#131F19","bg_hover":"#1B2D22","bg_sidebar":"#080F0B","bg_header":"#0F1A14","bg_input":"#16241C","bg_table":"#0D1911","bg_table_alt":"#111F17","accent":"#22C55E","accent_dim":"#14532D","accent_glow":"#4ADE80","blue":"#3B82F6","blue_dim":"#1E3A5F","green":"#22C55E","green_dim":"#14532D","red":"#EF4444","red_dim":"#7F1D1D","yellow":"#EAB308","yellow_dim":"#713F12","purple":"#A855F7","cyan":"#06B6D4","text_primary":"#EFFDF4","text_secondary":"#8FB89E","text_muted":"#597566","text_accent":"#22C55E","border":"#1D3226","border_focus":"#22C55E","status_open":"#EAB308","status_closed":"#22C55E","status_pending":"#3B82F6","status_critical":"#EF4444"}
    },
    "dark_purple": {
        "label": "🟣 صنعتی بنفش", "type": "dark",
        "preview": ["#120B1F", "#A855F7", "#1A1429"],
        "colors": {"bg_dark":"#120B1F","bg_card":"#1A1429","bg_hover":"#251D38","bg_sidebar":"#0E0918","bg_header":"#161021","bg_input":"#1E1830","bg_table":"#140E22","bg_table_alt":"#1A1328","accent":"#A855F7","accent_dim":"#581C87","accent_glow":"#C084FC","blue":"#3B82F6","blue_dim":"#1E3A5F","green":"#22C55E","green_dim":"#14532D","red":"#EF4444","red_dim":"#7F1D1D","yellow":"#EAB308","yellow_dim":"#713F12","purple":"#A855F7","cyan":"#06B6D4","text_primary":"#FAF5FF","text_secondary":"#A78BFA","text_muted":"#7C6A9E","text_accent":"#A855F7","border":"#2D2250","border_focus":"#A855F7","status_open":"#EAB308","status_closed":"#22C55E","status_pending":"#3B82F6","status_critical":"#EF4444"}
    },
    "dark_amber": {
        "label": "🟤 کهربایی صنعتی", "type": "dark",
        "preview": ["#0F0A05", "#D97706", "#1A140F"],
        "colors": {"bg_dark":"#0F0A05","bg_card":"#1A140F","bg_hover":"#261E14","bg_sidebar":"#0C0803","bg_header":"#14100A","bg_input":"#1E1910","bg_table":"#120D07","bg_table_alt":"#18130C","accent":"#D97706","accent_dim":"#78350F","accent_glow":"#F59E0B","blue":"#3B82F6","blue_dim":"#1E3A5F","green":"#22C55E","green_dim":"#14532D","red":"#EF4444","red_dim":"#7F1D1D","yellow":"#EAB308","yellow_dim":"#713F12","purple":"#A855F7","cyan":"#06B6D4","text_primary":"#FFFBEB","text_secondary":"#BFA88A","text_muted":"#8C7B62","text_accent":"#D97706","border":"#2A2215","border_focus":"#D97706","status_open":"#EAB308","status_closed":"#22C55E","status_pending":"#3B82F6","status_critical":"#EF4444"}
    },
    "dark_red": {
        "label": "🔴 صنعتی قرمز", "type": "dark",
        "preview": ["#120A0A", "#EF4444", "#1F1414"],
        "colors": {"bg_dark":"#120A0A","bg_card":"#1F1414","bg_hover":"#2B1C1C","bg_sidebar":"#0D0808","bg_header":"#1A1010","bg_input":"#241616","bg_table":"#180F0F","bg_table_alt":"#1D1212","accent":"#EF4444","accent_dim":"#7F1D1D","accent_glow":"#F87171","blue":"#3B82F6","blue_dim":"#1E3A5F","green":"#22C55E","green_dim":"#14532D","red":"#EF4444","red_dim":"#7F1D1D","yellow":"#EAB308","yellow_dim":"#713F12","purple":"#A855F7","cyan":"#06B6D4","text_primary":"#FEF2F2","text_secondary":"#C4918F","text_muted":"#7A5654","text_accent":"#EF4444","border":"#341E1E","border_focus":"#EF4444","status_open":"#EAB308","status_closed":"#22C55E","status_pending":"#3B82F6","status_critical":"#EF4444"}
    },
    "dark_cyan": {
        "label": "🩵 صنعتی فیروزه‌ای", "type": "dark",
        "preview": ["#081416", "#06B6D4", "#0F2226"],
        "colors": {"bg_dark":"#081416","bg_card":"#0F2226","bg_hover":"#153035","bg_sidebar":"#050D0F","bg_header":"#0C1B1E","bg_input":"#122A2E","bg_table":"#0B1D20","bg_table_alt":"#0E2124","accent":"#06B6D4","accent_dim":"#164E63","accent_glow":"#22D3EE","blue":"#3B82F6","blue_dim":"#1E3A5F","green":"#22C55E","green_dim":"#14532D","red":"#EF4444","red_dim":"#7F1D1D","yellow":"#EAB308","yellow_dim":"#713F12","purple":"#A855F7","cyan":"#06B6D4","text_primary":"#ECFEFF","text_secondary":"#8EBAC4","text_muted":"#547780","text_accent":"#06B6D4","border":"#1A3438","border_focus":"#06B6D4","status_open":"#EAB308","status_closed":"#22C55E","status_pending":"#3B82F6","status_critical":"#EF4444"}
    },
    "dark_slate": {
        "label": "⬛ خاکستری مینیمال", "type": "dark",
        "preview": ["#0F1215", "#64748B", "#181D22"],
        "colors": {"bg_dark":"#0F1215","bg_card":"#181D22","bg_hover":"#22282F","bg_sidebar":"#0A0D0F","bg_header":"#151A1E","bg_input":"#1D242B","bg_table":"#141A1E","bg_table_alt":"#181F23","accent":"#64748B","accent_dim":"#334155","accent_glow":"#94A3B8","blue":"#3B82F6","blue_dim":"#1E3A5F","green":"#22C55E","green_dim":"#14532D","red":"#EF4444","red_dim":"#7F1D1D","yellow":"#EAB308","yellow_dim":"#713F12","purple":"#A855F7","cyan":"#06B6D4","text_primary":"#F1F5F9","text_secondary":"#94A3B8","text_muted":"#5C6B7D","text_accent":"#64748B","border":"#293138","border_focus":"#64748B","status_open":"#EAB308","status_closed":"#22C55E","status_pending":"#3B82F6","status_critical":"#EF4444"}
    },
    # ── LIGHT (15) ──────────────────────────────────────────────────────────
    "light_neutral": {
        "label": "☀️ روشن خنثی", "type": "light",
        "preview": ["#F3F4F6", "#EA580C", "#FFFFFF"],
        "colors": {"bg_dark":"#F3F4F6","bg_card":"#FFFFFF","bg_hover":"#E5E7EB","bg_sidebar":"#1F2937","bg_header":"#FFFFFF","bg_input":"#F9FAFB","bg_table":"#FFFFFF","bg_table_alt":"#F3F4F6","accent":"#EA580C","accent_dim":"#FED7AA","accent_glow":"#FB923C","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#111827","text_secondary":"#4B5563","text_muted":"#9CA3AF","text_accent":"#EA580C","border":"#E5E7EB","border_focus":"#EA580C","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_blue": {
        "label": "💠 روشن آبی", "type": "light",
        "preview": ["#EFF6FF", "#2563EB", "#FFFFFF"],
        "colors": {"bg_dark":"#EFF6FF","bg_card":"#FFFFFF","bg_hover":"#DBEAFE","bg_sidebar":"#1E3A8A","bg_header":"#FFFFFF","bg_input":"#F0F7FF","bg_table":"#FFFFFF","bg_table_alt":"#EFF6FF","accent":"#2563EB","accent_dim":"#BFDBFE","accent_glow":"#60A5FA","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#0F172A","text_secondary":"#475569","text_muted":"#94A3B8","text_accent":"#2563EB","border":"#CBD5E1","border_focus":"#2563EB","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_green": {
        "label": "🌿 روشن سبز", "type": "light",
        "preview": ["#ECFDF5", "#059669", "#FFFFFF"],
        "colors": {"bg_dark":"#ECFDF5","bg_card":"#FFFFFF","bg_hover":"#D1FAE5","bg_sidebar":"#064E3B","bg_header":"#FFFFFF","bg_input":"#F0FDF4","bg_table":"#FFFFFF","bg_table_alt":"#ECFDF5","accent":"#059669","accent_dim":"#A7F3D0","accent_glow":"#34D399","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#059669","green_dim":"#D1FAE5","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#022C22","text_secondary":"#3D6B5B","text_muted":"#86B8A4","text_accent":"#059669","border":"#BBDECF","border_focus":"#059669","status_open":"#CA8A04","status_closed":"#059669","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_warm": {
        "label": "🌅 روشن گرم", "type": "light",
        "preview": ["#FFF7ED", "#C2410C", "#FFFFFF"],
        "colors": {"bg_dark":"#FFF7ED","bg_card":"#FFFFFF","bg_hover":"#FFEDD5","bg_sidebar":"#431407","bg_header":"#FFFFFF","bg_input":"#FFFAF5","bg_table":"#FFFFFF","bg_table_alt":"#FFF7ED","accent":"#C2410C","accent_dim":"#FED7AA","accent_glow":"#FB923C","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#2A1205","text_secondary":"#7C5C4A","text_muted":"#B59B8A","text_accent":"#C2410C","border":"#E8D5C4","border_focus":"#C2410C","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_soft": {
        "label": "🌸 روشن ملایم", "type": "light",
        "preview": ["#FAF5FF", "#7C3AED", "#FFFFFF"],
        "colors": {"bg_dark":"#FAF5FF","bg_card":"#FFFFFF","bg_hover":"#F3E8FF","bg_sidebar":"#3B0764","bg_header":"#FFFFFF","bg_input":"#FDF4FF","bg_table":"#FFFFFF","bg_table_alt":"#FAF5FF","accent":"#7C3AED","accent_dim":"#DDD6FE","accent_glow":"#A78BFA","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#7C3AED","cyan":"#0891B2","text_primary":"#1E1B4B","text_secondary":"#6D5E8C","text_muted":"#A99BBF","text_accent":"#7C3AED","border":"#DDD6FE","border_focus":"#7C3AED","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_orange": {
        "label": "🟠 روشن نارنجی", "type": "light",
        "preview": ["#F5F5F4", "#EA580C", "#FFFFFF"],
        "colors": {"bg_dark":"#F5F5F4","bg_card":"#FFFFFF","bg_hover":"#F3E8DF","bg_sidebar":"#1C1917","bg_header":"#FFFFFF","bg_input":"#FAF9F7","bg_table":"#FFFFFF","bg_table_alt":"#F5F5F4","accent":"#EA580C","accent_dim":"#FED7AA","accent_glow":"#FB923C","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#1C1917","text_secondary":"#57534E","text_muted":"#A8A29E","text_accent":"#EA580C","border":"#E7E5E4","border_focus":"#EA580C","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_purple": {
        "label": "🟣 روشن بنفش", "type": "light",
        "preview": ["#F6F3FA", "#9333EA", "#FFFFFF"],
        "colors": {"bg_dark":"#F6F3FA","bg_card":"#FFFFFF","bg_hover":"#EDE5F6","bg_sidebar":"#1E1330","bg_header":"#FFFFFF","bg_input":"#FBF9FD","bg_table":"#FFFFFF","bg_table_alt":"#F6F3FA","accent":"#9333EA","accent_dim":"#E9D5FF","accent_glow":"#A855F7","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#1E1030","text_secondary":"#5D4A73","text_muted":"#A290B5","text_accent":"#9333EA","border":"#E5DAF0","border_focus":"#9333EA","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_minimal": {
        "label": "⬜ روشن مینیمال", "type": "light",
        "preview": ["#FAFAFA", "#171717", "#FFFFFF"],
        "colors": {"bg_dark":"#FAFAFA","bg_card":"#FFFFFF","bg_hover":"#F0F0F0","bg_sidebar":"#171717","bg_header":"#FFFFFF","bg_input":"#F5F5F5","bg_table":"#FFFFFF","bg_table_alt":"#FAFAFA","accent":"#171717","accent_dim":"#D4D4D4","accent_glow":"#404040","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#0A0A0A","text_secondary":"#525252","text_muted":"#A3A3A3","text_accent":"#171717","border":"#E5E5E5","border_focus":"#171717","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_red": {
        "label": "🔴 روشن قرمز", "type": "light",
        "preview": ["#FDF4F3", "#DC2626", "#FFFFFF"],
        "colors": {"bg_dark":"#FDF4F3","bg_card":"#FFFFFF","bg_hover":"#FBE5E3","bg_sidebar":"#2C1210","bg_header":"#FFFFFF","bg_input":"#FEF9F8","bg_table":"#FFFFFF","bg_table_alt":"#FDF4F3","accent":"#DC2626","accent_dim":"#FECACA","accent_glow":"#EF4444","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#2C1210","text_secondary":"#78453F","text_muted":"#B08A85","text_accent":"#DC2626","border":"#F5DDDB","border_focus":"#DC2626","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_teal": {
        "label": "🩵 روشن فیروزه‌ای", "type": "light",
        "preview": ["#F0F9F8", "#0D9488", "#FFFFFF"],
        "colors": {"bg_dark":"#F0F9F8","bg_card":"#FFFFFF","bg_hover":"#DFF2F0","bg_sidebar":"#0F2B29","bg_header":"#FFFFFF","bg_input":"#F5FBFA","bg_table":"#FFFFFF","bg_table_alt":"#F0F9F8","accent":"#0D9488","accent_dim":"#99F6E4","accent_glow":"#14B8A6","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#0B2B28","text_secondary":"#3F6E68","text_muted":"#8FB3AE","text_accent":"#0D9488","border":"#D5EEEB","border_focus":"#0D9488","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_amber": {
        "label": "🟡 روشن کهربایی", "type": "light",
        "preview": ["#FEFAF0", "#D97706", "#FFFFFF"],
        "colors": {"bg_dark":"#FEFAF0","bg_card":"#FFFFFF","bg_hover":"#FCF0D5","bg_sidebar":"#2E2308","bg_header":"#FFFFFF","bg_input":"#FFFDF6","bg_table":"#FFFFFF","bg_table_alt":"#FEFAF0","accent":"#D97706","accent_dim":"#FDE68A","accent_glow":"#F59E0B","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#2E2308","text_secondary":"#7A6329","text_muted":"#B8A672","text_accent":"#D97706","border":"#F3E4BC","border_focus":"#D97706","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_rose": {
        "label": "🌷 روشن صورتی", "type": "light",
        "preview": ["#FDF3F6", "#E11D74", "#FFFFFF"],
        "colors": {"bg_dark":"#FDF3F6","bg_card":"#FFFFFF","bg_hover":"#FBE4EB","bg_sidebar":"#2B0F1A","bg_header":"#FFFFFF","bg_input":"#FEF8FA","bg_table":"#FFFFFF","bg_table_alt":"#FDF3F6","accent":"#E11D74","accent_dim":"#FBCFE8","accent_glow":"#EC4899","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#2B0F1A","text_secondary":"#7A4459","text_muted":"#B98CA0","text_accent":"#E11D74","border":"#F5DCE6","border_focus":"#E11D74","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_indigo": {
        "label": "🔷 روشن نیلی", "type": "light",
        "preview": ["#F2F3FB", "#4F46E5", "#FFFFFF"],
        "colors": {"bg_dark":"#F2F3FB","bg_card":"#FFFFFF","bg_hover":"#E4E6F8","bg_sidebar":"#161A3A","bg_header":"#FFFFFF","bg_input":"#F8F9FD","bg_table":"#FFFFFF","bg_table_alt":"#F2F3FB","accent":"#4F46E5","accent_dim":"#C7D2FE","accent_glow":"#6366F1","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#161A3A","text_secondary":"#4C4F7A","text_muted":"#9498C4","text_accent":"#4F46E5","border":"#E1E3F5","border_focus":"#4F46E5","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_slate": {
        "label": "⬜ روشن خاکستری", "type": "light",
        "preview": ["#F8FAFC", "#475569", "#FFFFFF"],
        "colors": {"bg_dark":"#F8FAFC","bg_card":"#FFFFFF","bg_hover":"#EEF1F5","bg_sidebar":"#1E293B","bg_header":"#FFFFFF","bg_input":"#F8FAFC","bg_table":"#FFFFFF","bg_table_alt":"#F8FAFC","accent":"#475569","accent_dim":"#CBD5E1","accent_glow":"#64748B","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#0F172A","text_secondary":"#475569","text_muted":"#94A3B8","text_accent":"#475569","border":"#E2E8F0","border_focus":"#475569","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
    "light_cream": {
        "label": "🍦 روشن کرم", "type": "light",
        "preview": ["#FAF6EF", "#B45309", "#FFFDF9"],
        "colors": {"bg_dark":"#FAF6EF","bg_card":"#FFFDF9","bg_hover":"#F2EAD9","bg_sidebar":"#2B2417","bg_header":"#FFFDF9","bg_input":"#FCF9F2","bg_table":"#FFFDF9","bg_table_alt":"#FAF6EF","accent":"#B45309","accent_dim":"#FDE9CC","accent_glow":"#D97706","blue":"#2563EB","blue_dim":"#DBEAFE","green":"#16A34A","green_dim":"#DCFCE7","red":"#DC2626","red_dim":"#FEE2E2","yellow":"#CA8A04","yellow_dim":"#FEF9C3","purple":"#9333EA","cyan":"#0891B2","text_primary":"#2B2417","text_secondary":"#6B5D40","text_muted":"#A69878","text_accent":"#B45309","border":"#ECE0C8","border_focus":"#B45309","status_open":"#CA8A04","status_closed":"#16A34A","status_pending":"#2563EB","status_critical":"#DC2626"}
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────
def _load_theme_name() -> str:
    try:
        with open(THEME_CONFIG_PATH, "r", encoding="utf-8") as f:
            name = json.load(f).get("theme", "dark_orange")
            return name if name in THEMES else "dark_orange"
    except Exception:
        return "dark_orange"


def save_theme(name: str):
    if name not in THEMES:
        return
    with open(THEME_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"theme": name}, f, ensure_ascii=False)


# ── Active theme ─────────────────────────────────────────────────────────────
CURRENT_THEME = _load_theme_name()
COLORS = THEMES[CURRENT_THEME]["colors"]

# ── Shared constants ─────────────────────────────────────────────────────────
FONTS = {
    "title": ("Segoe UI", 22, "bold"),
    "heading": ("Segoe UI", 14, "bold"),
    "subhead": ("Segoe UI", 11, "bold"),
    "body": ("Segoe UI", 10),
    "body_bold": ("Segoe UI", 10, "bold"),
    "small": ("Segoe UI", 9),
    "mono": ("Consolas", 10),
    "kpi": ("Segoe UI", 28, "bold"),
    "kpi_label": ("Segoe UI", 9),
    "arabic": ("Tahoma", 10),
    "arabic_b": ("Tahoma", 11, "bold"),
    "sidebar": ("Segoe UI", 11),
}
OPERATOR_COLORS = {"مکانیک": "#F97316", "برق": "#3B82F6", "تاسیسات": "#22C55E"}
PRIORITY_COLORS = {"بحرانی": "#EF4444", "بالا": "#F97316", "متوسط": "#EAB308", "پایین": "#22C55E"}
STATUS_COLORS = {"باز": "#EAB308", "در حال انجام": "#3B82F6", "بسته": "#22C55E", "معلق": "#A855F7"}
SIDEBAR_MENU = [
    ("🏠", "داشبورد"), ("📋", "دستور کار جدید"), ("📁", "لیست دستور کارها"),
    ("🔧", "تجهیزات"), ("📅", "برنامه PM"), ("📦", "قطعات یدکی"),("📊", "گزارش‌ها"),
    ("📈", "تحلیل داده ها"),
    # --- افزوده شد: OEE / DCC / ثبت تجربیات / کارتابل ---
    ("🎯", "OEE"), ("🗂️", "DCC"), ("📚", "ثبت تجربیات"),
    ("⚙️", "تنظیمات")
]