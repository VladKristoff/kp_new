"""Все SQL-запросы приложения в одном месте. UI работает только с этими функциями."""
from dataclasses import dataclass
from typing import Optional

from database.database_manager import db_session

SORT_OPTIONS = {
    "Без сортировки": None,
    "Баллы (по возрастанию)": ("itog_ball", "ASC"),
    "Баллы (по убыванию)": ("itog_ball", "DESC"),
    "Пропуски (по возрастанию)": ("kol_propuskov", "ASC"),
    "Пропуски (по убыванию)": ("kol_propuskov", "DESC"),
}

# Типы активностей, пустая оценка за которые означает «пропустил занятие»
LESSON_TYPES = ("Урок",)


@dataclass
class Stats:
    total: int
    avg_score: Optional[float]
    avg_absences: Optional[float]


def database_has_data() -> bool:
    try:
        with db_session() as conn:
            return conn.execute("SELECT COUNT(*) FROM Students").fetchone()[0] > 0
    except Exception:
        return False


def get_students(search: str = "", sort_key: str = "Без сортировки", sort_column: str = None,
                 sort_dir: str = "ASC") -> list:
    """
    Список студентов. Поиск регистронезависимый и для кириллицы
    (SQLite NOCASE работает только с латиницей, поэтому фильтруем в Python).
    Пустые значения всегда уходят в конец списка.
    """
    if sort_column is None and SORT_OPTIONS.get(sort_key):
        sort_column, sort_dir = SORT_OPTIONS[sort_key]

    query = "SELECT id, fio, itog_ball, kol_propuskov FROM Students"
    if sort_column in ("itog_ball", "kol_propuskov", "fio"):
        direction = "DESC" if sort_dir == "DESC" else "ASC"
        query += f" ORDER BY {sort_column} IS NULL, {sort_column} {direction}"
    else:
        query += " ORDER BY id"

    with db_session() as conn:
        rows = conn.execute(query).fetchall()

    needle = search.strip().casefold()
    if needle:
        rows = [r for r in rows if needle in (r["fio"] or "").casefold()]
    return rows


def get_stats() -> Stats:
    with db_session() as conn:
        total, avg_score, avg_abs = conn.execute(
            "SELECT COUNT(*), AVG(itog_ball), AVG(kol_propuskov) FROM Students"
        ).fetchone()
    return Stats(total or 0, avg_score, avg_abs)


def get_student(student_id: int):
    with db_session() as conn:
        return conn.execute(
            "SELECT id, fio, itog_ball, kol_propuskov FROM Students WHERE id = ?", (student_id,)
        ).fetchone()


def get_rank(student_id: int) -> Optional[int]:
    """Место в группе. Студенты с одинаковым баллом делят место."""
    with db_session() as conn:
        row = conn.execute("SELECT itog_ball FROM Students WHERE id = ?", (student_id,)).fetchone()
        if row is None or row["itog_ball"] is None:
            return None
        better = conn.execute(
            "SELECT COUNT(*) FROM Students WHERE itog_ball > ?", (row["itog_ball"],)
        ).fetchone()[0]
    return better + 1


def get_last_graded_date() -> str:
    """
    Дата последнего урока, по которому хоть у кого-то выставлена оценка (ISO).
    Всё, что позже, считается «ещё не проведённым», а не пропущенным.
    Итоговые столбцы («оценка 1») не учитываем: они заполнены формулами наперёд.
    """
    with db_session() as conn:
        row = conn.execute("""
            SELECT MAX(a.data) FROM Activities a
            JOIN Grades g ON g.activity_id = a.id
            WHERE g.poluchenny_ball IS NOT NULL AND a.data != '' AND a.tip IN ('Урок')
        """).fetchone()
    return row[0] or ""


def get_empty_activities(student_id: int, up_to_iso: str) -> list:
    """Активности до указанной даты, по которым у студента нет оценки."""
    with db_session() as conn:
        return conn.execute("""
            SELECT a.data, a.nazvanie, a.tema, a.tip
            FROM Activities a
            LEFT JOIN Grades g ON g.activity_id = a.id AND g.student_id = ?
            WHERE g.poluchenny_ball IS NULL AND g.raw_value IS NULL
              AND a.data != '' AND a.data <= ?
            ORDER BY a.data, a.id
        """, (student_id, up_to_iso)).fetchall()


def get_score_distribution(bin_size: float = 1.0) -> list:
    """[(начало_интервала, количество)] — для будущих графиков."""
    with db_session() as conn:
        scores = [r[0] for r in conn.execute(
            "SELECT itog_ball FROM Students WHERE itog_ball IS NOT NULL")]
    if not scores:
        return []
    start = int(min(scores) // bin_size * bin_size)
    result = {}
    for s in scores:
        b = int(s // bin_size * bin_size)
        result[b] = result.get(b, 0) + 1
    return [(b, result.get(b, 0)) for b in range(start, int(max(scores)) + 1, int(bin_size))]

TYPE_ORDER = ["Урок", "ПР", "ЛР", "ДЗ", "Зачет"]


def get_avg_by_type() -> list:
    """
    Средний полученный балл по каждому типу работ — для диаграммы.
    Учитываются только выставленные оценки (пустые ячейки не считаются нулём).
    Возвращает список словарей: tip, avg, max_ball, count — в привычном порядке типов.
    """
    with db_session() as conn:
        rows = conn.execute("""
            SELECT a.tip, AVG(g.poluchenny_ball), MAX(a.max_ball), COUNT(g.poluchenny_ball)
            FROM Activities a
            JOIN Grades g ON g.activity_id = a.id
            WHERE g.poluchenny_ball IS NOT NULL
            GROUP BY a.tip
        """).fetchall()

    data = [{"tip": r[0], "avg": r[1], "max_ball": r[2], "count": r[3]} for r in rows]
    data.sort(key=lambda d: TYPE_ORDER.index(d["tip"]) if d["tip"] in TYPE_ORDER else len(TYPE_ORDER))
    return data