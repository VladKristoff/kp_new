import math
import os
import tkinter as tk
from tkinter import ttk, messagebox

from config import FONT_FAMILY, LOW_SCORE_THRESHOLD
from database import repository
from view.tabs import build_tabs


def fmt_number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".") if value is not None else "—"


def short_name(fio):
    """Иванов Иван Иванович -> Иванов И.И."""
    parts = fio.split()
    if len(parts) <= 1:
        return fio
    return f"{parts[0]} " + "".join(f"{w[0]}." for w in parts[1:3])


class VisualizationPage:
    SORT_VALUES = ("Баллы по убыванию", "Баллы по возрастанию", "Как в списке")

    def __init__(self, main_frame, app, filepath):
        self.main_frame = main_frame
        self.app = app
        self.filepath = filepath

        self.sort_var = tk.StringVar(value=self.SORT_VALUES[0])
        self.threshold = float(LOW_SCORE_THRESHOLD)

        self._students = []   # [(фио, балл)] — только студенты с итоговым баллом
        self._no_score = 0    # сколько студентов без итогового балла

        self.create_widgets()
        self.load_data()
        self.draw()

    # ------------------------------------------------------------------
    # Интерфейс
    # ------------------------------------------------------------------

    def create_widgets(self):
        header = ttk.Frame(self.main_frame, style="Header.TFrame")
        header.pack(fill="x", side="top")
        ttk.Button(header, text="←  Назад", cursor="hand2", style="HeaderGhost.TButton",
                   command=self.back_to_main_menu).pack(side="left", padx=(14, 0), pady=10)
        build_tabs(header, self.app, "visualization_page", self.filepath).pack(side="left", padx=16)
        self.theme_btn = ttk.Button(header, text=self.app.theme_icon, width=3, cursor="hand2",
                                    style="HeaderGhost.TButton", command=self.app.toggle_theme)
        self.theme_btn.pack(side="right", padx=14)
        ttk.Frame(self.main_frame, style="Line.TFrame", height=1).pack(fill="x", side="top")

        ttk.Label(self.main_frame, text=f"Файл: {os.path.basename(self.filepath)}",
                  style="Hint.TLabel").pack(side="bottom", pady=8)

        content = ttk.Frame(self.main_frame)
        content.pack(fill="both", expand=True, padx=20, pady=(18, 4))

        self._build_left_panel(content)

        chart_card = ttk.Frame(content, style="Card.TFrame", padding=1)
        chart_card.pack(side="right", fill="both", expand=True)
        self.canvas = tk.Canvas(chart_card, bg=self.app.palette["surface"], bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        # Прокрутка колесом мыши (если студентов много и диаграмма не помещается)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.canvas.bind("<Button-4>", lambda _e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda _e: self.canvas.yview_scroll(1, "units"))

    def _build_left_panel(self, parent):
        panel = ttk.Frame(parent, width=290)
        panel.pack(side="left", fill="y", padx=(0, 18), anchor="n")
        panel.pack_propagate(False)

        # --- Сортировка ---
        sort_card = ttk.Frame(panel, style="Card.TFrame", padding=16)
        sort_card.pack(fill="x", pady=(0, 14))
        ttk.Label(sort_card, text="Сортировка", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        combo = ttk.Combobox(sort_card, textvariable=self.sort_var, state="readonly",
                             values=self.SORT_VALUES)
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", lambda _e: self.draw())

        # --- Сводка ---
        stats = ttk.Frame(panel, style="Card.TFrame", padding=16)
        stats.pack(fill="x", pady=(0, 14))
        ttk.Label(stats, text="Сводка", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        self.best_label = self._stat(stats, "Лучший результат")
        self.avg_label = self._stat(stats, "Средний балл")
        self.low_label = self._stat(stats, "Ниже порога")

    @staticmethod
    def _stat(parent, caption):
        value = ttk.Label(parent, text="—", style="Value.TLabel", font=(FONT_FAMILY, 16, "bold"))
        value.pack(anchor="w")
        ttk.Label(parent, text=caption, style="CardHint.TLabel").pack(anchor="w", pady=(0, 6))
        return value

    # ------------------------------------------------------------------
    # Данные и действия
    # ------------------------------------------------------------------

    def load_data(self):
        try:
            rows = repository.get_students()
        except Exception as e:
            messagebox.showerror("Ошибка базы данных", f"Не удалось получить данные:\n{e}")
            return

        self._students = [(r["fio"], r["itog_ball"]) for r in rows if r["itog_ball"] is not None]
        self._no_score = len(rows) - len(self._students)

        if self._students:
            best_name, best_score = max(self._students, key=lambda s: s[1])
            avg = sum(s[1] for s in self._students) / len(self._students)
            low = sum(1 for s in self._students if s[1] < self.threshold)
            self.best_label.config(text=f"{fmt_number(best_score)} · {short_name(best_name)}")
            self.avg_label.config(text=fmt_number(avg))
            self.low_label.config(text=f"{low} из {len(self._students)}")

    def back_to_main_menu(self):
        if messagebox.askyesno("Внимание!", "Вы уверены, что хотите выйти в главное меню?"):
            self.app.show_window("main_menu")

    def on_theme_changed(self):
        self.canvas.configure(bg=self.app.palette["surface"])
        self.theme_btn.config(text=self.app.theme_icon)
        self.draw()

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------

    def draw(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        c.configure(scrollregion=(0, 0, w, h))
        c.yview_moveto(0)
        self.draw_students_scores(c)

    def _title(self, c, title, subtitle):
        p = self.app.palette
        c.create_text(28, 26, anchor="nw", text=title, fill=p["text"], font=(FONT_FAMILY, 15, "bold"))
        c.create_text(28, 54, anchor="nw", text=subtitle, fill=p["muted"], font=(FONT_FAMILY, 10))

    def draw_students_scores(self, c):
        """Горизонтальные столбцы: студент — его итоговый балл."""
        p, F = self.app.palette, FONT_FAMILY
        w, view_h = c.winfo_width(), c.winfo_height()
        if w < 50 or view_h < 50:
            return

        self._title(c, "Баллы студентов", "Итоговый балл каждого студента")
        # Легенда
        lx = w - 28
        for color, text in ((p["low_fg"], f"ниже {fmt_number(self.threshold)}"), (p["accent"], "остальные")):
            tw = len(text) * 7
            c.create_text(lx, 34, anchor="e", text=text, fill=p["muted"], font=(F, 10))
            c.create_rectangle(lx - tw - 22, 28, lx - tw - 10, 40, fill=color, outline="")
            lx -= tw + 40

        if not self._students:
            c.create_text(w / 2, view_h / 2, text="Нет итоговых баллов для диаграммы",
                          fill=p["muted"], font=(F, 12))
            return

        data = list(self._students)
        order = self.sort_var.get()
        if order == "Баллы по убыванию":
            data.sort(key=lambda s: -s[1])
        elif order == "Баллы по возрастанию":
            data.sort(key=lambda s: s[1])

        n = len(data)
        top, bottom, left, right = 112, 56, 200, 70
        row_h = max(24, (view_h - top - bottom) / n)
        total_h = top + n * row_h + bottom
        c.configure(scrollregion=(0, 0, w, max(total_h, view_h)))

        y_max = max(1, math.ceil(max(s[1] for s in data)))
        x0, x1 = left, w - right
        scale = (x1 - x0) / y_max
        base_y = top + n * row_h

        # Сетка и подписи шкалы сверху
        ticks = min(y_max, 10)
        for i in range(ticks + 1):
            value = y_max * i / ticks
            x = x0 + value * scale
            c.create_line(x, top - 6, x, base_y, fill=p["border"])
            c.create_text(x, top - 12, anchor="s", text=f"{value:g}", fill=p["muted"], font=(F, 9))

        bar_h = row_h * 0.62
        for i, (fio, score) in enumerate(data):
            cy = top + row_h * (i + 0.5)
            color = p["low_fg"] if score < self.threshold else p["accent"]
            c.create_text(left - 12, cy, anchor="e", text=short_name(fio), fill=p["text"], font=(F, 10))
            c.create_rectangle(x0, cy - bar_h / 2, max(x0 + 2, x0 + score * scale), cy + bar_h / 2,
                               fill=color, outline="")
            c.create_text(x0 + score * scale + 8, cy, anchor="w", text=fmt_number(score),
                          fill=p["text"], font=(F, 10, "bold"))

        # Линия среднего балла
        avg = sum(s[1] for s in data) / n
        ax = x0 + avg * scale
        c.create_line(ax, top - 6, ax, base_y, fill=p["muted"], dash=(5, 4), width=2)
        c.create_text(ax, base_y + 10, anchor="n", text=f"средний балл {fmt_number(avg)}",
                      fill=p["muted"], font=(F, 10, "bold"))
        c.create_line(x0, top - 6, x0, base_y, fill=p["muted"])

        if self._no_score:
            c.create_text(28, base_y + 32, anchor="nw", fill=p["muted"], font=(F, 9),
                          text=f"Студентов без итогового балла (не показаны): {self._no_score}")

        c.create_line(left, base_y, w - right, base_y, fill=p["muted"])