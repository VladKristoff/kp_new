from tkinter import ttk

from config import FONT_FAMILY

# ----------------------------------------------------------------------
# Палитры. Тёмная тема — те же акценты (Indigo & Mint), но на глубоком синем фоне.
# ----------------------------------------------------------------------
PALETTES = {
    "light": {
        "bg": "#F3F5FB",          # фон окна
        "surface": "#FFFFFF",     # карточки
        "surface_alt": "#F8FAFC",  # полосатые строки, шапка таблицы
        "header": "#FFFFFF",
        "border": "#E2E8F0",
        "text": "#0F172A",
        "muted": "#64748B",
        "accent": "#4F46E5",
        "accent_hover": "#4338CA",
        "accent_active": "#312E81",
        "on_accent": "#FFFFFF",
        "accent_soft": "#E0E7FF",
        "mint": "#10B981",
        "input_bg": "#FFFFFF",
        "btn2": "#EEF2F7",
        "btn2_hover": "#E2E8F0",
        "btn2_active": "#CBD5E1",
        "disabled_bg": "#D5DAE5",
        "disabled_fg": "#F8FAFC",
        "scroll": "#CBD5E1",
        "scroll_hover": "#94A3B8",
        "select_bg": "#E0E7FF",
        "select_fg": "#1E1B4B",
        "low_bg": "#FEE2E2",
        "low_fg": "#991B1B",
        "warn_bg": "#FEF3C7",
        "warn_fg": "#92400E",
        "deco1": "#E4E8FB",
        "deco2": "#D9F5EA",
    },
    "dark": {
        "bg": "#0E1120",
        "surface": "#171B2D",
        "surface_alt": "#1C2136",
        "header": "#171B2D",
        "border": "#2A3050",
        "text": "#E8EAF6",
        "muted": "#8F96B8",
        "accent": "#6366F1",
        "accent_hover": "#7C7FF7",
        "accent_active": "#4F46E5",
        "on_accent": "#FFFFFF",
        "accent_soft": "#2B2F5C",
        "mint": "#34D399",
        "input_bg": "#10142A",
        "btn2": "#232843",
        "btn2_hover": "#2C3254",
        "btn2_active": "#383F68",
        "disabled_bg": "#262B45",
        "disabled_fg": "#5B6285",
        "scroll": "#3A4166",
        "scroll_hover": "#4C5585",
        "select_bg": "#33377A",
        "select_fg": "#FFFFFF",
        "low_bg": "#3F1D2B",
        "low_fg": "#FCA5A5",
        "warn_bg": "#3D3217",
        "warn_fg": "#FCD34D",
        "deco1": "#161B3A",
        "deco2": "#0F2C2B",
    },
}


def configure_tree_tags(tree, p):
    """Цвета строк таблицы: чередование и подсветка. Вызывать при смене темы."""
    tree.tag_configure("odd", background=p["surface"])
    tree.tag_configure("even", background=p["surface_alt"])
    tree.tag_configure("low_score", background=p["low_bg"], foreground=p["low_fg"])
    tree.tag_configure("many_absences", background=p["warn_bg"], foreground=p["warn_fg"])


def _button(style, name, *, bg, hover, pressed, fg, fg_pressed=None,
            disabled_bg, disabled_fg, font, padding, width=0):
    flat = dict(borderwidth=0, relief="flat")
    style.configure(name, font=font, padding=padding, anchor="center", width=width,
                    background=bg, foreground=fg, focuscolor=bg,
                    bordercolor=bg, lightcolor=bg, darkcolor=bg, **flat)
    # «pressed» должен стоять раньше «active», иначе нажатие не будет видно
    states = [("disabled", disabled_bg), ("pressed", pressed), ("active", hover)]
    style.map(name,
              background=states, bordercolor=states, lightcolor=states, darkcolor=states,
              foreground=[("disabled", disabled_fg), ("pressed", fg_pressed or fg),
                          ("active", fg)],
              relief=[("pressed", "flat")])


