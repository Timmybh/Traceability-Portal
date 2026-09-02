# Kết nối SQL Server

Nguồn dữ liệu đã xác định:

- Database: `eGMF`
- Bảng ánh xạ RFID: `dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping`
- Đơn đặt hàng: `dbo.Bravo_DonDatHangBan_Master`
- Khách hàng: `dbo.Lib_KhachHang`
- Khóa tra cứu: `RFID`
- Tab RFID hiện tại dùng `SQLQUERY`; tab RFID mới dùng `SQLQUERY_NEW` qua endpoint `/api/traceability/new`. Query mới nối `CUTTING_TemBarcode_TachCay_RFID_Mapping.BarcodeTachCay` với `CUTTING_TemBarcode_TachCay.Code`, không nối với cột `Barcode`. Query mới không đọc bất kỳ bảng tracking nào và tạm trả timeline rỗng.

Trình duyệt sẽ gọi API trung gian. API chạy trong mạng nội bộ, đọc câu lệnh từ `SQLQUERY`, bind giá trị RFID vào tham số `@RFID` rồi trả JSON cho giao diện. Không nối trực tiếp RFID vào chuỗi SQL. Tài khoản SQL Server chỉ nằm trong `.env` của backend, tuyệt đối không đưa vào frontend.

Mỗi lần đọc dữ liệu, backend đặt transaction isolation level là `READ COMMITTED`. Không thêm `WITH (NOLOCK)` hoặc `READUNCOMMITTED` vào `SQLQUERY`, vì các hint này có thể trả dữ liệu bẩn hoặc không nhất quán.

Giá trị cấu hình:

```dotenv
SQLQUERY=select top (1) mp.RFID, kh.TenNgan, so.PO, so.ProductCode, kh.MaKhachHang from [eGMF].[dbo].[CUTTING_TemBarcode_TachCay_RFID_Mapping] mp inner join [eGMF].[dbo].[Bravo_DonDatHangBan_Master] so on mp.po = so.po inner join [dbo].[Lib_KhachHang] kh on so.CustomerCode = kh.MaKhachHang where mp.RFID = @RFID
```

Kết quả đầu tiên trả về 5 trường: `RFID`, `TenNgan`, `PO`, `ProductCode`, `MaKhachHang`.

## Tách luồng tải hình ảnh

Không trả dữ liệu ảnh trong API tra cứu chính. Hai luồng hoạt động độc lập:

1. `GET /api/traceability?rfid=...` chạy `SQLQUERY` và trả dữ liệu chữ trước.
2. `GET /api/traceability/image?rfid=...` tải ảnh riêng sau khi dữ liệu chính đã hiển thị.

Frontend phải lazy-load ảnh, hiển thị trạng thái đang tải/không có ảnh/lỗi ảnh và không được chặn phần thông tin chung. API ảnh cần hỗ trợ cache HTTP; nếu ảnh đang lưu dạng binary trong SQL Server thì backend chỉ đọc ở endpoint ảnh.

Tab RFID hiện tại lấy URL mặt trước/mặt sau từ `Tracking_RFID_Master_Image` ngay trong `SQLQUERY`. Backend loại hai URL khỏi JSON trả về, chỉ giữ metadata ngắn hạn để endpoint ảnh stream riêng. Vì frontend render dữ liệu chung trước rồi mới tải ảnh nền, tốc độ file server không chặn phần thông tin truy suất.

Tab RFID mới dùng cùng cơ chế: URL ảnh được lấy từ `Tracking_RFID_Master_Image` ngay trong `SQLQUERY_NEW`, với điều kiện `image.RFID = mp.RFID`. Không cần cấu hình `SQLQUERY_IMAGE` hoặc `SQLQUERY_IMAGE_NEW` trong `.env`.

Công đoạn 03 “Nhập kho NPL” đi theo chuỗi khóa nghiệp vụ: RFID lấy PO, mã hàng và barcode tách cây từ `CUTTING_TemBarcode_TachCay_RFID_Mapping`; barcode nối `CUTTING_TemBarcode_TachCay.Code` để lấy mùa; PO, mã hàng và mùa nối `Bravo_BCD_Detail_PO` để lấy `IdDetail`; `IdDetail` nối `Bravo_BCD_Detail.Id` để lấy `DocNo`; cuối cùng `DocNo` nối `Bravo_PNK_Detail.BalanceNo` và `PNKMasterId` nối `Bravo_PNK_Master.Id` để lấy phiếu nhập. Link xem phiếu dùng `Bravo_PNK_Master.Id`.

```dotenv
HOSTFILE=10.8.0.72:9231
IMAGE_TIMEOUT_SECONDS=15
```

Quy ước tên file:

- `MT.jpg`: mặt trước.
- `MS.jpg`: mặt sau.

Backend không trả URL nội bộ thẳng cho trình duyệt. Backend xác thực host trong allow-list, tải ảnh từ URL lưu trong SQL rồi stream qua endpoint cùng nguồn như `/api/traceability/image?rfid=...&side=front`. Cách này tránh mixed-content khi website chạy HTTPS và ngăn URL trong database bị lợi dụng để truy cập host ngoài danh sách cho phép.
