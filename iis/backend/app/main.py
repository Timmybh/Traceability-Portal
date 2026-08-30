from __future__ import annotations

from contextlib import asynccontextmanager
import json
from typing import Literal
from urllib.parse import urlparse

import httpx
import pyodbc
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from .config import get_settings
from .database import connection_string, query_rows


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    try:
        with pyodbc.connect(connection_string(settings)) as connection:
            connection.cursor().execute("SELECT 1")
    except pyodbc.Error:
        # Service vẫn khởi động để /health báo trạng thái thay vì crash-loop.
        pass
    yield


app = FastAPI(title="Web Truy suất API", version="1.0.0", lifespan=lifespan)


def _validate_rfid(rfid: str) -> str:
    value = rfid.strip()
    if not value or len(value) > 100:
        raise HTTPException(status_code=400, detail="Mã RFID không hợp lệ")
    return value


def _validate_lookup(value: str, label: str, max_length: int) -> str:
    exact_value = value.strip()
    if not exact_value:
        raise HTTPException(status_code=400, detail=f"{label} không được để trống")
    if len(exact_value) > max_length:
        raise HTTPException(status_code=400, detail=f"{label} không hợp lệ")
    return exact_value


def _parse_nested_json(result: dict, source_key: str, target_key: str) -> dict:
    nested_json = result.pop(source_key, None)
    if nested_json:
        try:
            result[target_key] = json.loads(str(nested_json))
        except (TypeError, ValueError, json.JSONDecodeError):
            result[target_key] = []
    else:
        result[target_key] = []
    return result


def _database_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail="Không thể đọc dữ liệu SQL Server")


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    try:
        with pyodbc.connect(connection_string(settings)) as connection:
            connection.cursor().execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except pyodbc.Error:
        return {"status": "degraded", "database": "unavailable"}


@app.get("/api/traceability")
def traceability(rfid: str = Query(..., min_length=1, max_length=100)):
    settings = get_settings()
    value = _validate_rfid(rfid)
    try:
        rows = query_rows(settings, settings.sqlquery, {"RFID": value})
    except (pyodbc.Error, ValueError) as exc:
        raise _database_error(exc) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Không tìm thấy RFID")
    result = rows[0]
    timeline_json = result.pop("TimelineJson", None)
    if timeline_json:
        try:
            result["Timeline"] = json.loads(str(timeline_json))
        except (TypeError, ValueError, json.JSONDecodeError):
            result["Timeline"] = []
    else:
        result["Timeline"] = []
    return result


@app.get("/api/traceability/po")
def traceability_po(
    customer_code: str = Query(..., min_length=1, max_length=50),
    po: str = Query(..., min_length=1, max_length=250),
):
    settings = get_settings()
    customer_value = _validate_lookup(customer_code, "Khách hàng", 50)
    po_value = _validate_lookup(po, "PO", 250)
    try:
        rows = query_rows(
            settings,
            settings.sqlquery_po,
            {"CustomerCode": customer_value, "PO": po_value},
        )
    except (pyodbc.Error, ValueError) as exc:
        raise _database_error(exc) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Không tìm thấy PO của khách hàng")
    return _parse_nested_json(rows[0], "ProductsJson", "Products")


@app.get("/api/traceability/lot")
def traceability_lot(
    customer_code: str = Query(..., min_length=1, max_length=50),
    lot: str = Query(..., min_length=1, max_length=250),
):
    settings = get_settings()
    customer_value = _validate_lookup(customer_code, "Khách hàng", 50)
    lot_value = _validate_lookup(lot, "LOT", 250)
    try:
        rows = query_rows(
            settings,
            settings.sqlquery_lot,
            {"CustomerCode": customer_value, "LOT": lot_value},
        )
    except (pyodbc.Error, ValueError) as exc:
        raise _database_error(exc) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Không tìm thấy LOT của khách hàng")
    return _parse_nested_json(rows[0], "LotsJson", "Lots")


def _image_url_for_side(rows: list[dict], side: Literal["front", "back"]) -> str:
    suffix = "MT.JPG" if side == "front" else "MS.JPG"
    for row in rows:
        url = str(row.get("Url") or row.get("URL") or "").strip()
        if url.upper().endswith(suffix):
            return url
    raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")


def _validate_internal_url(url: str, allowed_host: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != allowed_host.lower():
        raise HTTPException(status_code=502, detail="Địa chỉ ảnh không được phép")


@app.get("/api/traceability/images")
def image_metadata(rfid: str = Query(..., min_length=1, max_length=100)):
    settings = get_settings()
    value = _validate_rfid(rfid)
    try:
        rows = query_rows(settings, settings.sqlquery_image, {"RFID": value})
    except (pyodbc.Error, ValueError) as exc:
        raise _database_error(exc) from exc
    available = {"front": False, "back": False}
    for row in rows:
        url = str(row.get("Url") or row.get("URL") or "").upper()
        available["front"] = available["front"] or url.endswith("MT.JPG")
        available["back"] = available["back"] or url.endswith("MS.JPG")
    return available


@app.get("/api/traceability/image")
def product_image(
    rfid: str = Query(..., min_length=1, max_length=100),
    side: Literal["front", "back"] = "front",
):
    settings = get_settings()
    value = _validate_rfid(rfid)
    client: httpx.Client | None = None
    upstream: httpx.Response | None = None
    try:
        rows = query_rows(settings, settings.sqlquery_image, {"RFID": value})
        url = _image_url_for_side(rows, side)
        _validate_internal_url(url, settings.image_allowed_host)
        client = httpx.Client(timeout=settings.image_timeout_seconds, follow_redirects=False)
        upstream = client.send(client.build_request("GET", url), stream=True)
        upstream.raise_for_status()
    except HTTPException:
        raise
    except (pyodbc.Error, ValueError) as exc:
        raise _database_error(exc) from exc
    except httpx.HTTPError as exc:
        if upstream is not None:
            upstream.close()
        if client is not None:
            client.close()
        raise HTTPException(status_code=502, detail="Không tải được ảnh nội bộ") from exc

    assert client is not None and upstream is not None

    headers = {
        "Cache-Control": f"public, max-age={settings.image_cache_seconds}",
        "X-Content-Type-Options": "nosniff",
    }
    content_type = upstream.headers.get("content-type", "image/jpeg")

    def stream_content():
        try:
            yield from upstream.iter_bytes()
        finally:
            upstream.close()
            client.close()

    return StreamingResponse(stream_content(), media_type=content_type, headers=headers)
