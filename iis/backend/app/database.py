from collections.abc import Mapping, Sequence
import re
from typing import Any

import pyodbc

from .config import Settings


def _server_value(settings: Settings) -> str:
    host = settings.sqlserver_host.strip()
    if "\\" in host or not settings.sqlserver_port:
        return host
    return f"{host},{settings.sqlserver_port}"


def connection_string(settings: Settings) -> str:
    values = {
        "DRIVER": f"{{{settings.sqlserver_driver}}}",
        "SERVER": _server_value(settings),
        "DATABASE": settings.sqlserver_database,
        "UID": settings.sqlserver_user,
        "PWD": settings.sqlserver_password,
        "Encrypt": "yes" if settings.sqlserver_encrypt else "no",
        "TrustServerCertificate": (
            "yes" if settings.sqlserver_trust_server_certificate else "no"
        ),
        "Connection Timeout": str(settings.sqlserver_connection_timeout),
    }
    return ";".join(f"{key}={value}" for key, value in values.items()) + ";"


def _parameterize(
    query: str, parameters: Mapping[str, str]
) -> tuple[str, Sequence[str]]:
    normalized = {
        name.removeprefix("@").casefold(): value for name, value in parameters.items()
    }
    if not normalized:
        raise ValueError("SQL query phải có ít nhất một tham số")
    if any(not value.strip() for value in normalized.values()):
        raise ValueError("Giá trị tra cứu không được để trống")

    names = sorted((re.escape(name) for name in normalized), key=len, reverse=True)
    pattern = re.compile(r"@(" + "|".join(names) + r")\b", flags=re.IGNORECASE)
    values: list[str] = []
    matched: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1).casefold()
        matched.add(name)
        values.append(normalized[name])
        return "?"

    prepared = pattern.sub(replace, query)
    missing = sorted(set(normalized) - matched)
    if missing:
        raise ValueError(
            "SQL query thiếu tham số: " + ", ".join(f"@{name}" for name in missing)
        )
    return prepared, tuple(values)


def query_rows(
    settings: Settings, query: str, parameters: Mapping[str, str]
) -> list[dict[str, Any]]:
    prepared, params = _parameterize(query, parameters)
    with pyodbc.connect(connection_string(settings)) as connection:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cursor.execute(prepared, *params)
        columns = [column[0] for column in cursor.description or []]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
