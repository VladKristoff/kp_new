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

        # Реестр диаграмм: ключ -> (название в списке слева, метод отрисовки).
        # Чтобы добавить новую диаграмму, достаточно дописать сюда строку и метод draw_*.
        self.charts = {
            "students_scores": ("Баллы студентов", self.draw_students_scores),
            "avg_by_type": ("Средний балл по типам работ", self.draw_avg_by_type),
        }
        self.current_chart = "students_scores"
        self._chart_buttons = {}
        self.sort_var = tk.StringVar(value=self.SORT_VALUES[0])
        self.threshold = float(LOW_SCORE_THRESHOLD)

        self._students = []   # [(фио, балл)] — только студенты с итоговым баллом
        self._no_score = 0    # сколько студентов без итогового балла
        self._types = []

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

        # --- Выбор диаграммы ---
        card = ttk.Frame(panel, style="Card.TFrame", padding=16)
        card.pack(fill="x", pady=(0, 14))
        ttk.Label(card, text="Диаграммы", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        for key, (title, _draw) in self.charts.items():
            btn = ttk.Button(card, text=title, cursor="hand2",
                             command=lambda k=key: self.select_chart(k))
            btn.pack(fill="x", pady=2)
            self._chart_buttons[key] = btn
        self._update_chart_buttons()

        # --- Сортировка (для диаграммы по студентам) ---
        sort_card = ttk.Frame(panel, style="Card.TFrame", padding=16)
        sort_card.pack(fill="x", pady=(0, 14))
        ttk.Label(sort_card, text="Сортировка", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        combo = ttk.Combobox(sort_card, textvariable=self.sort_var, state="readonly",
                             values=self.SORT_VALUES)
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", lambda _e: self.draw())
        ttk.Label(sort_card, text="Действует для диаграммы «Баллы студентов»",
                  style="CardHint.TLabel", wraplength=240, justify="left").pack(anchor="w", pady=(8, 0))

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

    def _update_chart_buttons(self):
        for key, btn in self._chart_buttons.items():
            btn.config(style="ChartItemActive.TButton" if key == self.current_chart
                       else "ChartItem.TButton")

    # ------------------------------------------------------------------
    # Данные и действия
    # ------------------------------------------------------------------

    def load_data(self):
        try:
            rows = repository.get_students()
            self._types = repository.get_avg_by_type()
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

    def select_chart(self, key):
        self.current_chart = key
        self._update_chart_buttons()
        self.draw()

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
        self.charts[self.current_chart][1](c)

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

    def draw_avg_by_type(self, c):
        p, F = self.app.palette, FONT_FAMILY
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or h < 50:
            return

        self._title(c, "Средний балл по типам работ",
                    "Яркий столбец — средний полученный балл, бледный — максимум за работу")

        if not self._types:
            c.create_text(w / 2, h / 2, text="Нет данных для диаграммы", fill=p["muted"], font=(F, 12))
            return

        left, right, top, bottom = 64, 32, 100, 80
        plot_w, plot_h = w - left - right, h - top - bottom
        y_max = max(d["max_ball"] for d in self._types)
        base_y = top + plot_h

        ticks = 5
        for i in range(ticks + 1):
            value = y_max * i / ticks
            y = base_y - plot_h * i / ticks
            c.create_line(left, y, w - right, y, fill=p["border"])
            c.create_text(left - 10, y, anchor="e", text=f"{value:g}", fill=p["muted"], font=(F, 9))

        slot = plot_w / len(self._types)
        bar_w = min(96, slot * 0.5)
        for i, d in enumerate(self._types):
            cx = left + slot * (i + 0.5)
            x0, x1 = cx - bar_w / 2, cx + bar_w / 2
            max_y = base_y - plot_h * d["max_ball"] / y_max
            avg_y = base_y - plot_h * d["avg"] / y_max

            c.create_rectangle(x0, max_y, x1, base_y, fill=p["accent_soft"], outline="")
            c.create_rectangle(x0, avg_y, x1, base_y, fill=p["accent"], outline="")
            c.create_text(cx, avg_y - 8, anchor="s", text=fmt_number(d["avg"]),
                          fill=p["text"], font=(F, 11, "bold"))
            c.create_text(cx, base_y + 14, anchor="n", text=d["tip"], fill=p["text"], font=(F, 11, "bold"))
            c.create_text(cx, base_y + 34, anchor="n",
                          text=f"из {fmt_number(d['max_ball'])} · {d['count']} оценок",
                          fill=p["muted"], font=(F, 9))

        c.create_line(left, base_y, w - right, base_y, fill=p["muted"])