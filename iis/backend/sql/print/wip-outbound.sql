-- CHƯA XÁC MINH ĐẦY ĐỦ VỚI DB THẬT.
-- Mẫu in này dựng "giống Phiếu đặt BTP công đoạn 12" (xem wip-issuing.sql) theo
-- yêu cầu, dùng lại đúng cấu trúc DetailsJson để 2 mẫu khớp layout. Cùng khóa
-- SoPhieuCapBTP với công đoạn 12 (xem docs/TRACEABILITY-NEW-QUERY.sql, nhánh
-- "wipOutbound" dùng chung cap.SoPhieuCapBTP / cap.NgayNhanBTP cho cả bước 13
-- "Xuất BTP" lẫn bước 15 "Quét nhận BTP").
--
-- LƯU Ý QUAN TRỌNG cần xác nhận khi có DB: đây là bước "xuất" (đã có giao dịch
-- thật), rất có thể chi tiết đúng phải lấy theo TỪNG BARCODE đã quét xuất từ
-- dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet (bảng này CÓ THẬT - đã dùng ở
-- docs/TRACEABILITY-NEW-QUERY.sql với các cột xác nhận: SoPhieuCapBTP, PO,
-- IdCapBTPCT [FK sang CUTTING_PhieuCapBTP_ChiTiet.Id], Lot, ChungLoai, TraBTP,
-- ThoiGianQuetXuat, IdPhieuXuatKhoBTP, TemBarcodeBTP) thay vì lấy theo PO/size
-- tổng hợp như công đoạn 12. Khi có DB, cân nhắc đổi JOIN detail bên dưới sang
-- bảng đó nếu form thật xuất theo barcode.
--
-- Cấu trúc 1 phần tử DetailsJson (giữ giống wip-issuing.sql):
-- {
--   "PO": "4524260955",
--   "Size": "UK10/EUM",
--   "ColorDescription": "8974285 T-SHIRT MH500 F VERT CEDAR FLEUR",
--   "QuantityInLine": 0, "QuantitySewn": 0, "QuantityRemaining": 0,
--   "QuantityNeeded": 130,   -- ở mẫu xuất, đây là "Số lượng xuất"
--   "Quantity": 130,
--   "Note": ""
-- }
SELECT
    master.SoPhieuCapBTP,
    master.IdCapBTP,
    master.ProductCode AS Style,
    master.SeasonCode AS Season,
    master.LenhSanXuat AS ProductionOrder,
    COALESCE(NULLIF(LTRIM(RTRIM(master.TenXiNghiep)), N''), NULLIF(LTRIM(RTRIM(master.TenPhanXuong)), N'')) AS Factory,
    master.TenCum AS Line,                     -- TODO: xác nhận đây đúng là "Tổ" trong mẫu hay không
    master.NgayNhanBTP AS IssueDate,            -- TODO: xác nhận đúng là ngày xuất thực tế hay chỉ là ngày nhận kế hoạch
    master.NgayDuyet AS RequestDate,
    CAST(NULL AS nvarchar(50))  AS Unit,               -- Đơn vị - chưa rõ nguồn
    CAST(NULL AS nvarchar(20))  AS FormNo,              -- mã BM - CHƯA có tham chiếu ảnh mẫu, để trống thay vì đoán
    CAST(NULL AS nvarchar(10))  AS RevisionNo,
    CAST(NULL AS nvarchar(50))  AS QrCode,              -- renderer mặc định dùng SoPhieuCapBTP nếu NULL
    CAST(NULL AS nvarchar(100)) AS FactoryDirector,
    CAST(NULL AS nvarchar(100)) AS TeamLeader,
    CAST(NULL AS nvarchar(100)) AS Requester,
    JSON_QUERY((
        SELECT
            detail.PO,
            detail.SizeCode AS Size,
            detail.TenMau AS ColorDescription,
            CAST(NULL AS decimal(18, 2)) AS QuantityInLine,     -- TODO: chưa rõ nguồn
            CAST(NULL AS decimal(18, 2)) AS QuantitySewn,       -- TODO: chưa rõ nguồn
            CAST(NULL AS decimal(18, 2)) AS QuantityRemaining,  -- TODO: chưa rõ nguồn
            CAST(NULL AS decimal(18, 2)) AS QuantityNeeded,     -- TODO: chưa rõ nguồn (Số lượng xuất)
            CAST(NULL AS decimal(18, 2)) AS Quantity,           -- TODO: chưa rõ nguồn
            CAST(NULL AS nvarchar(255)) AS Note
        FROM dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
        WHERE detail.IdCapBTP = master.IdCapBTP
        ORDER BY detail.Id
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.CUTTING_PhieuCapBTP AS master
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), master.SoPhieuCapBTP))) = @DocumentId;
