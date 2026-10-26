import sqlite3
from contextlib import contextmanager

from config import DB_PATH


def db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Открывает соединение с БД. Ошибки не скрываются — их обработает вызывающий код."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session(db_path: str = DB_PATH):
    """Контекстный менеджер: соединение гарантированно закрывается даже при ошибке."""
    conn = db_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()