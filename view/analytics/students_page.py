import os
import tkinter as tk
from datetime import date as date_cls
from tkinter import ttk, messagebox, filedialog

from tkcalendar import DateEntry

from config import FONT_FAMILY, LOW_SCORE_THRESHOLD, HIGH_ABSENCES_THRESHOLD
from database import repository
from styles import configure_tree_tags
from utils.dates import iso_to_display, iso_to_date, date_to_iso
from view.tabs import build_tabs


def fmt_number(value, empty="—"):
    """7.5 -> '7.5', 8.0 -> '8', None -> '—'."""
    return empty if value is None else f"{value:g}"


def initials(fio):
    parts = [w for w in fio.split() if w]
    return "".join(w[0] for w in parts[:2]).upper() or "?"


class StudentsPage:
    SEARCH_DELAY_MS = 250  # задержка перед поиском, чтобы не запрашивать БД на каждую букву

    # столбец таблицы -> столбец/алиас БД
    SORTABLE = {"fio": "fio", "score": "itog_ball", "missed": "missed"}
    HEADINGS = {"id": "№", "fio": "ФИО", "score": "Итоговый балл", "missed": "Пропущено занятий"}

    def __init__(self, main_frame, app, filepath):
        self.main_frame = main_frame
        self.app = app
        self.filepath = filepath

        self.search_var = tk.StringVar()
        self.sort_var = tk.StringVar(value="Без сортировки")
        self.sort_column = None  # столбец БД
        self.sort_dir = "ASC"
        self.current_rows = []
        self._search_job = None
        self._legend_swatches = []  # (виджет, ключ цвета в палитре, ключ цвета рамки)

        # Пороги подсветки: редактируются пользователем, начальные значения — из config
        self.low_score = float(LOW_SCORE_THRESHOLD)
        self.high_absences = float(HIGH_ABSENCES_THRESHOLD)
        self.low_score_var = tk.StringVar(value=fmt_number(self.low_score))
        self.high_absences_var = tk.StringVar(value=fmt_number(self.high_absences))
        self._threshold_job = None

        self.create_widgets()
        self.refresh_table()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------

    def create_widgets(self):
        # --- Шапка ---
        header_frame = ttk.Frame(self.main_frame, style="Header.TFrame")
        header_frame.pack(fill="x", side="top")

        ttk.Button(header_frame, text="←  Назад", cursor="hand2", style="HeaderGhost.TButton",
                   command=self.back_to_main_menu).pack(side="left", padx=(14, 0), pady=10)
        build_tabs(header_frame, self.app, "students_page", self.filepath).pack(side="left", padx=16)
        self.theme_btn = ttk.Button(header_frame, text=self.app.theme_icon, width=3,
                                    cursor="hand2", style="HeaderGhost.TButton",
                                    command=self.app.toggle_theme)
        self.theme_btn.pack(side="right", padx=14)
        ttk.Frame(self.main_frame, style="Line.TFrame", height=1).pack(fill="x", side="top")

        ttk.Label(self.main_frame, text=f"Файл: {os.path.basename(self.filepath)}",
                  style="Hint.TLabel").pack(side="bottom", pady=8)

        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(18, 4))

        self._build_left_panel(content_frame)
        self._build_table(content_frame)

    @staticmethod
    def _card(parent, title, pady=(0, 14)):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(fill="x", pady=pady)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        return card

    def _build_left_panel(self, parent):
        panel = ttk.Frame(parent, width=290)
        panel.pack(side="left", fill="y", padx=(0, 18), anchor="n")
        panel.pack_propagate(False)

        # --- Поиск ---
        search = self._card(panel, "Поиск")
        self.search_entry = ttk.Entry(search, textvariable=self.search_var)
        self.search_entry.pack(fill="x")
        self.search_var.trace_add("write", self.on_search_changed)

        # --- Статистика плитками 2 колонки ---
        stats = self._card(panel, "Общая информация")
        grid = ttk.Frame(stats, style="Surface.TFrame")
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="tiles")
        self.total_students_label = self._tile(grid, 0, 0, "Всего студентов")
        self.shown_label = self._tile(grid, 0, 1, "Показано")
        self.avg_score_label = self._tile(grid, 1, 0, "Средний балл")
        self.avg_absences_label = self._tile(grid, 1, 1, "Среднее пропусков")
        # «Осталось занятий» — одно число на весь курс (не по каждому студенту),
        # поэтому вынесено сюда, а не в столбец таблицы
        self.remaining_label = self._tile(grid, 2, 0, "Осталось занятий")
        self.total_lessons_label = self._tile(grid, 2, 1, "Всего занятий")

        # --- Легенда ---
        legend = self._card(panel, "Подсветка")
        for bg_key, fg_key, text, var in (
                ("low_bg", "low_fg", "балл ниже", self.low_score_var),
                ("warn_bg", "warn_fg", "пропусков больше", self.high_absences_var)):
            row = ttk.Frame(legend, style="Surface.TFrame")
            row.pack(fill="x", pady=3)
            swatch = tk.Frame(row, width=16, height=16, highlightthickness=1)
            swatch.pack(side="left", padx=(0, 10))
            self._legend_swatches.append((swatch, bg_key, fg_key))
            ttk.Label(row, text=text, style="CardHint.TLabel").pack(side="left")
            count_label = ttk.Label(row, text="0", style="CardTitle.TLabel", width=4, anchor="e")
            count_label.pack(side="right")
            entry = ttk.Entry(row, textvariable=var, width=6, justify="center")
            entry.pack(side="right", padx=(0, 6))
            var.trace_add("write", self.on_threshold_changed)
            if bg_key == "low_bg":
                self.low_count_label = count_label
            else:
                self.warn_count_label = count_label
        ttk.Label(legend, text="Справа — сколько студентов подсвечено среди показанных. "
                               "Пороги можно менять (например, 7.5)",
                  style="CardHint.TLabel", wraplength=240, justify="left").pack(anchor="w", pady=(6, 0))
        self._recolor_legend()

        self.moreinfo_btn = ttk.Button(panel, text="Подробнее", cursor="hand2",
                                       style="MainButton.TButton", state=tk.DISABLED,
                                       command=self.open_student_window)
        self.moreinfo_btn.pack(pady=(4, 0), fill="x")

    @staticmethod
    def _tile(parent, row, col, caption):
        tile = ttk.Frame(parent, style="Surface.TFrame")
        tile.grid(row=row, column=col, sticky="w", pady=6)
        value = ttk.Label(tile, text="—", style="Value.TLabel")
        value.pack(anchor="w")
        ttk.Label(tile, text=caption, style="CardHint.TLabel").pack(anchor="w")
        return value

    def _build_table(self, parent):
        # Карточка с рамкой; внутри таблица и тонкая полоса прокрутки
        table_card = ttk.Frame(parent, style="Card.TFrame", padding=1)
        table_card.pack(side="right", fill="both", expand=True)

        columns = ("id", "fio", "score", "missed")
        self.student_table = ttk.Treeview(table_card, columns=columns, show="headings",
                                          selectmode="browse")
        scrollbar = ttk.Scrollbar(table_card, orient="vertical", command=self.student_table.yview)
        self.student_table.configure(yscrollcommand=scrollbar.set)

        # (ширина, выравнивание, растягивается ли при изменении окна)
        layout = {"id": (60, "center", False), "fio": (300, "w", True),
                  "score": (140, "center", False), "missed": (200, "center", False)}
        for col in columns:
            width, anchor, stretch = layout[col]
            self.student_table.heading(col, text=self.HEADINGS[col], anchor=anchor)
            if col in self.SORTABLE:
                # команду задаём отдельно: command=None в новых версиях Python вызывает TclError
                self.student_table.heading(col, command=lambda c=col: self.on_heading_click(c))
            self.student_table.column(col, width=width, anchor=anchor, stretch=stretch)

        configure_tree_tags(self.student_table, self.app.palette)

        scrollbar.pack(side="right", fill="y")
        self.student_table.pack(side="left", fill="both", expand=True)

        # Заглушка, когда поиск ничего не нашёл
        self.empty_label = ttk.Label(table_card, text="Ничего не найдено", style="CardHint.TLabel",
                                     font=(FONT_FAMILY, 12))

        self.student_table.bind("<Double-1>", self.open_student_window)
        self.student_table.bind("<Return>", self.open_student_window)
        self.student_table.bind("<<TreeviewSelect>>", self.on_table_select)

    # ------------------------------------------------------------------
    # Тема
    # ------------------------------------------------------------------

    def _recolor_legend(self):
        p = self.app.palette
        for swatch, bg_key, fg_key in self._legend_swatches:
            swatch.configure(bg=p[bg_key], highlightbackground=p[fg_key])

    def on_theme_changed(self):
        configure_tree_tags(self.student_table, self.app.palette)
        self._recolor_legend()
        self.theme_btn.config(text=self.app.theme_icon)

    # ------------------------------------------------------------------
    # Поиск, сортировка, таблица
    # ------------------------------------------------------------------

    def on_search_changed(self, *_):
        if self._search_job:
            self.main_frame.after_cancel(self._search_job)
        self._search_job = self.main_frame.after(self.SEARCH_DELAY_MS, self.refresh_table)

    def on_threshold_changed(self, *_):
        if self._threshold_job:
            self.main_frame.after_cancel(self._threshold_job)
        self._threshold_job = self.main_frame.after(400, self.apply_thresholds)

    def apply_thresholds(self):
        """Применяет введённые пороги; некорректный ввод игнорируется (остаётся прежнее значение)."""
        self._threshold_job = None
        changed = False
        for var, attr in ((self.low_score_var, "low_score"),
                          (self.high_absences_var, "high_absences")):
            try:
                value = float(var.get().strip().replace(",", "."))
            except ValueError:
                continue
            if value != getattr(self, attr):
                setattr(self, attr, value)
                changed = True
        if changed:
            self.refresh_table()

    def on_sort_selected(self, _event=None):
        option = repository.SORT_OPTIONS.get(self.sort_var.get())
        self.sort_column, self.sort_dir = option if option else (None, "ASC")
        self.refresh_table()

    def on_heading_click(self, table_column):
        db_column = self.SORTABLE[table_column]
        if self.sort_column == db_column:
            self.sort_dir = "DESC" if self.sort_dir == "ASC" else "ASC"
        else:
            self.sort_column, self.sort_dir = db_column, "ASC"
        self.sort_var.set("Без сортировки")  # сортировка теперь задаётся заголовком
        self.refresh_table()

    def _update_heading_arrows(self):
        for table_column, db_column in self.SORTABLE.items():
            arrow = ""
            if self.sort_column == db_column:
                arrow = " ▲" if self.sort_dir == "ASC" else " ▼"
            self.student_table.heading(table_column, text=self.HEADINGS[table_column] + arrow)

    def refresh_table(self, *_):
        self._search_job = None
        try:
            rows = repository.get_students(self.search_var.get(), self.sort_var.get(),
                                           self.sort_column, self.sort_dir)
            stats = repository.get_stats()
            overview = repository.get_lesson_overview()
        except Exception as e:
            messagebox.showerror("Ошибка базы данных", f"Не удалось получить данные:\n{e}")
            return

        self.current_rows = rows
        self.student_table.delete(*self.student_table.get_children())
        for index, row in enumerate(rows):
            # Один тег на строку: подсветка проблем важнее чередования
            if row["itog_ball"] is not None and row["itog_ball"] < self.low_score:
                tag = "low_score"
            elif row["missed"] is not None and row["missed"] > self.high_absences:
                tag = "many_absences"
            else:
                tag = "even" if index % 2 else "odd"
            self.student_table.insert(
                "", "end", iid=str(row["id"]), tags=(tag,),
                values=(row["id"], row["fio"], fmt_number(row["itog_ball"]),
                        fmt_number(row["missed"])))

        low_count = sum(1 for r in rows
                        if r["itog_ball"] is not None and r["itog_ball"] < self.low_score)
        warn_count = sum(1 for r in rows
                         if r["missed"] is not None and r["missed"] > self.high_absences)
        self.low_count_label.config(text=str(low_count))
        self.warn_count_label.config(text=str(warn_count))

        if rows:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

        self._update_heading_arrows()
        self.on_table_select()

        self.total_students_label.config(text=str(stats.total))
        self.shown_label.config(text=str(len(rows)))
        self.avg_score_label.config(text=fmt_number(round(stats.avg_score, 2) if stats.avg_score is not None else None))
        self.avg_absences_label.config(
            text=fmt_number(round(stats.avg_missed, 2) if stats.avg_missed is not None else None))
        self.remaining_label.config(text=str(overview["remaining"]))
        self.total_lessons_label.config(text=str(overview["total"]))

    def on_table_select(self, _event=None):
        state = tk.NORMAL if self.student_table.selection() else tk.DISABLED
        self.moreinfo_btn.config(state=state)

    # ------------------------------------------------------------------
    # Действия
    # ------------------------------------------------------------------

    def back_to_main_menu(self):
        if messagebox.askyesno("Внимание!", "Вы уверены, что хотите выйти в главное меню?"):
            self.app.show_window("main_menu")

    def open_student_window(self, _event=None):
        selection = self.student_table.selection()
        if selection:
            self.create_moreinfo_window(int(selection[0]))

    # ------------------------------------------------------------------
    # Окно «Подробнее»
    # ------------------------------------------------------------------

    def create_moreinfo_window(self, student_id):
        student = repository.get_student(student_id)
        if student is None:
            messagebox.showerror("Ошибка", "Студент не найден в базе данных.")
            return

        p = self.app.palette
        win = tk.Toplevel(self.main_frame)
        win.title(f"Подробная информация ({student['fio']})")
        height = min(720, win.winfo_screenheight() - 80)  # не вылезаем за экран ноутбука
        win.geometry(f"940x{height}")
        win.configure(background=p["bg"])
        win.transient(self.main_frame.winfo_toplevel())
        win.grab_set()
        win.bind("<Escape>", lambda _e: win.destroy())

        container = ttk.Frame(win, padding=20)
        container.pack(fill="both", expand=True)

        # --- Карточка студента: аватар, ФИО, место, ключевые цифры ---
        rank = repository.get_rank(student_id)
        total = repository.get_stats().total
        place = f"{rank} из {total}" if rank else "нет итогового балла"

        top = ttk.Frame(container, style="Card.TFrame", padding=18)
        top.pack(fill="x", pady=(0, 12))
        top.columnconfigure(1, weight=1)

        avatar = tk.Canvas(top, width=60, height=60, bg=p["surface"], bd=0, highlightthickness=0)
        avatar.create_oval(2, 2, 58, 58, fill=p["accent"], outline="")
        avatar.create_text(30, 30, text=initials(student["fio"]), fill=p["on_accent"],
                           font=(FONT_FAMILY, 16, "bold"))
        avatar.grid(row=0, column=0, rowspan=2, padx=(0, 16))

        ttk.Label(top, text=student["fio"], style="Name.TLabel").grid(row=0, column=1, sticky="sw")
        ttk.Label(top, text=f"Место в группе: {place}",
                  style="Subtitle.TLabel").grid(row=1, column=1, sticky="nw")

        score_tile = ttk.Frame(top, style="Surface.TFrame")
        score_tile.grid(row=0, column=2, rowspan=2, padx=(28, 0))
        ttk.Label(score_tile, text=fmt_number(student["itog_ball"]), style="Value.TLabel").pack()
        ttk.Label(score_tile, text="Итоговый балл", style="CardHint.TLabel").pack()

        missed_tile = ttk.Frame(top, style="Surface.TFrame")
        missed_tile.grid(row=0, column=3, rowspan=2, padx=(28, 0))
        missed_value = ttk.Label(missed_tile, text="—", style="Value.TLabel")
        missed_value.pack()
        ttk.Label(missed_tile, text="Пропущено занятий", style="CardHint.TLabel").pack()

        # --- Дата, до которой учитываем занятия (выбирается календарём) ---
        last_date = repository.get_last_graded_date()
        initial_date = iso_to_date(last_date) or date_cls.today()

        date_row = ttk.Frame(container)
        date_row.pack(fill="x", pady=(0, 12))
        ttk.Label(date_row, text="Учитывать занятия до:").pack(side="left")

        calendar_colors = dict(
            background=p["accent"], foreground=p["on_accent"],
            headersbackground=p["accent"], headersforeground=p["on_accent"],
            normalbackground=p["surface"], normalforeground=p["text"],
            weekendbackground=p["surface"], weekendforeground=p["text"],
            selectbackground=p["accent"], selectforeground=p["on_accent"],
            othermonthbackground=p["surface_alt"], othermonthforeground=p["muted"],
            othermonthwebackground=p["surface_alt"], othermonthweforeground=p["muted"],
            disabledbackground=p["disabled_bg"], disabledforeground=p["disabled_fg"],
            bordercolor=p["border"])
        # Разные версии tkcalendar/системная локаль иногда не принимают часть параметров —
        # пробуем от самого полного варианта к самому простому, лишь бы календарь открылся.
        date_picker = None
        for kwargs in (dict(locale="ru_RU", **calendar_colors), calendar_colors, {}):
            try:
                date_picker = DateEntry(date_row, width=11, date_pattern="dd.mm.yyyy", **kwargs)
                break
            except Exception:
                continue
        date_picker.set_date(initial_date)
        date_picker.pack(side="left", padx=10)
        ttk.Label(date_row, text="по умолчанию — дата последнего оценённого занятия",
                  style="Hint.TLabel").pack(side="left", padx=12)

        # --- Таблица пропущенных занятий ---
        lessons_card, lessons_title = self._table_card(container, "Пропущенные занятия")
        lessons_table = self._build_activity_table(
            lessons_card, (("date", "Дата", 100, "center"), ("name", "Занятие", 110, "center"),
                           ("topic", "Тема", 600, "w")), height=12)

        def fill(_event=None):
            try:
                up_to = date_to_iso(date_picker.get_date())
            except Exception:
                messagebox.showerror("Неверная дата", "Выберите дату в календаре.", parent=win)
                return
            lessons = repository.get_missed_lessons(student_id, up_to)

            lessons_table.delete(*lessons_table.get_children())
            for i, r in enumerate(lessons):
                name = f"Урок {r['nazvanie']}" if r["nazvanie"].isdigit() else r["nazvanie"]
                lessons_table.insert("", "end", tags=("even" if i % 2 else "odd",),
                                     values=(iso_to_display(r["data"]), name, r["tema"] or ""))
            lessons_title.config(text=f"Пропущенные занятия ({len(lessons)})")
            missed_value.config(text=str(len(lessons)))

        date_picker.bind("<<DateEntrySelected>>", fill)
        date_picker.bind("<Return>", fill)
        date_picker.bind("<FocusOut>", fill)

        ttk.Button(container, text="Закрыть", style="Secondary.TButton", cursor="hand2",
                   command=win.destroy).pack(pady=(14, 0), anchor="e")
        fill()

    @staticmethod
    def _table_card(parent, title):
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill="both", expand=True, pady=(0, 12))
        title_label = ttk.Label(card, text=title, style="CardTitle.TLabel")
        title_label.pack(anchor="w", pady=(0, 8))
        return card, title_label

    def _build_activity_table(self, parent, columns, height=5):
        frame = ttk.Frame(parent, style="Surface.TFrame")
        frame.pack(fill="both", expand=True)
        ids = [c[0] for c in columns]
        table = ttk.Treeview(frame, columns=ids, show="headings", height=height)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        for col_id, title, width, anchor in columns:
            table.heading(col_id, text=title, anchor=anchor)
            table.column(col_id, width=width, anchor=anchor)
        configure_tree_tags(table, self.app.palette)
        scroll.pack(side="right", fill="y")
        table.pack(side="left", fill="both", expand=True)
        return table