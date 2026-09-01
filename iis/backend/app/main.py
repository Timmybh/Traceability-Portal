from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
import mimetypes
from pathlib import Path
import re
from threading import Lock
from time import monotonic
from typing import Literal
from urllib.parse import quote, unquote, urlparse

import httpx
import pyodbc
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from .config import get_settings
from .database import connection_string, query_rows


logger = logging.getLogger(__name__)


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

_image_metadata_cache: dict[str, tuple[float, list[dict]]] = {}
_image_metadata_cache_lock = Lock()


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
    logger.exception("SQL Server query failed", exc_info=exc)
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


def _traceability_by_query(rfid: str, query: str | None, response: Response | None = None):
    value = _validate_rfid(rfid)
    if not query:
        raise HTTPException(status_code=503, detail="Câu truy vấn chưa được cấu hình")
    try:
        timings: dict[str, float] = {}
        rows = query_rows(get_settings(), query, {"RFID": value}, timings)
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
    if response is not None and timings:
        response.headers["Server-Timing"] = ", ".join(
            f"{name};dur={duration:.1f}"
            for name, duration in (
                ("sql-connect", timings["connect_ms"]),
                ("sql-execute", timings["query_ms"]),
                ("sql-fetch", timings["fetch_ms"]),
                ("database-total", timings["database_ms"]),
            )
        )
    return result


def _new_traceability_query() -> str | None:
    settings = get_settings()
    if not settings.sqlquery_new_file:
        return settings.sqlquery_new
    query_path = Path(settings.sqlquery_new_file)
    if not query_path.is_absolute():
        query_path = Path(__file__).resolve().parents[1] / query_path
    try:
        query = query_path.read_text(encoding="utf-8-sig")
    except OSError:
        return settings.sqlquery_new
    query = re.sub(
        r"DECLARE\s+@rffid\s+nvarchar\(255\)\s*=\s*N'[^']*'\s*;",
        "",
        query,
        count=1,
        flags=re.IGNORECASE,
    )
    return re.sub(r"@rffid\b", "@RFID", query, flags=re.IGNORECASE)


@app.get("/api/traceability")
def traceability(response: Response, rfid: str = Query(..., min_length=1, max_length=100)):
    return _traceability_by_query(rfid, get_settings().sqlquery, response)


@app.get("/api/traceability/new")
def traceability_new(response: Response, rfid: str = Query(..., min_length=1, max_length=100)):
    return _traceability_by_query(rfid, _new_traceability_query(), response)


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


def _image_rows(rfid: str) -> list[dict]:
    settings = get_settings()
    cache_key = rfid.casefold()
    now = monotonic()
    with _image_metadata_cache_lock:
        cached = _image_metadata_cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
        if cached:
            _image_metadata_cache.pop(cache_key, None)

    rows = query_rows(settings, settings.sqlquery_image, {"RFID": rfid})
    expires_at = now + settings.image_metadata_cache_seconds
    with _image_metadata_cache_lock:
        # Giữ cache có giới hạn cho tiến trình IIS chạy lâu ngày.
        if len(_image_metadata_cache) >= 1000:
            expired_keys = [key for key, item in _image_metadata_cache.items() if item[0] <= now]
            for key in expired_keys:
                _image_metadata_cache.pop(key, None)
            if len(_image_metadata_cache) >= 1000:
                _image_metadata_cache.pop(next(iter(_image_metadata_cache)))
        _image_metadata_cache[cache_key] = (expires_at, rows)
    return rows


