-- CHƯA XÁC MINH ĐẦY ĐỦ VỚI DB THẬT.
-- Mẫu in này dựng "giống Phiếu xuất BTP công đoạn 13" (xem wip-outbound.sql)
-- theo yêu cầu, dùng lại đúng cấu trúc DetailsJson để các mẫu khớp layout.
-- Cùng khóa SoPhieuCapBTP với công đoạn 12/13 (xem docs/TRACEABILITY-NEW-QUERY.sql,
-- nhánh "wipOutbound" dùng chung cap.SoPhieuCapBTP cho cả bước 13 "Xuất BTP" lẫn
-- bước 15 "Quét nhận BTP").
--
-- LƯU Ý QUAN TRỌNG cần xác nhận khi có DB: bảng gốc trước khi sửa là
-- dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet (bảng CÓ THẬT, đã dùng ở
-- docs/TRACEABILITY-NEW-QUERY.sql với các cột xác nhận: SoPhieuCapBTP, PO,
-- IdCapBTPCT, Lot, ChungLoai, TraBTP, ThoiGianQuetXuat, IdPhieuXuatKhoBTP,
-- TemBarcodeBTP), tức bước "quét nhận" rất có thể phải lấy chi tiết THEO TỪNG
-- BARCODE đã quét (ThoiGianQuetXuat) chứ không phải theo PO/size tổng hợp như
-- đang để tạm ở đây. Khi có DB, đối chiếu lại và đổi JOIN detail nếu cần.
--
-- Cấu trúc 1 phần tử DetailsJson (giữ giống wip-outbound.sql):
-- {
--   "PO": "4524260955",
--   "Size": "UK10/EUM",
--   "ColorDescription": "8974285 T-SHIRT MH500 F VERT CEDAR FLEUR",
--   "QuantityInLine": 0, "QuantitySewn": 0, "QuantityRemaining": 0,
--   "QuantityNeeded": 130,   -- ở mẫu này là "Số lượng quét nhận"
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
    master.NgayNhanBTP AS ScanDate,             -- TODO: xác nhận đúng nguồn ngày quét nhận thực tế
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
            CAST(NULL AS decimal(18, 2)) AS QuantityNeeded,     -- TODO: chưa rõ nguồn (Số lượng quét nhận)
            CAST(NULL AS decimal(18, 2)) AS Quantity,           -- TODO: chưa rõ nguồn
            CAST(NULL AS nvarchar(255)) AS Note
        FROM dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
        WHERE detail.IdCapBTP = master.IdCapBTP
        ORDER BY detail.Id
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.CUTTING_PhieuCapBTP AS master
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), master.SoPhieuCapBTP))) = @DocumentId;
