# Web Truy suất — triển khai IIS

## Kiến trúc

- IIS phục vụ frontend tĩnh tại port `8374`.
- IIS URL Rewrite + ARR chuyển `/api/*` đến FastAPI tại `127.0.0.1:8000`.
- FastAPI gọi SQL Server bằng `pyodbc` và câu truy vấn trong `.env`.
- Backend tải ảnh nội bộ và stream về cùng tên miền.
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

Lần đầu script tạo `C:\Apps\WebTruySuat\backend\.env`. Điền `SQLSERVER_HOST`, `SQLSERVER_USER`, `SQLSERVER_PASSWORD`, giữ nguyên hai câu query rồi chạy lại script.

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
