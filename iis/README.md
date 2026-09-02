# Web Truy suất — triển khai IIS

## Kiến trúc

- IIS phục vụ frontend tĩnh tại port `8374`.
- IIS URL Rewrite + ARR chuyển `/api/*` đến FastAPI tại `127.0.0.1:8000`.
- FastAPI bind RFID vào tham số `@RFID` của `SQLQUERY`, đọc thông tin chung và timeline từ SQL Server.
- Sau khi dữ liệu chính trả về, frontend tải song song ảnh mặt trước/mặt sau qua API ảnh riêng; backend stream ảnh nội bộ về cùng tên miền.
- NSSM chạy backend dưới service `TraceabilityPortalBackend`, tự khởi động cùng Windows. IIS site và App Pool dùng tên `Traceability-Portal`.

## Yêu cầu Windows Server

- IIS với Static Content.
- IIS URL Rewrite 2 và Application Request Routing (ARR).
- Python 3.12 x64.
- Microsoft ODBC Driver 18 for SQL Server.
- NSSM tại `D:\Tools\nssm\nssm.exe` hoặc truyền `-NssmExe`.

## Triển khai

Mở PowerShell bằng **Run as administrator**:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\iis\deploy\windows\deploy-iis.ps1
```

Lần đầu script tạo `D:\Apps\Traceability-Portal\backend\.env`. Điền `SQLSERVER_HOST`, `SQLSERVER_USER`, `SQLSERVER_PASSWORD`, giữ nguyên các câu query rồi chạy lại script. Frontend được triển khai tại `C:\inetpub\wwwroot\Traceability-Portal`. Các lần deploy sau, script tự đồng bộ `SQLQUERY`, `SQLQUERY_NEW`, `SQLQUERY_IMAGE`, `SQLQUERY_PO` và `SQLQUERY_LOT` từ source mới; thông tin đăng nhập được giữ nguyên.

`SQLQUERY` phục vụ tab Truy suất RFID từ các bảng tracking. `SQLQUERY_NEW` phục vụ tab Truy suất RFID mới qua endpoint `/api/traceability/new`: RFID bắt đầu từ `CUTTING_TemBarcode_TachCay_RFID_Mapping`, nối `CUTTING_TemBarcode_TachCay.Code` để lấy thông tin. Tab mới không sử dụng bảng `Tracking_RFID_*`. Bàn cắt dùng `INNER JOIN` từ `CUTTING_TemBarcode_TachCay.IdBanMay` sang `Cutting_PhieuDieuTietGiacSoDo_ChiTiet_BanMay.IdBanMay` và lấy trực tiếp `bm.BanCat`. Phiếu cấp BTP được nối theo mã hàng, PO và size để lấy xí nghiệp, chuyền, màu và LOT chính. LOT phối nối trực tiếp `CUTTING_PhieuCapBTP_BarcodeChiTiet.TemBarcodeBTP = CUTTING_TemBarcode_TachCay.Barcode`, lọc `ChungLoai` chứa “phối”, rồi ghép các LOT bằng `STRING_AGG`. `CUTTING_TemBarcode_TachCay.Lot` chỉ là dự phòng khi phiếu cấp không có LOT chính. Ngày may lấy từ `ThoiGianMap` và chỉ hiển thị ngày. Item và Art đang chờ xác định nguồn đúng. Công đoạn 01 “Phát triển sản phẩm” lấy danh sách tài liệu từ `TEC_ThongTinTaiLieukyThuat`, nối `TEC_ProductInformation.Id = TEC_ThongTinTaiLieukyThuat.IdMaster`, lọc chính xác theo `ProductCode` và `SeasonCode`; tên loại tài liệu được bổ sung từ `TEC_LoaiTaiLieuKyThuat` khi có. Nút preview gọi `/api/traceability/document?id=...`; backend xác thực tài liệu trong SQL, ghép đường dẫn DB vào `http://{HOSTFILE}/PhieuDieTiet`, tải PDF/ảnh qua HTTP file service rồi stream cùng nguồn với chế độ `inline` để trình duyệt mở trong tab mới.

Preview phiếu nghiệp vụ từ công đoạn 02 trở đi gọi `/api/traceability/print/{document_type}?id=...`. Danh sách loại phiếu được whitelist trong `_PRINT_QUERY_TYPES`; mỗi loại đọc một câu SQL tham số hóa riêng tại `iis/backend/sql/print`. Trang HTML hiện tại là mẫu in tạm để kiểm tra dữ liệu master/detail và sẽ được thay bằng mẫu chính thức của từng loại phiếu. Công đoạn 01 không dùng registry này vì tiếp tục preview trực tiếp PDF/ảnh.

Named instance:

```env
SQLSERVER_HOST=TEN-SERVER\TEN-INSTANCE
```

Host và port:

```env
SQLSERVER_HOST=10.8.0.80
SQLSERVER_PORT=1433
```

## Kiểm tra

```powershell
.\iis\deploy\windows\test-deployment.ps1
```

Trang web: `http://SERVER-IP:8374/?rfid=(01)03608393748683(21)000000092192`

## Bảo mật

- Không commit `.env` thật.
- Tài khoản SQL chỉ cần quyền `SELECT` trên ba bảng liên quan.
- Backend chỉ tải ảnh và tài liệu từ `HOSTFILE`.
- FastAPI chỉ nghe tại `127.0.0.1`.
