# Web Truy suất — triển khai IIS

## Kiến trúc

- IIS phục vụ frontend tĩnh tại port `8374`.
- IIS URL Rewrite + ARR chuyển `/api/*` đến FastAPI tại `127.0.0.1:8000`.
- FastAPI bind RFID vào tham số `@RFID` của `SQLQUERY`, đọc thông tin chung và timeline từ SQL Server.
- Sau khi dữ liệu chính trả về, frontend tải song song ảnh mặt trước/mặt sau qua API ảnh riêng; backend stream ảnh nội bộ về cùng tên miền.
- NSSM chạy backend như Windows Service, tự khởi động cùng Windows.

## Yêu cầu Windows Server

- IIS với Static Content.
- IIS URL Rewrite 2 và Application Request Routing (ARR).
- Python 3.12 x64.
- Microsoft ODBC Driver 18 for SQL Server.
- NSSM tại `C:\Tools\nssm\nssm.exe` hoặc truyền `-NssmExe`.

## Triển khai

Mở PowerShell bằng **Run as administrator**:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\iis\deploy\windows\deploy-iis.ps1
```

Lần đầu script tạo `C:\Apps\WebTruySuat\backend\.env`. Điền `SQLSERVER_HOST`, `SQLSERVER_USER`, `SQLSERVER_PASSWORD`, giữ nguyên các câu query rồi chạy lại script. Các lần deploy sau, script tự đồng bộ `SQLQUERY`, `SQLQUERY_NEW`, `SQLQUERY_IMAGE`, `SQLQUERY_PO` và `SQLQUERY_LOT` từ source mới; thông tin đăng nhập được giữ nguyên.

`SQLQUERY` phục vụ tab Truy suất RFID; `SQLQUERY_NEW` phục vụ tab Truy suất RFID mới qua endpoint `/api/traceability/new`. Cả hai trả đúng một dòng và đóng gói tiến trình trong `TimelineJson`. `SQLQUERY_IMAGE` chạy riêng để việc tải ảnh không chặn thông tin chung và tiến trình. `SQLQUERY_PO` và `SQLQUERY_LOT` chỉ nhận truy vấn chính xác khi Khách hàng cùng PO/LOT đều có dữ liệu.

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
- Backend chỉ tải ảnh từ `IMAGE_ALLOWED_HOST`.
- FastAPI chỉ nghe tại `127.0.0.1`.
