import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from PIL import Image, ImageTk

from config import ICON_PATH
from database.repository import database_has_data
from utils.parser import UniversityParser, ParseError
from utils.settings import load_settings, save_setting


class MainMenu:
    def __init__(self, main_frame, app):
        self.main_frame = main_frame
        self.app = app
        self.result_queue = queue.Queue()
        self.is_loading = False

        self.create_widgets()

    def create_widgets(self):
        p = self.app.palette

        # Фон с мягкими декоративными кругами (перерисовывается при смене размера и темы)
        self.bg_canvas = tk.Canvas(self.main_frame, bg=p["bg"], bd=0, highlightthickness=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", lambda _e: self._draw_background())

        self.theme_btn = ttk.Button(self.main_frame, text=self.app.theme_icon, width=3,
                                    style="Ghost.TButton", cursor="hand2",
                                    command=self.app.toggle_theme)
        self.theme_btn.place(relx=1.0, x=-20, y=16, anchor="ne")

        # Центральная карточка
        card = ttk.Frame(self.main_frame, style="Card.TFrame", padding=(64, 44))
        card.place(relx=0.5, rely=0.5, anchor="center")

        try:
            pil_img = Image.open(ICON_PATH).resize((88, 88), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(pil_img)
            ttk.Label(card, image=self.logo_img, style="Card.TLabel").pack()
        except (OSError, FileNotFoundError):
            pass  # без логотипа меню остаётся рабочим

        ttk.Label(card, text="Work Tracking", style="BigLabel.TLabel").pack(pady=(12, 0))
        ttk.Label(card, text="Успеваемость студентов — наглядно",
                  style="Subtitle.TLabel").pack(pady=(2, 32))

        buttons = ttk.Frame(card, style="Surface.TFrame")
        buttons.pack()

        self.upload_btn = ttk.Button(buttons, text="Загрузить файл", cursor="hand2",
                                     command=self.open_analytics_page, style="BlueButton.TButton")
        self.upload_btn.pack(fill="x")

        # Если данные уже загружались, даём продолжить без повторной загрузки xlsx
        last_file = load_settings().get("last_file")
        if last_file and database_has_data():
            self.continue_btn = ttk.Button(buttons, text="Продолжить с последними данными",
                                           cursor="hand2", style="Secondary.TButton",
                                           command=lambda: self.app.show_window("students_page", last_file))
            self.continue_btn.pack(pady=(12, 0), fill="x")
            ttk.Label(buttons, text=os.path.basename(last_file),
                      style="CardHint.TLabel").pack(pady=(6, 0))

        # Сюда попадают индикатор и статус загрузки
        self.status_box = ttk.Frame(card, style="Surface.TFrame")
        self.status_box.pack(fill="x")
        self.progress = ttk.Progressbar(self.status_box, mode="indeterminate", length=320)
        self.status_label = ttk.Label(self.status_box, text="", style="CardHint.TLabel")

        ttk.Label(card, style="CardHint.TLabel", justify="center", wraplength=380,
                  text="Для начала работы загрузите файл с данными успеваемости.\n"
                       "Поддерживаемый формат: .xlsx").pack(pady=(28, 0))

    # ------------------------------------------------------------------
    # Оформление
    # ------------------------------------------------------------------

    def _draw_background(self):
        p = self.app.palette
        c = self.bg_canvas
        w, h = c.winfo_width(), c.winfo_height()
        c.delete("all")
        c.create_oval(-170, -170, 300, 300, fill=p["deco1"], outline="")
        c.create_oval(w - 330, h - 300, w + 170, h + 200, fill=p["deco2"], outline="")
        c.create_oval(w - 190, -90, w - 90, 10, fill=p["deco1"], outline="")
        c.create_oval(70, h - 120, 150, h - 40, fill=p["deco2"], outline="")

    def on_theme_changed(self):
        self.bg_canvas.configure(bg=self.app.palette["bg"])
        self._draw_background()
        self.theme_btn.config(text=self.app.theme_icon)

    # ------------------------------------------------------------------

    def open_analytics_page(self):
        if self.is_loading:
            return
        file_path = filedialog.askopenfilename(title="Выберите файл",
                                               filetypes=[("Excel файлы", "*.xlsx")])
        if not file_path:
            return

        if database_has_data() and not messagebox.askyesno(
                "Заменить данные?",
                "В программе уже есть загруженные данные.\n"
                "Они будут заменены данными из нового файла. Продолжить?"):
            return

        self.set_loading(True)
        # Парсинг в отдельном потоке, чтобы окно не зависало на больших файлах
        threading.Thread(target=self._parse_worker, args=(file_path,), daemon=True).start()
        self.main_frame.after(100, self._poll_result, file_path)

    def _parse_worker(self, file_path):
        try:
            parser = UniversityParser(excel_file=file_path, verbose=False)
            self.result_queue.put(("ok", parser.parse()))
        except ParseError as e:
            self.result_queue.put(("error", str(e)))
        except Exception as e:
            self.result_queue.put(("error", f"Непредвиденная ошибка: {e}"))

    def _poll_result(self, file_path):
        try:
            status, payload = self.result_queue.get_nowait()
        except queue.Empty:
            if self.main_frame.winfo_exists():
                self.main_frame.after(100, self._poll_result, file_path)
            return

        self.set_loading(False)
        if status == "error":
            messagebox.showerror("Не удалось загрузить файл", payload)
            return

        save_setting("last_file", file_path)
        warnings = payload.get("warnings", [])
        if warnings:
            shown = "\n• ".join(warnings[:8])
            extra = f"\n… и ещё {len(warnings) - 8}" if len(warnings) > 8 else ""
            messagebox.showwarning(
                "Файл загружен с замечаниями",
                f"Студентов: {payload['students']}, работ: {payload['activities']}.\n\n"
                f"Что стоит проверить в файле:\n• {shown}{extra}")
        self.app.show_window("students_page", file_path)

    def set_loading(self, loading: bool):
        self.is_loading = loading
        if loading:
            self.upload_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Обработка файла…")
            self.status_label.pack(pady=(14, 0))
            self.progress.pack(pady=(6, 0))
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.status_label.pack_forget()
            self.upload_btn.config(state=tk.NORMAL)