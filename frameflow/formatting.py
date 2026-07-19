import sqlite3
from datetime import date
from typing import Any


def money(value: float) -> str:
    return f"${value:,.2f}"


def phone_digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def format_us_phone(value: Any) -> str:
    raw = str(value or "").strip()
    digits = phone_digits(raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw


def is_valid_us_phone(value: Any) -> bool:
    digits = phone_digits(value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return len(digits) == 10


def today_iso() -> str:
    return date.today().isoformat()


def date_from_iso(value: str | None, fallback: date | None = None) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return fallback or date.today()


def display_date(value: str | None) -> str:
    if not value:
        return "Not set"
    try:
        return date.fromisoformat(value).strftime("%b %d, %Y")
    except ValueError:
        return value


def row_value(
    row: sqlite3.Row | dict[str, Any] | None,
    key: str,
    default: Any = "",
) -> Any:
    if row is None:
        return default
    keys = row.keys() if hasattr(row, "keys") else []
    if key not in keys:
        return default
    value = row[key]
    return default if value is None else value

