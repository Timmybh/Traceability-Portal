-- HOÀN TOÀN CHƯA XÁC MINH VỚI DB THẬT.
-- Khác với các mẫu công đoạn 10/12/13/15, "Báo cáo Endline" KHÔNG nằm trong
-- danh sách 15 công đoạn truy xuất hiện có (docs/TRACEABILITY-NEW-QUERY.sql) -
-- đây là một loại phiếu QA hoàn toàn mới, nên CHƯA có bất kỳ bảng/cột nào được
-- xác nhận là thật trong repo này (khác các mẫu trước, mẫu này không tận dụng
-- được cột có sẵn). Toàn bộ bên dưới là khung placeholder để khớp đúng tên cột
-- mà hàm _endline_print_html() trong iis/backend/app/main.py đọc.
--
-- Lưu ý theo yêu cầu: HÌNH ẢNH LỖI (DefectsJson[].ImageUrl) là ảnh lấy từ một
-- THƯ VIỆN ảnh lỗi dùng chung (theo loại lỗi), KHÔNG PHẢI ảnh chụp riêng của
-- lần kiểm này - cần tìm đúng bảng thư viện đó khi có DB (rồi JOIN theo mã lỗi
-- thay vì lưu URL trực tiếp trên từng lần kiểm).
--
-- Cấu trúc DetailsJson liên quan:
--
-- MeasurementTablesJson (mảng, mỗi phần tử là 1 "BẢNG THÔNG SỐ"):
-- {
--   "SizeLabel": "2XL",
--   "TimeSlots": ["9h", "11h"],      -- tên các mốc giờ đo, mỗi mốc render 3 cột mẫu
--   "Rows": [
--     {
--       "Code": "NEs",
--       "Description": "1/2 Stretched neckline minimum 1/2 đường chân cổ kéo giãn tối thiểu",
--       "Minus": 90, "Plus": 90, "Spec": 29.3,
--       "Groups": [["31","32","32"], ["","",""]]   -- 1 mảng con / TimeSlot, tối đa 3 giá trị
--     }
--   ]
-- }
--
-- DefectsJson (mảng, mỗi phần tử là 1 lỗi ghi nhận):
-- {
--   "Name": "LỖI DÍNH DƠ (DÍNH MỰC, SƠN, KEO)",
--   "Severity": "NHẸ",              -- đúng 1 trong 3 giá trị: "NHẸ" | "NẶNG" | "NGHIÊM TRỌNG"
--   "Location": "lai",
--   "Quantity": 1,
--   "ImageUrl": "https://.../defect-library/xxx.jpg"  -- ảnh lấy từ thư viện lỗi, xem lưu ý trên
-- }
--
-- Ghi chú: TỔNG SỐ LỖI NẶNG/NHẸ/NGHIÊM TRỌNG, TỔNG SỐ LƯỢNG LỖI, TỶ LỆ LỖI và
-- KẾT QUẢ (PASS/FAIL) KHÔNG cần SQL tính sẵn - renderer tự cộng dồn theo
-- Severity/Quantity trong DefectsJson rồi so với AcLimit/ReLimit/CdLimit.
SELECT
    CAST(@DocumentId AS nvarchar(255)) AS InspectionId,
    CAST(NULL AS nvarchar(20))  AS InspectionRound,     -- Số lần kiểm, vd "Lần 1"
    CAST(NULL AS datetime2)     AS InspectionDate,      -- Ngày kiểm
    CAST(NULL AS nvarchar(50))  AS Stage,               -- Công đoạn, vd "ENDLINE"
    CAST(NULL AS nvarchar(100)) AS Inspector,           -- Tên nhân viên
    CAST(NULL AS nvarchar(50))  AS Factory,             -- Xí nghiệp
    CAST(NULL AS nvarchar(50))  AS Line,                -- Chuyền may
    CAST(NULL AS nvarchar(100)) AS Customer,            -- Khách hàng
    CAST(NULL AS nvarchar(100)) AS Style,               -- Mã hàng
    CAST(NULL AS nvarchar(255)) AS ColorDescription,    -- Màu
    CAST(NULL AS nvarchar(50))  AS LotSize,             -- Tổng số lượng cần cứ bóc mẫu
    CAST(NULL AS nvarchar(50))  AS AqlTable,            -- vd "AQL Table G-1"
    CAST(NULL AS nvarchar(50))  AS SampleSize,          -- Tổng số lượng bóc mẫu
    CAST(NULL AS nvarchar(20))  AS AcLimit,             -- Giới hạn chấp nhận lỗi nặng
    CAST(NULL AS nvarchar(20))  AS ReLimit,             -- Giới hạn chấp nhận lỗi nhẹ
    CAST(NULL AS nvarchar(20))  AS CdLimit,             -- Giới hạn chấp nhận lỗi nghiêm trọng
    CAST(NULL AS nvarchar(500)) AS FrontImageUrl,       -- Ảnh mặt trước (rập/kỹ thuật)
    CAST(NULL AS nvarchar(500)) AS BackImageUrl,        -- Ảnh mặt sau
    CAST(NULL AS nvarchar(20))  AS FormNo,              -- mặc định "BM 03 HD 10-05" nếu NULL
    CAST(NULL AS nvarchar(10))  AS RevisionNo,          -- mặc định "02" nếu NULL
    CAST(NULL AS nvarchar(500)) AS SignatureImageUrl,   -- Ảnh chữ ký (nếu có)
    CAST(NULL AS nvarchar(max)) AS NonConformanceNote,  -- Biên bản KT SP không phù hợp (nếu có)
    CAST(N'[]' AS nvarchar(max)) AS MeasurementTablesJson,  -- TODO: xem cấu trúc ở trên
    CAST(N'[]' AS nvarchar(max)) AS DefectsJson             -- TODO: xem cấu trúc ở trên
WHERE 1 = 0; -- TODO: chưa rõ bảng nguồn "Báo cáo Endline" - bỏ WHERE 1=0 khi đã có bảng thật
