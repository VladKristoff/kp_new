import re
from datetime import date, datetime
from typing import Optional

_DOT_RE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?")


def to_iso(value, default_year: Optional[int] = None) -> str:
    """
    Приводит значение ячейки к строке 'YYYY-MM-DD'. Если дату распознать нельзя — ''.

    Поддерживаются: datetime/date, '2025-09-05', '05.09.2025',
    '12.10/15.1' (берётся первая дата; год — default_year).
    """
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text[:10]

    match = _DOT_RE.match(text.split("/")[0])
    if match and default_year:
        day, month = int(match.group(1)), int(match.group(2))
        year = match.group(3)
        year = int(year) + (2000 if year and len(year) == 2 else 0) if year else default_year
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return ""
    return ""


def iso_to_display(iso: str) -> str:
    """'2025-09-05' -> '05.09.2025' для показа пользователю."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso or ""


def display_to_iso(text: str) -> str:
    """'05.09.2025' -> '2025-09-05'. Бросает ValueError при неверном формате."""
    return datetime.strptime(text.strip(), "%d.%m.%Y").date().isoformat()
