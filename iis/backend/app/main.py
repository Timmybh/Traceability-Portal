from __future__ import annotations

import base64
import binascii
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
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
    "wip-to-subcontractor": ("14 - Phiếu xuất BTP gia công", "wip-to-subcontractor.sql"),
    "wip-scanning": ("15 - Phiếu quét nhận BTP", "wip-scanning.sql"),
    "endline": ("QC - Báo cáo Endline", "endline.sql"),
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


def _fmt_datetime_parts(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text, ""
    return parsed.strftime("%d/%m/%Y"), parsed.strftime("%H:%M")


def _fabric_relaxing_print_html(row: dict) -> str:
    doc_no = _first_value(row, "IdPhieuXaVai")
    customer = _first_value(row, "CustomerName")
    hours = row.get("ThoiGian")
    try:
        hours_value = float(hours) if hours is not None else None
    except (TypeError, ValueError):
        hours_value = None
    is_24 = hours_value == 24
    is_48 = hours_value == 48
    is_other = hours_value is not None and not is_24 and not is_48

    def checkbox(checked: bool) -> str:
        return "☑" if checked else "☐"

    relax_date, relax_time = _fmt_datetime_parts(row.get("ThoiGianXaVai"))
    spread_date, spread_time = _fmt_datetime_parts(row.get("ThoiGianTraiVai"))
    relaxing_staff = _first_value(row, "NguoiXaVai")
    spreading_staff = _first_value(row, "NguoiTraiVai")

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phiếu xả vải {escape(doc_no)}</title><style>
@page{{size:A4;margin:10mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:13px Arial,sans-serif}} .sheet{{max-width:820px;margin:auto;border:1px solid #333;padding:16px 22px}}
.top{{display:flex;justify-content:space-between;font-size:12px}} .top .form-code{{text-align:right}}
.heading{{text-align:center;margin:8px 0 16px}} .heading h1{{margin:0;font-size:22px;letter-spacing:1px}} .heading small{{font-size:12px}}
.row{{margin:8px 0;display:flex;gap:6px;align-items:baseline}} .row b{{min-width:0}}
.checks{{display:flex;gap:20px;margin:10px 0}} .checks span{{display:inline-flex;align-items:center;gap:4px;border:1px solid #333;padding:2px 8px}}
.two-col{{display:flex;justify-content:space-between}} .two-col > div{{flex:1}}
.note{{margin-top:16px;font-size:12px}} .note b{{display:block}}
.sign-grid{{display:flex;justify-content:space-around;margin-top:36px;text-align:center;font-size:12px}} .sign-grid .role{{font-weight:700}} .sign-grid .confirmed{{font-style:italic;margin-top:32px}} .sign-grid .name{{margin-top:4px;font-weight:700}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><div>Công ty cổ phần Đồng Tiến (Dong Tien Joint Stock Company)</div><div class="form-code">BM 27 HD 10-02<br>Số lần sửa đổi: 05</div></div>
<div class="heading"><h1>PHIẾU XẢ VẢI</h1><small>(Fabric relaxing note)</small></div>
<div class="row"><b>Khách hàng (Customer):</b>&nbsp;{escape(customer)}</div>
<div class="checks">
<span>24h: {checkbox(is_24)}</span><span>48h: {checkbox(is_48)}</span><span>Xả trải: {checkbox(False)}</span>
<span>Khác: {checkbox(is_other)} {escape(_fmt_number(hours_value, 0)) + 'h' if is_other else ''}</span>
</div>
<div class="two-col"><div><b>Ngày xả vải (Relaxing date):</b> {escape(relax_date)}</div><div><b>Giờ (Time):</b> {escape(relax_time)}</div></div>
<div class="two-col"><div><b>Ngày có thể trải/cắt (Spreading/Cutting date able):</b> {escape(spread_date)}</div><div><b>Giờ (Time):</b> {escape(spread_time)}</div></div>
<div class="two-col"><div><b>Mã cây:</b> {escape(_first_value(row, 'MaCay'))} &nbsp;&nbsp; <b>Màu:</b> {escape(_first_value(row, 'MauVai'))}</div></div>
<div class="two-col"><div><b>Số cây (Roll):</b> {escape(_first_value(row, 'SoCay_Roll'))}</div><div><b>Yard / Meter:</b> {escape(_fmt_number(row.get('YardQuantity')))} yards / {escape(_fmt_number(row.get('MeterQuantity')))} meter</div></div>
<div class="two-col"><div><b>Art vải (Fabric Art):</b> {escape(_first_value(row, 'Art'))}</div><div><b>Lot:</b> {escape(_first_value(row, 'Lot'))}</div></div>
<div class="two-col"><div><b>Khổ cắt (Cuttable width):</b> {escape(_fmt_number(row.get('KhoCat')))}</div><div><b>Ánh màu:</b> {escape(_first_value(row, 'ShadeNo'))}</div></div>
<div class="note"><b>Ghi chú: Đối với thời gian xả vải khác 24h hay 48h thì phải ghi rõ thời gian xả vào ô "Khác".</b>
(Note: For the fabric relaxing time which differs from 24h or 48h, needs to be written in "Other" box clearly.)</div>
<div class="sign-grid">
<div><div class="role">Nhân viên xả vải<br>(Fabric relaxing staff)</div>{f'<div class="confirmed">Đã xác nhận</div><div class="name">{escape(relaxing_staff)}</div>' if relaxing_staff else ''}</div>
<div><div class="role">Nhân viên trải vải<br>(Fabric spreading staff)</div>{f'<div class="confirmed">Đã xác nhận</div><div class="name">{escape(spreading_staff)}</div>' if spreading_staff else ''}</div>
</div>
</main></body></html>"""


_INSPECTION_POSITIONS = ("T", "G", "D")


def _inspection_cell(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "Chưa kiểm", "unchecked"
    if text.upper() in ("OK", "DAT", "ĐẠT", "PASS"):
        return "✓", "pass"
    return text, "defect"


def _wip_inspection_print_html(row: dict) -> str:
    details = [item for item in _json_list(row, "DetailsJson") if isinstance(item, dict)]
    recheck_details = [item for item in _json_list(row, "RecheckDetailsJson") if isinstance(item, dict)]

    doc_no = _first_value(row, "IdPhieuKiemTra")
    form_no = _first_value(row, "FormNo") or "BM 02 HD 10-03"
    revision_no = _first_value(row, "RevisionNo") or "08"
    inspection_date = _fmt_date(row.get("InspectionDate"))
    inspector = _first_value(row, "Inspector")
    qc_leader = _first_value(row, "QcLeader")

    def cell_text(value: object) -> str:
        return "" if value is None else str(value)

    def summary_row(label: str, groups: list[list[int]], total: object) -> str:
        g = groups
        return (
            "<tr class='summary'>"
            f"<td colspan='2'>{escape(label)}</td>"
            f"<td>{cell_text(g[0][0])}</td><td>{cell_text(g[0][1])}</td><td>{cell_text(g[0][2])}</td>"
            f"<td></td><td>{cell_text(g[1][0])}</td><td>{cell_text(g[1][1])}</td><td>{cell_text(g[1][2])}</td>"
            f"<td></td><td>{cell_text(g[2][0])}</td><td>{cell_text(g[2][1])}</td><td>{cell_text(g[2][2])}</td>"
            "<td></td><td></td>"
            f"<td>{cell_text(g[3][0])}</td><td>{cell_text(g[3][1])}</td><td>{cell_text(g[3][2])}</td>"
            "<td></td><td></td>"
            f"<td>{escape(str(total))}</td>"
            "</tr>"
        )

    def blank_summary_row(label: str) -> str:
        return f"<tr class='summary'><td colspan='2'>{escape(label)}</td>{'<td></td>' * 19}</tr>"

    _SUMMARY_LABELS = (
        "Tổng số chi tiết lỗi",
        "Tổng số lượng đạt",
        "Tổng số lượng kiểm",
        "RFT (Tổng số lượng đạt/Tổng số lượng kiểm*100%)",
    )

    def render_section(items: list[dict]) -> tuple[str, str]:
        if not items:
            body = "<tr>" + "<td></td>" * 21 + "</tr>"
            summary = "".join(blank_summary_row(label) for label in _SUMMARY_LABELS)
            return body, summary

        pass_counts = [[0, 0, 0] for _ in range(4)]
        defect_counts = [[0, 0, 0] for _ in range(4)]
        body_rows = []
        for item in items:
            sheets_raw = item.get("Sheets")
            sheets = sheets_raw if isinstance(sheets_raw, list) else []
            sheet_cells = []
            for group_index in range(3):
                sheet = sheets[group_index] if group_index < len(sheets) and isinstance(sheets[group_index], dict) else {}
                size = _first_value(sheet, "Size")
                position_cells = []
                for pos_index, pos in enumerate(_INSPECTION_POSITIONS):
                    text, state = _inspection_cell(sheet.get(pos))
                    if state == "pass":
                        pass_counts[group_index][pos_index] += 1
                    elif state == "defect":
                        defect_counts[group_index][pos_index] += 1
                    position_cells.append(f"<td class='chk {state}'>{escape(text)}</td>")
                sheet_cells.append(f"<td>{escape(size)}</td>{''.join(position_cells)}")
            recheck_raw = item.get("Recheck")
            recheck = recheck_raw if isinstance(recheck_raw, dict) else {}
            recheck_cells = []
            for pos_index, pos in enumerate(_INSPECTION_POSITIONS):
                text, state = _inspection_cell(recheck.get(pos))
                if state == "pass":
                    pass_counts[3][pos_index] += 1
                elif state == "defect":
                    defect_counts[3][pos_index] += 1
                recheck_cells.append(f"<td class='chk {state}'>{escape(text)}</td>")
            body_rows.append(
                "<tr>"
                f"<td>{escape(_first_value(item, 'PartName', 'ChiTiet'))}</td>"
                f"{''.join(sheet_cells)}"
                f"<td>{escape(_first_value(item, 'DefectDescription'))}</td>"
                f"<td>{escape(_first_value(item, 'QcLeaderConfirm') or qc_leader)}</td>"
                f"{''.join(recheck_cells)}"
                f"<td>{escape(_first_value(item, 'RecheckDefectDescription'))}</td>"
                f"<td>{escape(_first_value(item, 'ReplacementConfirm'))}</td>"
                "<td></td>"
                "</tr>"
            )

        total_pass = sum(sum(group) for group in pass_counts)
        total_defect = sum(sum(group) for group in defect_counts)
        total_checked = total_pass + total_defect
        rft = f"{total_pass / total_checked * 100:.0f}%" if total_checked else ""

        # Lượng kiểm và RFT chỉ có tổng hợp (giống mẫu giấy không tách theo lá kiểm).
        summary = (
            summary_row(_SUMMARY_LABELS[0], defect_counts, total_defect)
            + summary_row(_SUMMARY_LABELS[1], pass_counts, total_pass)
            + f"<tr class='summary'><td colspan='2'>{escape(_SUMMARY_LABELS[2])}</td>{'<td></td>' * 18}<td>{total_checked}</td></tr>"
            + f"<tr class='summary'><td colspan='2'>{escape(_SUMMARY_LABELS[3])}</td>{'<td></td>' * 18}<td>{escape(rft)}</td></tr>"
        )
        body = "".join(body_rows)
        return body, summary

    main_body, main_summary = render_section(details)
    recheck_body, recheck_summary = render_section(recheck_details)

    group_header = "<th>T</th><th>G</th><th>D</th>"

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phiếu kiểm BTP cắt {escape(doc_no)}</title><style>
@page{{size:A4 landscape;margin:8mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:11px Arial,sans-serif}} .sheet{{max-width:1500px;margin:auto}}
.top{{display:flex;justify-content:space-between;font-size:11px}} .top .form-code{{text-align:right}}
.heading{{text-align:center;margin:6px 0 12px}} .heading h1{{margin:0;font-size:18px}} .heading div{{font-size:13px}}
.meta{{display:grid;grid-template-columns:repeat(3,1fr);gap:2px 20px;font-size:11px;margin-bottom:8px}} .meta b{{margin-right:4px}}
table{{width:100%;border-collapse:collapse;table-layout:fixed;margin-top:6px}} th,td{{border:1px solid #444;padding:3px;text-align:center;font-size:9.5px;vertical-align:middle;word-break:break-word}}
th{{background:#f1f0e8}} tr.summary td{{font-weight:700;text-align:left}} tr.summary td:first-child{{padding-left:6px}}
td.chk.pass{{color:#0a7a2f;font-weight:700}} td.chk.defect{{color:#c0272d;font-weight:700}} td.chk.unchecked{{color:#888;font-style:italic}}
.section-title td{{font-style:italic;font-weight:700;background:#ddd;text-align:left;padding:4px 6px}}
.note{{font-size:10px;margin:8px 0 2px}}
.sign{{display:flex;justify-content:space-between;margin-top:26px;font-size:11px}} .sign .role{{font-weight:700}} .sign .name{{margin-top:32px;font-weight:700}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><div>CÔNG TY CỔ PHẦN ĐỒNG TIẾN<br>DONG TIEN JOINT STOCK COMPANY</div><div class="form-code">{escape(form_no)}<br>Số lần sửa đổi: {escape(revision_no)}</div></div>
<div class="heading"><h1>PHIẾU KIỂM TRA CHẤT LƯỢNG BÁN THÀNH PHẨM CẮT</h1><div>SEMI-FINISHED PRODUCTS QUALITY INSPECTION REPORT</div></div>
<section class="meta">
<div><b>Xí nghiệp (Factory):</b>{escape(_first_value(row, 'Factory'))}</div>
<div><b>Tổ (Line):</b>{escape(_first_value(row, 'Line'))}</div>
<div><b>Mã hàng (Style):</b>{escape(_first_value(row, 'Style'))}</div>
<div><b>Mùa (Season):</b>{escape(_first_value(row, 'Season'))}</div>
<div><b>Lệnh:</b>{escape(_first_value(row, 'ProductionOrder'))}</div>
<div></div>
<div><b>Bàn cắt (Cutting table no):</b>{escape(_first_value(row, 'CuttingTable'))}</div>
<div><b>Bàn may (Sewing no):</b>{escape(_first_value(row, 'SewingTable'))}</div>
<div></div>
<div><b>Số lượng (quantities):</b>{escape(_first_value(row, 'Quantities'))}</div>
<div><b>Art vải:</b>{escape(_first_value(row, 'FabricArt'))}</div>
<div><b>Vóc:</b>{escape(_first_value(row, 'Voc'))}</div>
</section>
<table><thead>
<tr>
<th rowspan="2">Chi tiết</th>
<th rowspan="2">Size</th><th colspan="3">Lá kiểm</th>
<th rowspan="2">Size</th><th colspan="3">Lá kiểm</th>
<th rowspan="2">Size</th><th colspan="3">Lá kiểm</th>
<th rowspan="2">Mô tả lỗi</th>
<th rowspan="2">Tổ trưởng ký<br>xác nhận lỗi</th>
<th colspan="3">Kiểm lần 2</th>
<th rowspan="2">Mô tả lỗi</th>
<th rowspan="2">Thay thân<br>xác nhận</th>
<th rowspan="2">Tổng hợp</th>
</tr>
<tr>{group_header}{group_header}{group_header}{group_header}</tr>
</thead>
<tbody>{main_body}</tbody>
<tbody>{main_summary}</tbody>
<tbody><tr class="section-title"><td colspan="21">Kiểm lại (sau khi thay thân)</td></tr></tbody>
<tbody>{recheck_body}</tbody>
<tbody>{recheck_summary}</tbody>
</table>
<p class="note">*Ghi chú: Đạt (✓) ; không đạt (Mã lỗi); lá kiểm tiếp của lá không đạt – nếu lá kiểm tiếp không đạt (Mã lỗi).</p>
<p class="note">Viết tắt: Trên: T, Giữa: G, Dưới: D</p>
<section class="sign">
<div><div class="role">Người kiểm (QC)</div><div class="name">{escape(inspector)}</div></div>
<div style="text-align:right"><div>{escape(inspection_date)}</div><div class="role">Tổ trưởng QC (QC leader)</div><div class="name">{escape(qc_leader)}</div></div>
</section>
</main></body></html>"""


def _fmt_date_vn_words(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    return f"Ngày {parsed.day} tháng {parsed.month} năm {parsed.year}"


def _wip_issuing_print_html(row: dict) -> str:
    details = [item for item in _json_list(row, "DetailsJson") if isinstance(item, dict)]

    doc_no = _first_value(row, "SoPhieuCapBTP")
    form_no = _first_value(row, "FormNo") or "BM 09 HD 10-02"
    revision_no = _first_value(row, "RevisionNo") or "01"
    qr_code = _first_value(row, "QrCode") or doc_no
    receive_date = _fmt_date_vn_words(row.get("ReceiveDate"))
    request_date = _fmt_date_vn_words(row.get("RequestDate"))

    body_rows = []
    totals = {"in_line": 0.0, "sewn": 0.0, "remaining": 0.0, "needed": 0.0, "quantity": 0.0}

    def add_total(key: str, value: object) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        totals[key] += number
        return number

    for detail in details:
        in_line = add_total("in_line", detail.get("QuantityInLine"))
        sewn = add_total("sewn", detail.get("QuantitySewn"))
        remaining = add_total("remaining", detail.get("QuantityRemaining"))
        needed = add_total("needed", detail.get("QuantityNeeded"))
        quantity = add_total("quantity", detail.get("Quantity"))
        color = escape(_first_value(detail, "ColorDescription")).replace("\n", "<br>")
        body_rows.append(
            "<tr>"
            f"<td>{escape(_first_value(detail, 'PO'))}</td>"
            f"<td>{escape(_fmt_number(in_line, 0)) if in_line is not None else ''}</td>"
            f"<td>{escape(_fmt_number(sewn, 0)) if sewn is not None else ''}</td>"
            f"<td>{escape(_fmt_number(remaining, 0)) if remaining is not None else ''}</td>"
            f"<td>{escape(_fmt_number(needed, 0)) if needed is not None else ''}</td>"
            f"<td class='color'>{color}</td>"
            f"<td>{escape(_first_value(detail, 'Size'))}</td>"
            f"<td>{escape(_fmt_number(quantity, 0)) if quantity is not None else ''}</td>"
            f"<td>{escape(_first_value(detail, 'Note'))}</td>"
            "</tr>"
        )

    delivery_rows = "".join(
        f"<tr><td>Giao BTP lần {n}</td><td></td><td></td><td></td><td></td></tr>" for n in range(1, 5)
    )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phiếu cấp BTP {escape(doc_no)}</title><style>
@page{{size:A4;margin:10mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:12px Arial,sans-serif}} .sheet{{max-width:1000px;margin:auto}}
.top{{display:flex;justify-content:space-between;align-items:flex-start}} .form-code{{text-align:right;font-size:12px}}
.heading{{text-align:center;margin:10px 0 14px;position:relative}} .heading h1{{margin:0;font-size:22px;letter-spacing:.5px}}
.qr{{position:absolute;right:0;top:-6px;text-align:center;font-size:10px}} .qr .box{{width:64px;height:64px;border:1px dashed #999;display:flex;align-items:center;justify-content:center;font-size:8px;color:#999;margin:0 auto 2px}}
.meta{{display:flex;gap:24px;font-size:12px;margin-bottom:4px}} .meta b{{margin-right:4px}}
.meta2{{font-size:12px;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #333;padding:5px;text-align:center;font-size:11px;vertical-align:middle}} th{{background:#f1f0e8}}
td.color{{text-align:left}} tfoot td{{font-weight:700}} tfoot td:first-child{{text-align:right}}
.section-title{{font-weight:700;margin:14px 0 6px}}
.delivery td:first-child{{text-align:left}}
.sign{{display:grid;grid-template-columns:1fr 1fr 1fr;text-align:center;margin-top:26px;font-size:12px}} .sign .role{{font-weight:700}} .sign .name{{margin-top:40px;font-weight:700}}
.sign-date{{text-align:right;font-weight:700;margin-top:18px;font-size:12px}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><div>CÔNG TY CỔ PHẦN ĐỒNG TIẾN</div><div class="form-code">{escape(form_no)}<br>Số lần sửa đổi: {escape(revision_no)}</div></div>
<div class="heading"><h1>PHIẾU CẤP BÁN THÀNH PHẨM</h1>
<div class="qr"><div class="box">QR</div>{escape(qr_code)}</div>
</div>
<div class="meta">
<div><b>Đơn vị:</b>{escape(_first_value(row, 'Unit'))}</div>
<div><b>Tổ:</b>{escape(_first_value(row, 'Line'))}</div>
<div><b>Mã hàng:</b>{escape(_first_value(row, 'Style'))}</div>
<div><b>Lệnh:</b>{escape(_first_value(row, 'ProductionOrder'))}</div>
<div><b>Mùa:</b>{escape(_first_value(row, 'Season'))}</div>
</div>
<div class="meta2">{escape(receive_date)}{' (nhận BTP)' if receive_date else ''}</div>
<table><thead>
<tr>
<th rowspan="2">Số PO</th>
<th rowspan="2">Số lượng<br>đã vào chuyền</th>
<th rowspan="2">Số lượng<br>đã may ra</th>
<th rowspan="2">Số lượng<br>tồn</th>
<th colspan="5">Cấp bán thành phẩm</th>
</tr>
<tr><th>Số lượng<br>cần cấp</th><th>Màu</th><th>Size</th><th>Số lượng</th><th>Ghi chú</th></tr>
</thead>
<tbody>{''.join(body_rows) if body_rows else '<tr><td colspan="9">Không có dữ liệu</td></tr>'}</tbody>
<tfoot><tr>
<td>Tổng cộng:</td>
<td>{escape(_fmt_number(totals['in_line'], 0))}</td>
<td>{escape(_fmt_number(totals['sewn'], 0))}</td>
<td>{escape(_fmt_number(totals['remaining'], 0))}</td>
<td>{escape(_fmt_number(totals['needed'], 0))}</td>
<td></td><td></td>
<td>{escape(_fmt_number(totals['quantity'], 0))}</td>
<td></td>
</tr></tfoot>
</table>
<div class="section-title">YÊU CẦU TẦN SUẤT GIAO BTP:</div>
<table class="delivery"><thead><tr><th>Số lần giao BTP</th><th>Thời gian giao</th><th>Size/Vóc</th><th>Số lượng</th><th>Ghi chú</th></tr></thead>
<tbody>{delivery_rows}</tbody></table>
<div class="sign-date">{escape(request_date)}</div>
<section class="sign">
<div><div class="role">(P)Giám đốc xí nghiệp</div><div class="name">{escape(_first_value(row, 'FactoryDirector'))}</div></div>
<div><div class="role">Tổ trưởng</div><div class="name">{escape(_first_value(row, 'TeamLeader'))}</div></div>
<div><div class="role">Người đề nghị</div><div class="name">{escape(_first_value(row, 'Requester'))}</div></div>
</section>
</main></body></html>"""


def _wip_outbound_print_html(row: dict) -> str:
    details = [item for item in _json_list(row, "DetailsJson") if isinstance(item, dict)]

    doc_no = _first_value(row, "SoPhieuCapBTP")
    form_no = _first_value(row, "FormNo")
    revision_no = _first_value(row, "RevisionNo")
    qr_code = _first_value(row, "QrCode") or doc_no
    issue_date = _fmt_date_vn_words(row.get("IssueDate"))
    request_date = _fmt_date_vn_words(row.get("RequestDate"))

    body_rows = []
    totals = {"in_line": 0.0, "sewn": 0.0, "remaining": 0.0, "needed": 0.0, "quantity": 0.0}

    def add_total(key: str, value: object) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        totals[key] += number
        return number

    for detail in details:
        in_line = add_total("in_line", detail.get("QuantityInLine"))
        sewn = add_total("sewn", detail.get("QuantitySewn"))
        remaining = add_total("remaining", detail.get("QuantityRemaining"))
        needed = add_total("needed", detail.get("QuantityNeeded"))
        quantity = add_total("quantity", detail.get("Quantity"))
        color = escape(_first_value(detail, "ColorDescription")).replace("\n", "<br>")
        body_rows.append(
            "<tr>"
            f"<td>{escape(_first_value(detail, 'PO'))}</td>"
            f"<td>{escape(_fmt_number(in_line, 0)) if in_line is not None else ''}</td>"
            f"<td>{escape(_fmt_number(sewn, 0)) if sewn is not None else ''}</td>"
            f"<td>{escape(_fmt_number(remaining, 0)) if remaining is not None else ''}</td>"
            f"<td>{escape(_fmt_number(needed, 0)) if needed is not None else ''}</td>"
            f"<td class='color'>{color}</td>"
            f"<td>{escape(_first_value(detail, 'Size'))}</td>"
            f"<td>{escape(_fmt_number(quantity, 0)) if quantity is not None else ''}</td>"
            f"<td>{escape(_first_value(detail, 'Note'))}</td>"
            "</tr>"
        )

    delivery_rows = "".join(
        f"<tr><td>Giao BTP lần {n}</td><td></td><td></td><td></td><td></td></tr>" for n in range(1, 5)
    )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phiếu xuất BTP {escape(doc_no)}</title><style>
@page{{size:A4;margin:10mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:12px Arial,sans-serif}} .sheet{{max-width:1000px;margin:auto}}
.top{{display:flex;justify-content:space-between;align-items:flex-start}} .form-code{{text-align:right;font-size:12px}}
.heading{{text-align:center;margin:10px 0 14px;position:relative}} .heading h1{{margin:0;font-size:22px;letter-spacing:.5px}}
.qr{{position:absolute;right:0;top:-6px;text-align:center;font-size:10px}} .qr .box{{width:64px;height:64px;border:1px dashed #999;display:flex;align-items:center;justify-content:center;font-size:8px;color:#999;margin:0 auto 2px}}
.meta{{display:flex;gap:24px;font-size:12px;margin-bottom:4px}} .meta b{{margin-right:4px}}
.meta2{{font-size:12px;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #333;padding:5px;text-align:center;font-size:11px;vertical-align:middle}} th{{background:#f1f0e8}}
td.color{{text-align:left}} tfoot td{{font-weight:700}} tfoot td:first-child{{text-align:right}}
.section-title{{font-weight:700;margin:14px 0 6px}}
.delivery td:first-child{{text-align:left}}
.sign{{display:grid;grid-template-columns:1fr 1fr 1fr;text-align:center;margin-top:26px;font-size:12px}} .sign .role{{font-weight:700}} .sign .name{{margin-top:40px;font-weight:700}}
.sign-date{{text-align:right;font-weight:700;margin-top:18px;font-size:12px}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><div>CÔNG TY CỔ PHẦN ĐỒNG TIẾN</div><div class="form-code">{escape(form_no)}<br>{f'Số lần sửa đổi: {escape(revision_no)}' if revision_no else ''}</div></div>
<div class="heading"><h1>PHIẾU XUẤT BÁN THÀNH PHẨM</h1>
<div class="qr"><div class="box">QR</div>{escape(qr_code)}</div>
</div>
<div class="meta">
<div><b>Đơn vị:</b>{escape(_first_value(row, 'Unit'))}</div>
<div><b>Tổ:</b>{escape(_first_value(row, 'Line'))}</div>
<div><b>Mã hàng:</b>{escape(_first_value(row, 'Style'))}</div>
<div><b>Lệnh:</b>{escape(_first_value(row, 'ProductionOrder'))}</div>
<div><b>Mùa:</b>{escape(_first_value(row, 'Season'))}</div>
</div>
<div class="meta2">{escape(issue_date)}{' (xuất BTP)' if issue_date else ''}</div>
<table><thead>
<tr>
<th rowspan="2">Số PO</th>
<th rowspan="2">Số lượng<br>đã vào chuyền</th>
<th rowspan="2">Số lượng<br>đã may ra</th>
<th rowspan="2">Số lượng<br>tồn</th>
<th colspan="5">Xuất bán thành phẩm</th>
</tr>
<tr><th>Số lượng<br>xuất</th><th>Màu</th><th>Size</th><th>Số lượng</th><th>Ghi chú</th></tr>
</thead>
<tbody>{''.join(body_rows) if body_rows else '<tr><td colspan="9">Không có dữ liệu</td></tr>'}</tbody>
<tfoot><tr>
<td>Tổng cộng:</td>
<td>{escape(_fmt_number(totals['in_line'], 0))}</td>
<td>{escape(_fmt_number(totals['sewn'], 0))}</td>
<td>{escape(_fmt_number(totals['remaining'], 0))}</td>
<td>{escape(_fmt_number(totals['needed'], 0))}</td>
<td></td><td></td>
<td>{escape(_fmt_number(totals['quantity'], 0))}</td>
<td></td>
</tr></tfoot>
</table>
<div class="section-title">YÊU CẦU TẦN SUẤT GIAO BTP:</div>
<table class="delivery"><thead><tr><th>Số lần giao BTP</th><th>Thời gian giao</th><th>Size/Vóc</th><th>Số lượng</th><th>Ghi chú</th></tr></thead>
<tbody>{delivery_rows}</tbody></table>
<div class="sign-date">{escape(request_date)}</div>
<section class="sign">
<div><div class="role">(P)Giám đốc xí nghiệp</div><div class="name">{escape(_first_value(row, 'FactoryDirector'))}</div></div>
<div><div class="role">Tổ trưởng</div><div class="name">{escape(_first_value(row, 'TeamLeader'))}</div></div>
<div><div class="role">Người đề nghị</div><div class="name">{escape(_first_value(row, 'Requester'))}</div></div>
</section>
</main></body></html>"""


def _wip_to_subcontractor_print_html(row: dict) -> str:
    details = [item for item in _json_list(row, "DetailsJson") if isinstance(item, dict)]

    doc_no = _first_value(row, "DocNo")
    status = _first_value(row, "Status")
    created_date = _fmt_date(row.get("CreatedDate"))

    body_rows = []
    totals = {"out": 0.0, "in": 0.0, "remaining": 0.0}

    def add_total(key: str, value: object) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        totals[key] += number
        return number

    for index, detail in enumerate(details, start=1):
        qty_out = add_total("out", detail.get("QuantityOut"))
        qty_in = add_total("in", detail.get("QuantityIn"))
        qty_remaining = add_total("remaining", detail.get("QuantityRemaining"))
        scan_date, scan_time = _fmt_datetime_parts(detail.get("ScannedOutAt"))
        body_rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{escape(_first_value(detail, 'Barcode'))}</td>"
            f"<td>{escape(_first_value(detail, 'PO'))}</td>"
            f"<td>{escape(_first_value(detail, 'ProductCode'))}</td>"
            f"<td>{escape(_first_value(detail, 'Size'))}</td>"
            f"<td>{escape(_first_value(detail, 'SubcontractType'))}</td>"
            f"<td>{escape(_fmt_number(qty_out, 0)) if qty_out is not None else ''}</td>"
            f"<td>{escape(_fmt_number(qty_in, 0)) if qty_in is not None else ''}</td>"
            f"<td>{escape(_fmt_number(qty_remaining, 0)) if qty_remaining is not None else ''}</td>"
            f"<td>{escape(_first_value(detail, 'ScannedOutBy'))}</td>"
            f"<td>{escape(scan_date)} {escape(scan_time)}</td>"
            f"<td>{escape(_first_value(detail, 'Note'))}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phiếu xuất BTP gia công {escape(doc_no)}</title><style>
@page{{size:A4;margin:10mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:12px Arial,sans-serif}} .sheet{{max-width:1100px;margin:auto}}
.top{{display:flex;justify-content:space-between;align-items:flex-start}}
.heading{{text-align:center;margin:10px 0 14px}} .heading h1{{margin:0;font-size:22px;letter-spacing:.5px}}
.meta{{display:flex;flex-wrap:wrap;gap:24px;font-size:12px;margin-bottom:4px}} .meta b{{margin-right:4px}}
table{{width:100%;border-collapse:collapse;margin-top:10px}} th,td{{border:1px solid #333;padding:5px;text-align:center;font-size:11px;vertical-align:middle}} th{{background:#f1f0e8}}
tfoot td{{font-weight:700}} tfoot td:first-child{{text-align:right}}
.sign{{display:grid;grid-template-columns:1fr 1fr 1fr;text-align:center;margin-top:26px;font-size:12px}} .sign .role{{font-weight:700}} .sign .name{{margin-top:40px;font-weight:700}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><div>CÔNG TY CỔ PHẦN ĐỒNG TIẾN</div><div>{escape(created_date)}</div></div>
<div class="heading"><h1>PHIẾU XUẤT BÁN THÀNH PHẨM GIA CÔNG</h1></div>
<div class="meta">
<div><b>Số phiếu:</b>{escape(doc_no)}</div>
<div><b>Trạng thái:</b>{escape(status)}</div>
<div><b>Lệnh SX:</b>{escape(_first_value(row, 'ProductionOrder'))}</div>
<div><b>Khách hàng:</b>{escape(_first_value(row, 'CustomerCode'))}</div>
</div>
<div class="meta">
<div><b>Đơn vị gia công:</b>{escape(_first_value(row, 'UnitName'))} ({escape(_first_value(row, 'UnitCode'))})</div>
<div><b>Địa chỉ:</b>{escape(_first_value(row, 'UnitAddress'))}</div>
</div>
<table><thead><tr>
<th>STT</th><th>Tem BTP</th><th>PO</th><th>Mã hàng</th><th>Size</th><th>Loại gia công</th>
<th>SL xuất</th><th>SL nhận</th><th>SL còn lại</th><th>Người quét xuất</th><th>Thời gian quét xuất</th><th>Ghi chú</th>
</tr></thead>
<tbody>{''.join(body_rows) if body_rows else '<tr><td colspan="12">Không có dữ liệu</td></tr>'}</tbody>
<tfoot><tr>
<td colspan="6">Tổng cộng:</td>
<td>{escape(_fmt_number(totals['out'], 0))}</td>
<td>{escape(_fmt_number(totals['in'], 0))}</td>
<td>{escape(_fmt_number(totals['remaining'], 0))}</td>
<td colspan="3"></td>
</tr></tfoot>
</table>
<section class="sign">
<div><div class="role">Người lập phiếu</div><div class="name">{escape(_first_value(row, 'CreatedBy'))}</div></div>
<div><div class="role">Thủ kho</div><div class="name"></div></div>
<div><div class="role">Đơn vị gia công nhận hàng</div><div class="name"></div></div>
</section>
</main></body></html>"""


def _wip_scanning_print_html(row: dict) -> str:
    details = [item for item in _json_list(row, "DetailsJson") if isinstance(item, dict)]

    doc_no = _first_value(row, "SoPhieuCapBTP")
    form_no = _first_value(row, "FormNo")
    revision_no = _first_value(row, "RevisionNo")
    qr_code = _first_value(row, "QrCode") or doc_no
    scan_date = _fmt_date_vn_words(row.get("ScanDate"))
    request_date = _fmt_date_vn_words(row.get("RequestDate"))

    body_rows = []
    totals = {"in_line": 0.0, "sewn": 0.0, "remaining": 0.0, "needed": 0.0, "quantity": 0.0}

    def add_total(key: str, value: object) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        totals[key] += number
        return number

    for detail in details:
        in_line = add_total("in_line", detail.get("QuantityInLine"))
        sewn = add_total("sewn", detail.get("QuantitySewn"))
        remaining = add_total("remaining", detail.get("QuantityRemaining"))
        needed = add_total("needed", detail.get("QuantityNeeded"))
        quantity = add_total("quantity", detail.get("Quantity"))
        color = escape(_first_value(detail, "ColorDescription")).replace("\n", "<br>")
        body_rows.append(
            "<tr>"
            f"<td>{escape(_first_value(detail, 'PO'))}</td>"
            f"<td>{escape(_fmt_number(in_line, 0)) if in_line is not None else ''}</td>"
            f"<td>{escape(_fmt_number(sewn, 0)) if sewn is not None else ''}</td>"
            f"<td>{escape(_fmt_number(remaining, 0)) if remaining is not None else ''}</td>"
            f"<td>{escape(_fmt_number(needed, 0)) if needed is not None else ''}</td>"
            f"<td class='color'>{color}</td>"
            f"<td>{escape(_first_value(detail, 'Size'))}</td>"
            f"<td>{escape(_fmt_number(quantity, 0)) if quantity is not None else ''}</td>"
            f"<td>{escape(_first_value(detail, 'Note'))}</td>"
            "</tr>"
        )

    delivery_rows = "".join(
        f"<tr><td>Giao BTP lần {n}</td><td></td><td></td><td></td><td></td></tr>" for n in range(1, 5)
    )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phiếu quét nhận BTP {escape(doc_no)}</title><style>
@page{{size:A4;margin:10mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:12px Arial,sans-serif}} .sheet{{max-width:1000px;margin:auto}}
.top{{display:flex;justify-content:space-between;align-items:flex-start}} .form-code{{text-align:right;font-size:12px}}
.heading{{text-align:center;margin:10px 0 14px;position:relative}} .heading h1{{margin:0;font-size:22px;letter-spacing:.5px}}
.qr{{position:absolute;right:0;top:-6px;text-align:center;font-size:10px}} .qr .box{{width:64px;height:64px;border:1px dashed #999;display:flex;align-items:center;justify-content:center;font-size:8px;color:#999;margin:0 auto 2px}}
.meta{{display:flex;gap:24px;font-size:12px;margin-bottom:4px}} .meta b{{margin-right:4px}}
.meta2{{font-size:12px;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse}} th,td{{border:1px solid #333;padding:5px;text-align:center;font-size:11px;vertical-align:middle}} th{{background:#f1f0e8}}
td.color{{text-align:left}} tfoot td{{font-weight:700}} tfoot td:first-child{{text-align:right}}
.section-title{{font-weight:700;margin:14px 0 6px}}
.delivery td:first-child{{text-align:left}}
.sign{{display:grid;grid-template-columns:1fr 1fr 1fr;text-align:center;margin-top:26px;font-size:12px}} .sign .role{{font-weight:700}} .sign .name{{margin-top:40px;font-weight:700}}
.sign-date{{text-align:right;font-weight:700;margin-top:18px;font-size:12px}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><div>CÔNG TY CỔ PHẦN ĐỒNG TIẾN</div><div class="form-code">{escape(form_no)}<br>{f'Số lần sửa đổi: {escape(revision_no)}' if revision_no else ''}</div></div>
<div class="heading"><h1>PHIẾU QUÉT NHẬN BÁN THÀNH PHẨM</h1>
<div class="qr"><div class="box">QR</div>{escape(qr_code)}</div>
</div>
<div class="meta">
<div><b>Đơn vị:</b>{escape(_first_value(row, 'Unit'))}</div>
<div><b>Tổ:</b>{escape(_first_value(row, 'Line'))}</div>
<div><b>Mã hàng:</b>{escape(_first_value(row, 'Style'))}</div>
<div><b>Lệnh:</b>{escape(_first_value(row, 'ProductionOrder'))}</div>
<div><b>Mùa:</b>{escape(_first_value(row, 'Season'))}</div>
</div>
<div class="meta2">{escape(scan_date)}{' (quét nhận BTP)' if scan_date else ''}</div>
<table><thead>
<tr>
<th rowspan="2">Số PO</th>
<th rowspan="2">Số lượng<br>đã vào chuyền</th>
<th rowspan="2">Số lượng<br>đã may ra</th>
<th rowspan="2">Số lượng<br>tồn</th>
<th colspan="5">Quét nhận bán thành phẩm</th>
</tr>
<tr><th>Số lượng<br>quét nhận</th><th>Màu</th><th>Size</th><th>Số lượng</th><th>Ghi chú</th></tr>
</thead>
<tbody>{''.join(body_rows) if body_rows else '<tr><td colspan="9">Không có dữ liệu</td></tr>'}</tbody>
<tfoot><tr>
<td>Tổng cộng:</td>
<td>{escape(_fmt_number(totals['in_line'], 0))}</td>
<td>{escape(_fmt_number(totals['sewn'], 0))}</td>
<td>{escape(_fmt_number(totals['remaining'], 0))}</td>
<td>{escape(_fmt_number(totals['needed'], 0))}</td>
<td></td><td></td>
<td>{escape(_fmt_number(totals['quantity'], 0))}</td>
<td></td>
</tr></tfoot>
</table>
<div class="section-title">YÊU CẦU TẦN SUẤT GIAO BTP:</div>
<table class="delivery"><thead><tr><th>Số lần giao BTP</th><th>Thời gian giao</th><th>Size/Vóc</th><th>Số lượng</th><th>Ghi chú</th></tr></thead>
<tbody>{delivery_rows}</tbody></table>
<div class="sign-date">{escape(request_date)}</div>
<section class="sign">
<div><div class="role">(P)Giám đốc xí nghiệp</div><div class="name">{escape(_first_value(row, 'FactoryDirector'))}</div></div>
<div><div class="role">Tổ trưởng</div><div class="name">{escape(_first_value(row, 'TeamLeader'))}</div></div>
<div><div class="role">Người đề nghị</div><div class="name">{escape(_first_value(row, 'Requester'))}</div></div>
</section>
</main></body></html>"""


def _fmt_plain(value: object) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value) == int(value) else f"{value:g}"
    return str(value)


def _round_half_up(value: float, decimals: int = 2) -> float:
    quantum = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _endline_severity_bucket(value: object) -> str | None:
    text = str(value or "").strip().upper()
    if text == "NGHIÊM TRỌNG":
        return "critical"
    if text == "NẶNG":
        return "major"
    if text == "NHẸ":
        return "minor"
    return None


def _endline_image_cell(label: str, url: str) -> str:
    body = f"<img src='{escape(url)}' alt='{escape(label)}'>" if url else "<span class='no-image'>Không có ảnh</span>"
    return f"<div class='img-label'>{escape(label)}</div>{body}"


def _endline_print_html(row: dict) -> str:
    tables = [item for item in _json_list(row, "MeasurementTablesJson") if isinstance(item, dict)]
    defects = [item for item in _json_list(row, "DefectsJson") if isinstance(item, dict)]

    doc_no = _first_value(row, "InspectionId")
    form_no = _first_value(row, "FormNo") or "BM 03 HD 10-05"
    revision_no = _first_value(row, "RevisionNo") or "02"
    inspection_date = _fmt_date(row.get("InspectionDate"))

    info_rows = [
        ("SỐ LẦN KIỂM", "InspectionRound"),
        ("NGÀY KIỂM", None),
        ("CÔNG ĐOẠN", "Stage"),
        ("TÊN NHÂN VIÊN", "Inspector"),
        ("XÍ NGHIỆP", "Factory"),
        ("CHUYỀN MAY", "Line"),
        ("KHÁCH HÀNG", "Customer"),
        ("MÃ HÀNG", "Style"),
        ("MÀU", "ColorDescription"),
        ("TỔNG SỐ LƯỢNG CẦN CỨ BÓC MẪU", "LotSize"),
        ("AQL", "AqlTable"),
        ("TỔNG SỐ LƯỢNG BÓC MẪU", "SampleSize"),
        ("GIỚI HẠN CHẤP NHẬN LỖI NẶNG (AC)", "AcLimit"),
        ("GIỚI HẠN CHẤP NHẬN LỖI NHẸ (RE)", "ReLimit"),
        ("GIỚI HẠN CHẤP NHẬN LỖI NGHIÊM TRỌNG (CD)", "CdLimit"),
    ]
    info_html = "".join(
        f"<tr><td class='ilabel'>{escape(label)}</td>"
        f"<td>{escape(inspection_date if key is None else _fmt_plain(row.get(key)))}</td></tr>"
        for label, key in info_rows
    )

    measurement_html = []
    for table_index, table in enumerate(tables, start=1):
        size_label = _first_value(table, "SizeLabel")
        time_slots = [str(slot) for slot in (table.get("TimeSlots") or [])] or ["9h", "11h"]
        rows = [item for item in (table.get("Rows") or []) if isinstance(item, dict)]
        total_cols = 5 + 3 * len(time_slots)

        slot_headers = "".join(f"<th colspan='3'>{escape(slot)}</th>" for slot in time_slots)
        slot_subheaders = "".join("<th></th><th></th><th></th>" for _ in time_slots)

        data_rows = []
        for r in rows:
            groups = r.get("Groups") or []
            group_cells = []
            for slot_index in range(len(time_slots)):
                values = groups[slot_index] if slot_index < len(groups) and isinstance(groups[slot_index], list) else []
                for cell_index in range(3):
                    value = values[cell_index] if cell_index < len(values) else ""
                    group_cells.append(f"<td>{escape(_fmt_plain(value))}</td>")
            data_rows.append(
                "<tr>"
                f"<td class='code'>⚠<br>{escape(_first_value(r, 'Code'))}</td>"
                f"<td class='desc'>{escape(_first_value(r, 'Description'))}</td>"
                f"<td>{escape(_fmt_plain(r.get('Minus')))}</td>"
                f"<td>{escape(_fmt_plain(r.get('Plus')))}</td>"
                f"<td>{escape(_fmt_plain(r.get('Spec')))}</td>"
                f"{''.join(group_cells)}"
                "</tr>"
            )

        measurement_html.append(f"""<table class="measure"><thead>
<tr><th colspan="{total_cols}">BẢNG THÔNG SỐ {table_index}</th></tr>
<tr><th rowspan="2"></th><th rowspan="2">Decription/ vị trí đo</th><th colspan="2">Loại</th><th rowspan="2">{escape(size_label)}</th>{slot_headers}</tr>
<tr><th>-</th><th>+</th>{slot_subheaders}</tr>
</thead><tbody>{''.join(data_rows) if data_rows else f"<tr><td colspan='{total_cols}'>Không có dữ liệu</td></tr>"}</tbody></table>""")

    counts = {"critical": 0.0, "major": 0.0, "minor": 0.0}
    defect_html = []
    for pair_start in range(0, len(defects), 2):
        d1 = defects[pair_start]
        d2 = defects[pair_start + 1] if pair_start + 1 < len(defects) else None
        idx1 = pair_start + 1
        idx2 = pair_start + 2

        for d in (d1, d2):
            if d is None:
                continue
            bucket = _endline_severity_bucket(d.get("Severity"))
            if bucket:
                try:
                    counts[bucket] += float(d.get("Quantity") or 0)
                except (TypeError, ValueError):
                    pass

        def field_row(label1: str, label2: str, key: str) -> str:
            v1 = escape(_first_value(d1, key))
            if d2 is not None:
                v2 = escape(_first_value(d2, key))
                return f"<tr><td class='dlabel'>{label1}</td><td>{v1}</td><td class='dlabel'>{label2}</td><td>{v2}</td></tr>"
            return f"<tr><td class='dlabel'>{label1}</td><td>{v1}</td><td colspan='2'></td></tr>"

        defect_html.append(field_row(f"LỖI {idx1}", f"LỖI {idx2}", "Name"))
        defect_html.append(field_row(f"MỨC ĐỘ {idx1}", f"MỨC ĐỘ {idx2}", "Severity"))
        defect_html.append(field_row(f"VỊ TRÍ LỖI {idx1}", f"VỊ TRÍ LỖI {idx2}", "Location"))
        defect_html.append(field_row(f"SỐ LƯỢNG LỖI {idx1}", f"SỐ LƯỢNG LỖI {idx2}", "Quantity"))
        img1 = _endline_image_cell(f"HÌNH ẢNH {idx1}", _first_value(d1, "ImageUrl"))
        if d2 is not None:
            img2 = _endline_image_cell(f"HÌNH ẢNH {idx2}", _first_value(d2, "ImageUrl"))
            defect_html.append(f"<tr><td colspan='2' class='dimg'>{img1}</td><td colspan='2' class='dimg'>{img2}</td></tr>")
        else:
            defect_html.append(f"<tr><td colspan='2' class='dimg'>{img1}</td><td colspan='2'></td></tr>")

    total_defect_qty = sum(counts.values())
    try:
        sample_size_num = float(row.get("SampleSize"))
    except (TypeError, ValueError):
        sample_size_num = None
    rate = (total_defect_qty / sample_size_num * 100) if sample_size_num else None

    def within_limit(bucket: str, limit_key: str) -> bool:
        try:
            limit_num = float(row.get(limit_key))
        except (TypeError, ValueError):
            return True
        return counts[bucket] <= limit_num

    passed = (
        within_limit("critical", "CdLimit")
        and within_limit("major", "AcLimit")
        and within_limit("minor", "ReLimit")
    )
    result_text = "PASS" if passed else "FAIL"

    non_conformance_note = _first_value(row, "NonConformanceNote")
    signature_url = _first_value(row, "SignatureImageUrl")
    front_image = _first_value(row, "FrontImageUrl")
    back_image = _first_value(row, "BackImageUrl")

    def garment_image(label: str, url: str) -> str:
        return f"<img src='{escape(url)}' alt='{escape(label)}'>" if url else "<span class='no-image'>Không có ảnh</span>"

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Báo cáo Endline {escape(doc_no)}</title><style>
@page{{size:A4;margin:10mm}} *{{box-sizing:border-box}} body{{margin:0;color:#111;font:12px Arial,sans-serif}} .sheet{{max-width:1000px;margin:auto}}
.top{{display:flex;justify-content:space-between;align-items:flex-start}} .logo{{width:44px;height:44px;border-radius:8px;background:#0d3b66;color:#f4c14b;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:20px}}
.heading{{text-align:center}} .heading h1{{margin:0;font-size:22px}} .heading div{{font-size:12px;margin-top:2px}}
.form-code{{text-align:right;font-size:12px;white-space:nowrap}}
table{{width:100%;border-collapse:collapse;margin-top:10px}} th,td{{border:1px solid #333;padding:4px 6px;font-size:11px;vertical-align:middle}}
th{{background:#f1f0e8;text-align:center}} td.ilabel{{font-weight:700;width:38%}} td.code{{text-align:center;width:44px}} td.desc{{text-align:left}}
table.measure td, table.measure th{{text-align:center}} table.measure td.desc{{text-align:left}}
.photo-box{{border:1px solid #333;text-align:center;padding:6px}} .photo-box b{{display:block;background:#f1f0e8;padding:4px;margin:-6px -6px 6px}}
.photo-box img{{max-width:100%;max-height:160px}}
.section-title{{text-align:center;font-weight:700;font-size:16px;margin:16px 0 4px}}
td.dlabel{{font-weight:700;width:20%}} td.dimg{{text-align:center;padding:8px}} .img-label{{font-weight:700;margin-bottom:6px}}
td.dimg img{{max-width:100%;max-height:140px}} .no-image{{color:#999;font-style:italic}}
.nc-title{{text-align:center;font-weight:700;border:1px solid #333;background:#f1f0e8;padding:6px;margin-top:16px}}
.nc-body{{border:1px solid #333;border-top:none;min-height:40px;padding:6px;font-size:11px}}
table.result td:first-child{{font-weight:700;width:60%}} .result-pass{{color:#0a7a2f;font-weight:700}} .result-fail{{color:#c0272d;font-weight:700}}
.signature img{{max-height:60px}}
.actions{{position:fixed;right:12px;top:12px}} button{{border:0;border-radius:6px;background:#172239;padding:8px 14px;color:#fff;cursor:pointer}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="actions"><button onclick="window.print()">In phiếu</button></div><main class="sheet">
<div class="top"><div class="logo">D</div>
<div class="heading"><h1>BÁO CÁO ENDLINE</h1><div>PHÒNG QA - TEAM DFC</div></div>
<div class="form-code">{escape(form_no)}<br>Số lần sửa đổi: {escape(revision_no)}</div>
</div>
<table>{info_html}</table>
<table><tr>
<td class="photo-box" style="width:50%"><b>MẶT TRƯỚC</b>{garment_image('Mặt trước', front_image)}</td>
<td class="photo-box" style="width:50%"><b>MẶT SAU</b>{garment_image('Mặt sau', back_image)}</td>
</tr></table>
<div class="section-title">THÔNG SỐ</div>
{''.join(measurement_html) if measurement_html else '<p>Không có bảng thông số</p>'}
<div class="section-title">CHẤT LƯỢNG</div>
<table class="defects"><tbody>{''.join(defect_html) if defect_html else '<tr><td>Không có lỗi</td></tr>'}</tbody></table>
<div class="nc-title">BIÊN BẢN KIỂM TRA SP KHÔNG PHÙ HỢP (NẾU CÓ)</div>
<div class="nc-body">{escape(non_conformance_note)}</div>
<table class="result">
<tr><td>TỔNG SỐ LỖI NGHIÊM TRỌNG</td><td>{escape(_fmt_plain(counts['critical']))}</td></tr>
<tr><td>TỔNG SỐ LỖI NẶNG</td><td>{escape(_fmt_plain(counts['major']))}</td></tr>
<tr><td>TỔNG SỐ LỖI NHẸ</td><td>{escape(_fmt_plain(counts['minor']))}</td></tr>
<tr><td>TỔNG SỐ LƯỢNG LỖI</td><td>{escape(_fmt_plain(total_defect_qty))}</td></tr>
<tr><td>TỶ LỆ LỖI</td><td>{f"{_round_half_up(rate):.2f}%" if rate is not None else ''}</td></tr>
<tr><td>KẾT QUẢ</td><td class="{'result-pass' if passed else 'result-fail'}">{result_text}</td></tr>
<tr><td>KÝ TÊN</td><td class="signature">{f"<img src='{escape(signature_url)}' alt='Ký tên'>" if signature_url else ''}</td></tr>
</table>
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
    elif document_type == "fabric-relaxing":
        html = _fabric_relaxing_print_html(rows[0])
    elif document_type == "wip-inspection":
        html = _wip_inspection_print_html(rows[0])
    elif document_type == "wip-issuing":
        html = _wip_issuing_print_html(rows[0])
    elif document_type == "wip-outbound":
        html = _wip_outbound_print_html(rows[0])
    elif document_type == "wip-to-subcontractor":
        html = _wip_to_subcontractor_print_html(rows[0])
    elif document_type == "wip-scanning":
        html = _wip_scanning_print_html(rows[0])
    elif document_type == "endline":
        html = _endline_print_html(rows[0])
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
