from __future__ import annotations

import base64
import binascii
from contextlib import asynccontextmanager
from datetime import datetime
import json
import logging
import mimetypes
from pathlib import Path
import re
from html import escape
from threading import Lock
from time import monotonic
from typing import Literal
from urllib.parse import quote, unquote, urlparse

import httpx
import pyodbc
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, StreamingResponse

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

_image_metadata_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_image_metadata_cache_lock = Lock()

_PRINT_QUERY_TYPES = {
    "invoice": ("02 - Số Invoice", "invoice.sql"),
    "rm-receipt": ("03 - Phiếu nhập kho NPL", "rm-receipt.sql"),
    "rm-inspection": ("04 - Phiếu kiểm NPL", "rm-inspection.sql"),
    "pl-inspection": ("04 - Phiếu kiểm phụ liệu", "pl-inspection.sql"),
    "rm-outbound": ("05 - Phiếu xuất kho NPL", "rm-outbound.sql"),
    "fabric-relaxing": ("07 - Phiếu xả vải", "fabric-relaxing.sql"),
    "fabric-cutting": ("09 - Phiếu cắt vải", "fabric-cutting.sql"),
    "wip-inspection": ("10 - Phiếu kiểm BTP", "wip-inspection.sql"),
    "wip-inbound": ("11 - Phiếu nhập kho BTP", "wip-inbound.sql"),
    "wip-issuing": ("12 - Phiếu đặt BTP", "wip-issuing.sql"),
    "wip-outbound": ("13 - Phiếu xuất BTP", "wip-outbound.sql"),
    "wip-scanning": ("15 - Phiếu quét nhận BTP", "wip-scanning.sql"),
}


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


def _print_query(document_type: str) -> tuple[str, str]:
    definition = _PRINT_QUERY_TYPES.get(document_type)
    if definition is None:
        raise HTTPException(status_code=404, detail="Loại phiếu chưa được hỗ trợ")
    title, filename = definition
    path = Path(__file__).resolve().parents[1] / "sql" / "print" / filename
    try:
        return title, path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        logger.exception("Print query file is unavailable: %s", path, exc_info=exc)
        raise HTTPException(status_code=503, detail="Câu SQL chi tiết chưa sẵn sàng") from exc


