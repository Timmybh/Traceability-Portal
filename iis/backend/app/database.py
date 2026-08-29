from collections.abc import Sequence
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


def _parameterize(query: str, rfid: str) -> tuple[str, Sequence[str]]:
    count = len(re.findall(r"@RFID\b", query, flags=re.IGNORECASE))
    if count == 0:
        raise ValueError("SQL query phải chứa tham số @RFID")
    prepared = re.sub(r"@RFID\b", "?", query, flags=re.IGNORECASE)
    return prepared, tuple(rfid for _ in range(count))


def query_rows(settings: Settings, query: str, rfid: str) -> list[dict[str, Any]]:
    prepared, params = _parameterize(query, rfid)
    with pyodbc.connect(connection_string(settings)) as connection:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cursor.execute(prepared, *params)
        columns = [column[0] for column in cursor.description or []]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
