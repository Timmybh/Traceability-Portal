-- CHƯA XÁC MINH ĐẦY ĐỦ VỚI DB THẬT (viết lúc DB đang off).
-- Các cột sau đã dùng và xác nhận đúng ở nơi khác trong hệ thống
-- (xem docs/TRACEABILITY-NEW-QUERY.sql, nhánh "cap"/"wipOrder"):
--   CUTTING_PhieuCapBTP: SoPhieuCapBTP, IdCapBTP, ProductCode, TenXiNghiep,
--                        TenPhanXuong, TenCum, SeasonCode, LenhSanXuat,
--                        NgayDuyet, NgayNhanBTP, NgayTao
--   CUTTING_PhieuCapBTP_ChiTiet: IdCapBTP (FK), Id, PO, SizeCode, TenMau
-- Các cột số lượng (đã vào chuyền/đã may ra/tồn/cần cấp/số lượng cấp) và người ký
-- (Giám đốc xí nghiệp/Tổ trưởng/Người đề nghị) CHƯA rõ nguồn - đang để NULL,
-- cần bổ sung khi có DB. GIỮ NGUYÊN TÊN CỘT OUTPUT vì hàm
-- _wip_issuing_print_html() trong iis/backend/app/main.py đọc đúng các tên này
-- để render mẫu BM 09 HD 10-02.
--
-- Cấu trúc 1 phần tử của DetailsJson:
-- {
--   "PO": "4524260955",
--   "Size": "UK10/EUM",
--   "ColorDescription": "8974285 T-SHIRT MH500 F VERT CEDAR FLEUR",
--   "QuantityInLine": 0,      -- Số lượng đã vào chuyền
--   "QuantitySewn": 0,        -- Số lượng đã may ra
--   "QuantityRemaining": 0,   -- Số lượng tồn
--   "QuantityNeeded": 130,    -- Số lượng cần cấp
--   "Quantity": 130,          -- Số lượng cấp (cột "Số lượng" trong nhóm Cấp BTP)
--   "Note": ""
-- }
SELECT
    master.SoPhieuCapBTP,
    master.IdCapBTP,
    master.ProductCode AS Style,
    master.SeasonCode AS Season,
    master.LenhSanXuat AS ProductionOrder,
    COALESCE(NULLIF(LTRIM(RTRIM(master.TenXiNghiep)), N''), NULLIF(LTRIM(RTRIM(master.TenPhanXuong)), N'')) AS Factory,
    master.TenCum AS Line,                      -- TODO: xác nhận đây đúng là "Tổ" trong mẫu hay không
    master.NgayNhanBTP AS ReceiveDate,
    master.NgayDuyet AS RequestDate,
    CAST(NULL AS nvarchar(50))  AS Unit,               -- Đơn vị (vd "1") - chưa rõ nguồn
    CAST(NULL AS nvarchar(20))  AS FormNo,              -- vd "BM 09 HD 10-02" (renderer tự điền mặc định nếu NULL)
    CAST(NULL AS nvarchar(10))  AS RevisionNo,          -- Số lần sửa đổi (renderer mặc định "01" nếu NULL)
    CAST(NULL AS nvarchar(50))  AS QrCode,              -- renderer mặc định dùng SoPhieuCapBTP nếu NULL
    CAST(NULL AS nvarchar(100)) AS FactoryDirector,     -- (P)Giám đốc xí nghiệp
    CAST(NULL AS nvarchar(100)) AS TeamLeader,          -- Tổ trưởng
    CAST(NULL AS nvarchar(100)) AS Requester,           -- Người đề nghị
    JSON_QUERY((
        SELECT
            detail.PO,
            detail.SizeCode AS Size,
            detail.TenMau AS ColorDescription,
            CAST(NULL AS decimal(18, 2)) AS QuantityInLine,     -- TODO: chưa rõ nguồn
            CAST(NULL AS decimal(18, 2)) AS QuantitySewn,       -- TODO: chưa rõ nguồn
            CAST(NULL AS decimal(18, 2)) AS QuantityRemaining,  -- TODO: chưa rõ nguồn
            CAST(NULL AS decimal(18, 2)) AS QuantityNeeded,     -- TODO: chưa rõ nguồn
            CAST(NULL AS decimal(18, 2)) AS Quantity,           -- TODO: chưa rõ nguồn (có thể = QuantityNeeded)
            CAST(NULL AS nvarchar(255)) AS Note
        FROM dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
        WHERE detail.IdCapBTP = master.IdCapBTP
        ORDER BY detail.Id
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.CUTTING_PhieuCapBTP AS master
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), master.SoPhieuCapBTP))) = @DocumentId;