def _print_value(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return text
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _temporary_print_html(title: str, document_id: str, rows: list[dict]) -> str:
    sections = []
    for index, row in enumerate(rows, start=1):
        cells = "".join(
            f"<tr><th>{escape(str(name))}</th><td><pre>{escape(_print_value(value))}</pre></td></tr>"
            for name, value in row.items()
        )
        sections.append(f"<section><h2>Bản ghi {index}</h2><table>{cells}</table></section>")
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
body{{font:14px Arial,sans-serif;color:#172239;margin:24px}} header{{display:flex;justify-content:space-between;align-items:end;border-bottom:2px solid #172239;margin-bottom:20px}} h1{{font-size:22px}} h2{{font-size:16px;margin-top:24px}} table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #cbd5e1;padding:7px;text-align:left;vertical-align:top}} th{{width:220px;background:#f1f5f9}} pre{{white-space:pre-wrap;word-break:break-word;margin:0;font:inherit}} button{{padding:8px 16px}} @media print{{button{{display:none}} body{{margin:0}}}}
</style></head><body><header><div><h1>{escape(title)}</h1><p>Mã phiếu: {escape(document_id)}</p></div><button onclick="window.print()">In phiếu</button></header>{''.join(sections)}</body></html>"""


def _first_value(row: dict, *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _receipt_print_html(row: dict) -> str:
    try:
        details = json.loads(str(row.get("DetailsJson") or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        details = []
    if not isinstance(details, list):
        details = []

    doc_no = _first_value(row, "DocNo", "DocumentNo")
    doc_code = _first_value(row, "DocCode").upper()
    is_material = doc_code == "NK"
    doc_date = _first_value(row, "DocDate", "DocumentDate", "NgayChungTu", "CreatedDate")
    try:
        doc_date = datetime.fromisoformat(doc_date).strftime("%d/%m/%Y")
    except ValueError:
        pass
    supplier = _first_value(row, "SupplierName", "VendorName", "ObjectName", "ContactName", "TenNhaCungCap")
    warehouse = _first_value(row, "WarehouseName", "StockName", "WarehouseCode", "KhoNhap")
    description = _first_value(row, "Description", "Content", "Note", "DienGiai")
    first_detail = details[0] if details and isinstance(details[0], dict) else {}
    contract = _first_value(first_detail, "SalesContractsNo", "PurchaseContractNo")
    declaration = _first_value(first_detail, "CustomsDeclareNo")
    invoice_no = _first_value(row, "InvoiceNo", "AtchDocNo", "ReferenceNo") or _first_value(first_detail, "AtchDocNo")
    customer_content = _first_value(row, "CustomerContent", "CustomerName", "CustomerDescription", "DienGiaiKhachHang")
    reference_label = "Invoice" if is_material else "HĐGTGT"
    item_heading = "Tên, nhãn hiệu quy cách phẩm chất vật tư (sản phẩm, hàng hóa)" if is_material else "Mặt hàng"

    body_rows = []
    total_document = 0.0
    total_received = 0.0
    for index, detail in enumerate((item for item in details if isinstance(item, dict)), start=1):
        item_name = _first_value(detail, "ItemName", "ProductName", "Description", "ItemDescription", "ArtCode")
        item_code = _first_value(detail, "ItemCode", "MaterialCode", "ProductCode")
        unit = _first_value(detail, "Unit", "UnitName")
        document_quantity = _first_value(detail, "Quantity", "OrderQuantity", "DocumentQuantity")
        received_quantity = _first_value(detail, "ActualQuantity", "ReceivedQuantity", "Quantity")
        for value, target in ((document_quantity, "document"), (received_quantity, "received")):
            try:
                number = float(value.replace(".", "").replace(",", "."))
            except (AttributeError, ValueError):
                number = 0
            if target == "document":
                total_document += number
            else:
                total_received += number
        body_rows.append(
            "<tr>"
            f"<td class='number'>{index}</td><td>{escape(item_name)}</td>"
            f"<td>{escape(item_code)}</td><td>{escape(unit)}</td>"
            f"<td class='quantity'>{escape(document_quantity)}</td>"
            f"<td class='quantity'>{escape(received_quantity)}</td></tr>"
        )

    def total_text(value: float) -> str:
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phiếu nhập kho {escape(doc_no)}</title><style>
@page{{size:A4 landscape;margin:10mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:14px "Times New Roman",serif}} .sheet{{max-width:1120px;margin:auto}} .company{{font-size:18px;font-weight:700}} .heading{{position:relative;text-align:center;margin:28px 0 12px}} h1{{margin:0;font-size:28px}} .doc-no{{position:absolute;right:0;bottom:3px;font-size:17px;font-weight:700}} .meta{{display:grid;grid-template-columns:1fr 1fr;gap:5px 28px;margin:0 36px 22px;font-size:16px}} .field{{display:flex;gap:8px}} .field b{{min-width:145px}} .value{{flex:1;border-bottom:1px dotted #777;font-weight:700}} table{{width:100%;border-collapse:collapse;table-layout:fixed}} th,td{{border:1px solid #222;padding:6px;vertical-align:top}} th{{background:#fffef0;text-align:center;font-size:15px}} th:nth-child(1){{width:5%}} th:nth-child(2){{width:43%}} th:nth-child(3){{width:16%}} th:nth-child(4){{width:9%}} th:nth-child(5),th:nth-child(6){{width:13.5%}} .number,.quantity{{text-align:right}} tbody td{{min-height:34px}} tfoot td{{background:#fffed5;font-weight:700}} .signatures{{display:grid;grid-template-columns:repeat(5,1fr);margin-top:48px;text-align:center;font-weight:700}} .actions{{position:fixed;right:18px;top:18px}} button{{border:0;border-radius:7px;background:#172239;padding:9px 16px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="company">CÔNG TY CP ĐỒNG TIẾN</div><div class="heading"><h1>PHIẾU NHẬP KHO</h1><span class="doc-no">Số: {escape(doc_no)}</span></div>
<section class="meta"><div class="field"><b>Người giao hàng:</b><span class="value">{escape(supplier)}</span></div><div class="field"><b>Ngày:</b><span class="value">{escape(doc_date)}</span></div><div class="field"><b>Theo {reference_label}:</b><span class="value">{escape(invoice_no)}</span></div><div class="field"><b>Hợp đồng:</b><span class="value">{escape(contract)}</span></div>{f'<div class="field"><b>Của khách hàng:</b><span class="value">{escape(customer_content)}</span></div>' if is_material else f'<div class="field"><b>Nội dung nhập:</b><span class="value">{escape(description)}</span></div>'}<div class="field"><b>Số tờ khai:</b><span class="value">{escape(declaration)}</span></div><div class="field"><b>Nhập tại kho:</b><span class="value">{escape(warehouse)}</span></div></section>
<table><thead><tr><th rowspan="2">STT</th><th rowspan="2">{item_heading}</th><th rowspan="2">Mã vật tư</th><th rowspan="2">ĐVT</th><th colspan="2">Số lượng</th></tr><tr><th>Theo chứng từ</th><th>Thực nhập</th></tr></thead>
<tbody>{''.join(body_rows) if body_rows else '<tr><td colspan="6" style="text-align:center">Không có chi tiết vật tư</td></tr>'}</tbody>
<tfoot><tr><td></td><td colspan="3">Tổng cộng:</td><td class="quantity">{total_text(total_document)}</td><td class="quantity">{total_text(total_received)}</td></tr></tfoot></table>
<section class="signatures"><span>Thủ trưởng đơn vị</span><span>Thủ kho</span><span>Người giao</span><span>Kế toán trưởng</span><span>Người lập phiếu</span></section>
</main></body></html>"""


def _to_yards(meters: float) -> float:
    return meters * 1.0936133


def _fmt_number(value: object, decimals: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%d/%m/%Y")
    except ValueError:
        return text


def _json_list(row: dict, key: str) -> list:
    value = row.get(key)
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _fabric_inspection_print_html(row: dict) -> str:
    rolls = [item for item in _json_list(row, "InspectionTreesJson") if isinstance(item, dict)]
    legend = [item for item in _json_list(row, "DefectLegendJson") if isinstance(item, dict)]
    legend_index = {str(item.get("MaLoi")): index for index, item in enumerate(legend)}

    doc_no = _first_value(row, "DocNo")
    customer = _first_value(row, "CustomerName")
    ma_hang = _first_value(row, "MaHang")
    item_code = _first_value(row, "Item")
    supplier = _first_value(row, "SupplierName")
    po = _first_value(row, "CumPO")
    received_date = _fmt_date(row.get("NgayNhanVai"))
    inspection_date = _fmt_date(row.get("NgayKiemVai"))
    roll_count = _first_value(row, "RollCount")
    inspector = _first_value(row, "NhanVienKiem")

    def qty_text(meters: object) -> str:
        try:
            value = float(meters)
        except (TypeError, ValueError):
            return ""
        return f"{_fmt_number(value)} M / {_fmt_number(_to_yards(value))} YDS"

    roll_rows = []
    for index, roll in enumerate(rolls, start=1):
        defects = [item for item in _json_list(roll, "DefectsJson") if isinstance(item, dict)]
        points: list[object] = [None] * 25
        other_defects = []
        for defect in defects:
            code = str(defect.get("MaLoi") or "")
            total = defect.get("TongDiem") or defect.get("SoDiem") or defect.get("SoLoi")
            position = legend_index.get(code)
            if position is not None:
                points[position] = total
            else:
                name = str(defect.get("TenLoi") or code)
                other_defects.append(f"{name} ({_fmt_number(total, 0)})" if total is not None else name)
        defect_cells = "".join(
            f"<td>{escape(_fmt_number(value, 0)) if value is not None else ''}</td>" for value in points
        )
        passed = bool(roll.get("KetQuaKiem"))
        roll_rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{escape(_first_value(roll, 'MaMau'))}</td>"
            f"<td>{escape(_first_value(roll, 'MaCayVai'))}</td>"
            f"<td>{escape(_first_value(roll, 'Lot'))}</td>"
            "<td>Mét</td>"
            f"<td>{escape(_first_value(roll, 'KhoVaiTenTem'))}</td>"
            f"<td>{escape(_first_value(roll, 'KhoVaiThucTe'))}</td>"
            f"<td>{escape(_fmt_number(roll.get('SoLuongChungTu')))}</td>"
            f"<td>{escape(_fmt_number(roll.get('SoLuongThucTe')))}</td>"
            f"{defect_cells}"
            f"<td>{escape(_fmt_number(roll.get('DiemTrungBinh')))}</td>"
            f"<td class='result'>{'X' if passed else ''}</td>"
            f"<td class='result'>{'' if passed else 'X'}</td>"
            f"<td>{escape(_first_value(roll, 'HuongXuLy'))}</td>"
            f"<td>{escape(_first_value(roll, 'GhiChu'))}</td>"
            "</tr>"
        )
        if other_defects:
            roll_rows.append(
                "<tr class='note-row'><td colspan='9'></td>"
                f"<td colspan='30'>Lỗi khác (mã cũ): {escape('; '.join(other_defects))}</td></tr>"
            )

    legend_items = "".join(
        f"<div>{index + 1}. {escape(str(item.get('TenLoi') or ''))}</div>" for index, item in enumerate(legend)
    )
    defect_headers = "".join(f"<th>{index + 1}</th>" for index in range(25))

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Biên bản kiểm vải {escape(doc_no)}</title><style>
@page{{size:A4 landscape;margin:8mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:11px Arial,sans-serif}} .sheet{{max-width:1600px;margin:auto}}
.top{{display:flex;justify-content:space-between;font-weight:700;font-size:11px}} .title{{text-align:center;margin:6px 0}} .title h1{{margin:0;font-size:20px}} .title h2{{margin:2px 0;font-size:13px;font-weight:400}}
.meta{{display:grid;grid-template-columns:1.3fr 1fr 1.3fr;gap:3px 24px;margin:10px 0;font-size:12px}} .meta div{{display:flex;gap:6px}} .meta b{{min-width:120px}}
table{{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:6px}} th,td{{border:1px solid #444;padding:2px;text-align:center;font-size:8.5px;vertical-align:middle;word-break:break-word}}
.result{{width:22px}} .note-row td{{text-align:left;font-style:italic;font-size:9px;border-top:none}}
.note{{font-size:10px;margin:6px 0}} .legend{{display:grid;grid-template-columns:repeat(5,1fr);gap:2px 10px;font-size:9px;margin:8px 0;border-top:1px solid #ccc;padding-top:6px}}
.sign{{display:grid;grid-template-columns:1fr 1fr;text-align:center;margin-top:22px;font-size:11px}} .sign .date{{grid-column:2;margin-bottom:4px}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><span>CÔNG TY CỔ PHẦN ĐỒNG TIẾN<br>PHÒNG ĐBCL</span><span style="text-align:right">MẪU SỐ: 02SX<br>Ban hành lần: 3/0</span></div>
<div class="title"><h1>BIÊN BẢN KIỂM VẢI CHI TIẾT</h1><h2>Fabric inspection report — Số: {escape(doc_no)}</h2></div>
<section class="meta">
<div><b>Khách hàng:</b><span>{escape(customer)}</span></div>
<div><b>PO/ Cụm PO:</b><span>{escape(po)}</span></div>
<div><b>Ngày nhận vải:</b><span>{escape(received_date)}</span></div>
<div><b>Mã hàng:</b><span>{escape(ma_hang)}</span></div>
<div><b>Item:</b><span>{escape(item_code)}</span></div>
<div><b>Ngày kiểm vải:</b><span>{escape(inspection_date)}</span></div>
<div><b>Nhà cung cấp:</b><span>{escape(supplier)}</span></div>
<div><b>Số cây:</b><span>{escape(roll_count)}</span></div>
<div><b>Số lượng nhận:</b><span>{escape(qty_text(row.get('SoLuongNhan')))}</span></div>
<div></div><div></div>
<div><b>Số lượng kiểm:</b><span>{escape(qty_text(row.get('SoLuongKiem')))}</span></div>
</section>
<table><thead>
<tr><th rowspan="2">STT</th><th rowspan="2">Tên màu vải</th><th rowspan="2">Số roll</th><th rowspan="2">Lot</th><th rowspan="2">ĐVT</th>
<th colspan="2">Khổ vải (cm)</th><th colspan="2">Số lượng (m)</th><th colspan="25">Số lỗi vải</th><th rowspan="2">Điểm TB/<br>100yds²</th>
<th colspan="2">Kết quả</th><th rowspan="2">Hướng xử lý</th><th rowspan="2">Ghi chú</th></tr>
<tr><th>Tem</th><th>T.tế</th><th>Tem</th><th>T.tế</th>{defect_headers}<th>Đạt</th><th>K.đạt</th></tr>
</thead><tbody>{''.join(roll_rows) if roll_rows else '<tr><td colspan="39">Không có dữ liệu cây vải</td></tr>'}</tbody></table>
<p class="note">Ghi chú: Nếu tổng số lỗi dưới 25 điểm/100 yard vuông thì "đạt" và ngược lại thì "không đạt".</p>
<div class="legend">{legend_items}</div>
<section class="sign"><div class="date">{escape(inspection_date)}</div><div>MQP nhà máy<br>Inspection Leader</div><div>Người kiểm<br>Inspector<br><b>{escape(inspector)}</b></div></section>
</main></body></html>"""


def _pl_inspection_print_html(row: dict) -> str:
    details = [item for item in _json_list(row, "DetailsJson") if isinstance(item, dict)]

    doc_no = _first_value(row, "DocNo")
    customer = _first_value(row, "CustomerName")
    received_date = _fmt_date(row.get("ReceivedDate"))
    check_date = _fmt_date(row.get("DocDate"))

    body_rows = []
    for index, detail in enumerate(details, start=1):
        defects = [item for item in _json_list(detail, "DefectsJson") if isinstance(item, dict)]
        defect_qty = sum(float(d.get("SoLuongLoi") or 0) for d in defects)
        defect_names = "; ".join(
            f"{escape(str(d.get('DefectName') or d.get('MaLoi') or ''))} ({_fmt_number(d.get('SoLuongLoi'), 0)})"
            for d in defects
        )
        try:
            checked = float(detail.get("SLKiem") or 0)
        except (TypeError, ValueError):
            checked = 0.0
        rate = f"{defect_qty / checked * 100:.1f}%" if checked else ""
        result = "KHÔNG ĐẠT" if defect_qty > 0 else "ĐẠT"
        body_rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{escape(_first_value(detail, 'NgayNhan'))}</td>"
            f"<td>{escape(_first_value(detail, 'TenNPL', 'ItemName'))}</td>"
            f"<td>{escape(_first_value(detail, 'StyleCode'))}</td>"
            f"<td>{escape(_first_value(detail, 'ChungTu'))}</td>"
            f"<td>{escape(_first_value(detail, 'ItemCode', 'MaNPL'))}</td>"
            f"<td>{escape(_first_value(detail, 'SupplierName'))}</td>"
            f"<td>{escape(_first_value(detail, 'ColorCodeB'))}</td>"
            f"<td>{escape(_first_value(detail, 'UnitCodeB'))}</td>"
            f"<td>{escape(_fmt_number(detail.get('DocumentQuantity')))}</td>"
            f"<td>{escape(_fmt_number(detail.get('ReceivedQuantity')))}</td>"
            f"<td>{escape(_fmt_number(detail.get('SLKiem'), 0))}</td>"
            f"<td>{escape(_fmt_number(defect_qty, 0)) if defect_qty else ''}</td>"
            f"<td>{escape(rate)}</td>"
            f"<td>{escape(result)}</td>"
            f"<td>{defect_names}</td>"
            f"<td>{escape(_first_value(detail, 'HuongXuLy'))}</td>"
            f"<td>{escape(_first_value(detail, 'AnhMauPL'))}</td>"
            f"<td>{escape(_first_value(detail, 'GhiChu'))}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Báo cáo kiểm phụ liệu {escape(doc_no)}</title><style>
@page{{size:A4 landscape;margin:8mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:11px Arial,sans-serif}} .sheet{{max-width:1500px;margin:auto}}
.top{{display:flex;justify-content:space-between;font-weight:700;font-size:11px}} .title{{text-align:center;margin:6px 0}} .title h1{{margin:0;font-size:16px}} .title h2{{margin:2px 0;font-size:10px;font-weight:400}}
.meta{{display:flex;justify-content:space-between;font-size:11px;margin:8px 0}} .meta b{{margin-right:6px}}
table{{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:6px}} th,td{{border:1px solid #444;padding:3px;text-align:center;font-size:9px;vertical-align:middle;word-break:break-word}}
.sign{{display:flex;justify-content:flex-end;text-align:center;margin-top:26px;font-size:11px}} .sign div{{width:160px}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><span>CÔNG TY CỔ PHẦN ĐỒNG TIẾN<br>ĐƠN VỊ: KHO NPL</span><span style="text-align:right">MẪU SỐ: QA 02<br>Ban hành lần: 3/0</span></div>
<div class="title"><h1>BÁO CÁO GIÁM ĐỊNH KIỂM TRA CHẤT LƯỢNG PHỤ LIỆU</h1><h2>Accessory inspection report</h2></div>
<section class="meta">
<div><b>Số PGD:</b>{escape(doc_no)} &nbsp; <b>Từ ngày:</b>{escape(received_date)} &nbsp; <b>Đến ngày:</b>{escape(check_date)}</div>
<div><b>Khách hàng:</b>{escape(customer)}</div>
</section>
<table><thead><tr>
<th>STT</th><th>Ngày nhận</th><th>Tên vật tư</th><th>Mã hàng</th><th>Chứng từ</th><th>Item</th><th>Nhà cung cấp</th><th>Màu</th><th>ĐVT</th>
<th>SL Packing List</th><th>SL Thực tế</th><th>SL Kiểm</th><th>SL Ko đạt</th><th>Tỉ lệ lỗi</th><th>Kết quả</th><th>Loại lỗi phụ liệu</th><th>Hướng xử lý</th><th>Ánh màu</th><th>Ghi chú</th>
</tr></thead><tbody>{''.join(body_rows) if body_rows else '<tr><td colspan="19">Không có dữ liệu chi tiết</td></tr>'}</tbody></table>
<section class="sign"><div>{escape(check_date)}<br>Người thực hiện</div></section>
</main></body></html>"""


_VN_WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def _fmt_date_vn(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    return f"{_VN_WEEKDAYS[parsed.weekday()]}, Ngày {parsed.day:02d} tháng {parsed.month:02d} năm {parsed.year}"


def _outbound_print_html(row: dict) -> str:
    details = [item for item in _json_list(row, "DetailsJson") if isinstance(item, dict)]

    doc_no = _first_value(row, "DocNo")
    signer = _first_value(row, "TenNguoiTao")
    production_order = ""

    body_rows = []
    total_qty = 0.0
    index = 0
    for detail in details:
        item_name = _first_value(detail, "DienGiai")
        unit = _first_value(detail, "DVT")
        rolls = [item for item in (detail.get("RollsJson") or []) if isinstance(item, dict)]
        for roll in rolls:
            index += 1
            if not production_order:
                production_order = _first_value(roll, "ProductionOrderNo")
            barcode_start = _first_value(roll, "MaCay")
            barcode = _first_value(roll, "MaCayMoi") or barcode_start
            quantity = roll.get("SoLuong")
            try:
                total_qty += float(quantity)
            except (TypeError, ValueError):
                pass
            body_rows.append(
                "<tr>"
                f"<td>{index}</td>"
                f"<td>{escape(_first_value(roll, 'MaHangPO'))}</td>"
                f"<td>{escape(item_name)}</td>"
                f"<td>{escape(_first_value(roll, 'ArtCode'))}</td>"
                f"<td>{escape(_first_value(roll, 'SizeCode'))}</td>"
                f"<td>{escape(barcode_start)}</td>"
                f"<td>{escape(barcode)}</td>"
                f"<td class='quantity'>{escape(_fmt_number(quantity))}</td>"
                f"<td>{escape(unit)}</td>"
                f"<td>{escape(_first_value(roll, 'MaRo'))}</td>"
                f"<td>{escape(_first_value(roll, 'TenViTriRo'))}</td>"
                "</tr>"
            )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Danh sách soạn hàng {escape(doc_no)}</title><style>
@page{{size:A4;margin:10mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:12px Arial,sans-serif}} .sheet{{max-width:1000px;margin:auto}}
.top{{display:flex;justify-content:space-between;align-items:flex-start}} .company{{font-weight:700}}
.heading{{text-align:center;margin:6px 0 14px}} .heading h1{{margin:0;font-size:20px}} .heading .lsx{{font-size:13px;margin-top:2px}}
.doc-no{{font-weight:700;font-size:13px;text-align:right}}
table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #333;padding:5px;text-align:center;font-size:11px;vertical-align:middle}} th{{background:#f1f0e8}}
.quantity{{text-align:right}} tfoot td{{font-weight:700}} tfoot td:first-child{{text-align:left}}
.sign{{text-align:right;margin-top:22px;font-size:12px}} .sign b{{display:block;margin-top:26px}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><div class="company">CÔNG TY CỔ PHẦN ĐỒNG TIẾN<br><span style="font-weight:400">ĐƠN VỊ: KHO</span></div><div class="doc-no">{escape(doc_no)}</div></div>
<div class="heading"><h1>DANH SÁCH SOẠN HÀNG</h1>{f'<div class="lsx">LSX: {escape(production_order)}</div>' if production_order else ''}</div>
<table><thead><tr>
<th>STT</th><th>Mã hàng</th><th>Tên vật tư</th><th>Art</th><th>Size</th><th>Barcode BĐ</th><th>Barcode</th><th>Số lượng<br>thực xuất</th><th>ĐVT</th><th>Rọ/Pallet</th><th>Vị trí</th>
</tr></thead>
<tbody>{''.join(body_rows) if body_rows else '<tr><td colspan="11">Không có dữ liệu</td></tr>'}</tbody>
<tfoot><tr><td colspan="7">TỔNG:</td><td class="quantity">{escape(_fmt_number(total_qty))}</td><td colspan="3"></td></tr></tfoot>
</table>
<section class="sign">{escape(_fmt_date_vn(row.get('DocDate')))}<b>Nhân viên soạn hàng</b>{escape(signer)}</section>
</main></body></html>"""


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    try:
        with pyodbc.connect(connection_string(settings)) as connection:
            connection.cursor().execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except pyodbc.Error:
        return {"status": "degraded", "database": "unavailable"}


def _traceability_by_query(
    rfid: str,
    query: str | None,
    response: Response | None = None,
    image_source: Literal["legacy", "new"] | None = None,
):
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
    if image_source is not None:
        image_rows = _extract_image_rows(result)
        _cache_image_rows(image_source, value, image_rows)
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
    return _traceability_by_query(rfid, get_settings().sqlquery, response, image_source="legacy")


@app.get("/api/traceability/new")
def traceability_new(response: Response, rfid: str = Query(..., min_length=1, max_length=100)):
    return _traceability_by_query(rfid, _new_traceability_query(), response, image_source="new")


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
        row_side = str(row.get("Side") or row.get("SIDE") or "").strip().casefold()
        if row_side == side or (not row_side and url.upper().endswith(suffix)):
            return url
    raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")


def _extract_image_rows(result: dict) -> list[dict]:
    rows = []
    for column, side in (("URLFrontImage", "front"), ("URLBackImage", "back")):
        url = str(result.pop(column, None) or "").strip()
        if url:
            rows.append({"Url": url, "Side": side})
    return rows


def _cache_image_rows(source: str, rfid: str, rows: list[dict]) -> None:
    now = monotonic()
    cache_key = (source, rfid.casefold())
    expires_at = now + get_settings().image_metadata_cache_seconds
    with _image_metadata_cache_lock:
        if len(_image_metadata_cache) >= 1000:
            expired_keys = [key for key, item in _image_metadata_cache.items() if item[0] <= now]
            for key in expired_keys:
                _image_metadata_cache.pop(key, None)
            if len(_image_metadata_cache) >= 1000:
                _image_metadata_cache.pop(next(iter(_image_metadata_cache)))
        _image_metadata_cache[cache_key] = (expires_at, rows)


def _image_rows(rfid: str, source: Literal["legacy", "new"] = "legacy") -> list[dict]:
    settings = get_settings()
    cache_key = (source, rfid.casefold())
    now = monotonic()
    with _image_metadata_cache_lock:
        cached = _image_metadata_cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
        if cached:
            _image_metadata_cache.pop(cache_key, None)

    query = _new_traceability_query() if source == "new" else settings.sqlquery
    if not query:
        raise ValueError("Câu truy vấn RFID chưa được cấu hình")
    rows = query_rows(settings, query, {"RFID": rfid})
    if source == "legacy":
        rows = _extract_image_rows(rows[0]) if rows else []
    _cache_image_rows(source, rfid, rows)
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


_BASE64_IMAGE_SIGNATURES: dict[str, str] = {
    "iVBORw0KGgo": "image/png",
    "/9j/": "image/jpeg",
    "R0lGOD": "image/gif",
    "Qk0": "image/bmp",
}


def _validate_legacy_document_url(url: str, allowed_hosts: str) -> None:
    parsed = urlparse(url)
    hosts = {host.strip().lower() for host in allowed_hosts.split(",") if host.strip()}
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in hosts:
        raise HTTPException(status_code=502, detail="Địa chỉ tài liệu không được phép")


@app.get("/api/traceability/legacy-document")
def legacy_document(url: str = Query(..., min_length=1, max_length=2000)):
    settings = get_settings()
    _validate_legacy_document_url(url, settings.legacy_document_hosts)
    try:
        with httpx.Client(timeout=settings.image_timeout_seconds, follow_redirects=True) as client:
            upstream = client.get(url)
            upstream.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Không tải được tài liệu nội bộ") from exc

    content_type = upstream.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    body = upstream.content
    if content_type.startswith("image/"):
        return Response(content=body, media_type=content_type)

    # Máy chủ tài liệu cũ trả về chuỗi base64 của ảnh thay vì bytes ảnh thật.
    text = body.decode("utf-8", errors="ignore").strip().strip('"')
    for prefix, mime in _BASE64_IMAGE_SIGNATURES.items():
        if text.startswith(prefix):
            try:
                decoded = base64.b64decode(text, validate=False)
            except (binascii.Error, ValueError) as exc:
                raise HTTPException(status_code=502, detail="Không giải mã được ảnh") from exc
            return Response(content=decoded, media_type=mime)

    return Response(content=body, media_type=content_type or "application/octet-stream")


@app.get("/api/traceability/print/{document_type}", response_class=HTMLResponse)
def print_traceability_document(
    document_type: str,
    document_id: str = Query(..., alias="id", min_length=1, max_length=255),
):
    value = _validate_lookup(document_id, "Mã phiếu", 255)
    title, query = _print_query(document_type)
    try:
        rows = query_rows(get_settings(), query, {"DocumentId": value})
    except (pyodbc.Error, ValueError) as exc:
        raise _database_error(exc) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu chi tiết phiếu")
    if document_type == "rm-receipt":
        html = _receipt_print_html(rows[0])
    elif document_type == "rm-inspection":
        html = _fabric_inspection_print_html(rows[0])
    elif document_type == "pl-inspection":
        html = _pl_inspection_print_html(rows[0])
    elif document_type == "rm-outbound":
        html = _outbound_print_html(rows[0])
    else:
        html = _temporary_print_html(title, value, rows)
    return HTMLResponse(html)


@app.get("/api/traceability/images")
def image_metadata(
    rfid: str = Query(..., min_length=1, max_length=100),
    source: Literal["legacy", "new"] = "legacy",
):
    value = _validate_rfid(rfid)
    try:
        rows = _image_rows(value, source)
    except (pyodbc.Error, ValueError) as exc:
        raise _database_error(exc) from exc
    available = {"front": False, "back": False}
    for row in rows:
        url = str(row.get("Url") or row.get("URL") or "").upper()
        side = str(row.get("Side") or row.get("SIDE") or "").strip().casefold()
        available["front"] = available["front"] or side == "front" or (not side and url.endswith("MT.JPG"))
        available["back"] = available["back"] or side == "back" or (not side and url.endswith("MS.JPG"))
    return available


@app.get("/api/traceability/image")
def product_image(
    rfid: str = Query(..., min_length=1, max_length=100),
    side: Literal["front", "back"] = "front",
    source: Literal["legacy", "new"] = "legacy",
):
    settings = get_settings()
    value = _validate_rfid(rfid)
    client: httpx.Client | None = None
    upstream: httpx.Response | None = None
    try:
        rows = _image_rows(value, source)
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