def _validate_internal_url(url: str, allowed_host: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != allowed_host.lower():
        raise HTTPException(status_code=502, detail="Địa chỉ tệp nội bộ không được phép")


def _technical_document(document_id: int) -> dict:
    rows = query_rows(
        get_settings(),
        """
        SELECT TOP (1)
            Id,
            TenTaiLieu,
            LoaiFile,
            DuongDanURL,
            DuongDanLocal
        FROM dbo.TEC_ThongTinTaiLieukyThuat
        WHERE Id = @DocumentId
        """,
        {"DocumentId": str(document_id)},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu kỹ thuật")
    return rows[0]


def _technical_document_source(document: dict) -> str:
    source = str(document.get("DuongDanURL") or document.get("DuongDanLocal") or "").strip()
    if not source:
        raise HTTPException(status_code=404, detail="Tài liệu chưa có đường dẫn")
    return source


def _technical_document_url(source: str, base_url: str, allowed_host: str) -> str:
    if urlparse(source).scheme:
        url = source
    else:
        normalized = source.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if not parts or any(part in {".", ".."} or ":" in part for part in parts):
            raise HTTPException(status_code=400, detail="Đường dẫn tài liệu không hợp lệ")
        url = f"{base_url.rstrip('/')}/{'/'.join(quote(part) for part in parts)}"
    _validate_internal_url(url, allowed_host)
    return url


def _technical_document_filename(document: dict, url: str) -> str:
    path_name = Path(unquote(urlparse(url).path)).name
    name = str(document.get("TenTaiLieu") or "").strip() or path_name
    # Không cho ký tự điều khiển đi vào Content-Disposition.
    return re.sub(r"[\r\n\x00-\x1f\x7f]", "", name) or f"document-{document['Id']}"


@app.get("/api/traceability/document")
def technical_document(document_id: int = Query(..., alias="id", ge=1)):
    settings = get_settings()
    client: httpx.Client | None = None
    upstream: httpx.Response | None = None
    try:
        document = _technical_document(document_id)
        source = _technical_document_source(document)
        url = _technical_document_url(
            source, f"http://{settings.hostfile}/PhieuDieTiet", settings.hostfile
        )
        extension = Path(unquote(urlparse(url).path)).suffix.lower()
        allowed_extensions = {
            ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"
        }
        if extension not in allowed_extensions:
            raise HTTPException(status_code=415, detail="Chỉ hỗ trợ preview PDF hoặc hình ảnh")
        client = httpx.Client(timeout=settings.image_timeout_seconds, follow_redirects=False)
        upstream = client.send(client.build_request("GET", url), stream=True)
        if upstream.status_code == 404 and not urlparse(source).scheme:
            for fallback_base_url in (
                f"http://{settings.hostfile}/PhieuDieuTiet",
                f"http://{settings.hostfile}",
            ):
                fallback_url = _technical_document_url(
                    source, fallback_base_url, settings.hostfile
                )
                if fallback_url == url:
                    continue
                upstream.close()
                url = fallback_url
                upstream = client.send(client.build_request("GET", url), stream=True)
                if upstream.status_code != 404:
                    break
        upstream.raise_for_status()
    except HTTPException:
        raise
    except (pyodbc.Error, ValueError) as exc:
        raise _database_error(exc) from exc
    except httpx.HTTPError as exc:
        logger.exception(
            "Internal document download failed for document_id=%s url=%s status=%s database_url=%r database_local=%r",
            document_id,
            locals().get("url", "unresolved"),
            upstream.status_code if upstream is not None else "unavailable",
            locals().get("document", {}).get("DuongDanURL"),
            locals().get("document", {}).get("DuongDanLocal"),
            exc_info=exc,
        )
        if upstream is not None:
            upstream.close()
        if client is not None:
            client.close()
        raise HTTPException(status_code=502, detail="Không tải được tài liệu nội bộ") from exc

    assert client is not None and upstream is not None
    filename = _technical_document_filename(document, url)
    guessed_type = mimetypes.guess_type(filename)[0] or mimetypes.guess_type(url)[0]
    content_type = upstream.headers.get("content-type", "").split(";", 1)[0].strip()
    if not content_type or content_type == "application/octet-stream":
        content_type = guessed_type or "application/pdf"
    headers = {
        "Cache-Control": f"private, max-age={settings.image_cache_seconds}",
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
        "X-Content-Type-Options": "nosniff",
    }

    def stream_content():
        try:
            yield from upstream.iter_bytes()
        finally:
            upstream.close()
            client.close()

    return StreamingResponse(stream_content(), media_type=content_type, headers=headers)


@app.get("/api/traceability/images")
def image_metadata(rfid: str = Query(..., min_length=1, max_length=100)):
    value = _validate_rfid(rfid)
    try:
        rows = _image_rows(value)
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
        rows = _image_rows(value)
        url = _image_url_for_side(rows, side)
        _validate_internal_url(url, settings.hostfile)
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
