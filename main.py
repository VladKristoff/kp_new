import tkinter as tk

from app import AppWorkTracker
from view.main_menu import MainMenu
from view.analytics.students_page import StudentsPage

if __name__ == "__main__":
    root = tk.Tk()
    app = AppWorkTracker(root)

    app.register_page("main_menu", MainMenu)
    app.register_page("students_page", StudentsPage)

    app.show_window("main_menu")

    root.mainloop()
