from tkinter import ttk

# (имя страницы в app.register_page, подпись вкладки)
TABS = (
    ("students_page", "Студенты"),
    ("visualization_page", "Визуализация"),
)


def build_tabs(parent, app, active, filepath):
    """
    Панель вкладок для шапки: сегментированный переключатель («таблетка»).
    Активная вкладка — светлый фон и акцентный текст, остальные — приглушённый текст
    на фоне общей рамки; клик переключает страницу.
    """
    bar = ttk.Frame(parent, style="TabsBar.TFrame", padding=3)
    for name, title in TABS:
        is_active = name == active
        ttk.Button(bar, text=title, cursor="" if is_active else "hand2",
                   style="TabActive.TButton" if is_active else "Tab.TButton",
                   command=(lambda: None) if is_active
                   else (lambda n=name: app.show_window(n, filepath))
                   ).pack(side="left")
    return bar