def set_styles(root, theme="light"):
    """Применяет тему ко всем ttk-стилям и возвращает палитру (dict)."""
    p = PALETTES[theme]
    F = FONT_FAMILY
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=p["bg"], foreground=p["text"], font=(F, 10),
                    troughcolor=p["border"], focuscolor=p["accent"])

    # --- Фреймы ---
    style.configure("TFrame", background=p["bg"])
    style.configure("Surface.TFrame", background=p["surface"])
    style.configure("Card.TFrame", background=p["surface"], relief="solid", borderwidth=1,
                    bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"])
    style.configure("Header.TFrame", background=p["header"])
    style.configure("Line.TFrame", background=p["border"])
    style.configure("TLabelframe", background=p["surface"], bordercolor=p["border"],
                    lightcolor=p["border"], darkcolor=p["border"])
    style.configure("TLabelframe.Label", background=p["surface"], foreground=p["text"],
                    font=(F, 10, "bold"))

    # --- Надписи ---
    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Card.TLabel", background=p["surface"])
    style.configure("CardTitle.TLabel", background=p["surface"], font=(F, 11, "bold"))
    style.configure("CardHint.TLabel", background=p["surface"], foreground=p["muted"],
                    font=(F, 9))
    style.configure("Value.TLabel", background=p["surface"], foreground=p["accent"],
                    font=(F, 22, "bold"))
    style.configure("Name.TLabel", background=p["surface"], font=(F, 16, "bold"))
    style.configure("Subtitle.TLabel", background=p["surface"], foreground=p["muted"],
                    font=(F, 11))
    style.configure("Header.TLabel", background=p["header"], font=(F, 13, "bold"))
    style.configure("BigLabel.TLabel", background=p["surface"], foreground=p["accent"],
                    font=(F, 34, "bold"))
    style.configure("SmallLabel.TLabel", background=p["bg"], font=(F, 12, "bold"))
    style.configure("Hint.TLabel", background=p["bg"], foreground=p["muted"], font=(F, 9))

    # --- Поля ввода ---
    focus = [("focus", p["accent"])]
    style.configure("TEntry", fieldbackground=p["input_bg"], foreground=p["text"],
                    insertcolor=p["text"], padding=(10, 8), borderwidth=1,
                    bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"])
    style.map("TEntry", bordercolor=focus, lightcolor=focus, darkcolor=focus)

    # --- Таблицы ---
    style.configure("Treeview", background=p["surface"], fieldbackground=p["surface"],
                    foreground=p["text"], rowheight=38, borderwidth=0, relief="flat",
                    font=(F, 10))
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # без рамки
    style.map("Treeview", background=[("selected", p["select_bg"])],
              foreground=[("selected", p["select_fg"])])
    style.configure("Treeview.Heading", background=p["surface_alt"], foreground=p["muted"],
                    font=(F, 10, "bold"), relief="flat", padding=(12, 10), borderwidth=1,
                    bordercolor=p["border"], lightcolor=p["surface_alt"],
                    darkcolor=p["surface_alt"])
    style.map("Treeview.Heading", background=[("active", p["accent_soft"])],
              foreground=[("active", p["accent"])])

    # --- Полоса прокрутки: тонкая, без стрелок ---
    style.layout("Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    style.configure("Vertical.TScrollbar", background=p["scroll"], troughcolor=p["surface"],
                    bordercolor=p["surface"], lightcolor=p["scroll"], darkcolor=p["scroll"],
                    arrowsize=12, relief="flat", borderwidth=0, gripcount=0)
    hover = [("active", p["scroll_hover"])]
    style.map("Vertical.TScrollbar", background=hover, lightcolor=hover, darkcolor=hover)

    # --- Индикатор загрузки ---
    style.configure("Horizontal.TProgressbar", background=p["accent"], troughcolor=p["border"],
                    bordercolor=p["border"], lightcolor=p["accent"], darkcolor=p["accent"],
                    thickness=6)

    # --- Кнопки ---
    primary = dict(bg=p["accent"], hover=p["accent_hover"], pressed=p["accent_active"],
                   fg=p["on_accent"], disabled_bg=p["disabled_bg"], disabled_fg=p["disabled_fg"])
    _button(style, "BlueButton.TButton", font=(F, 12, "bold"), padding=(28, 14), width=22, **primary)
    _button(style, "MainButton.TButton", font=(F, 11, "bold"), padding=(18, 12), **primary)

    secondary = dict(bg=p["btn2"], hover=p["btn2_hover"], pressed=p["btn2_active"],
                     fg=p["text"], disabled_bg=p["btn2"], disabled_fg=p["disabled_fg"])
    _button(style, "Secondary.TButton", font=(F, 10, "bold"), padding=(14, 9), **secondary)

    # «Призрачные» кнопки: на фоне окна и на фоне шапки
    for name, base in (("Ghost.TButton", p["bg"]), ("HeaderGhost.TButton", p["header"])):
        _button(style, name, bg=base, hover=p["btn2_hover"], pressed=p["btn2_active"],
                fg=p["text"], disabled_bg=base, disabled_fg=p["disabled_fg"],
                font=(F, 11, "bold"), padding=(12, 8))
    style.configure("ArrowButton.TButton", font=(F, 12, "bold"))  # совместимость со старым кодом

    return p