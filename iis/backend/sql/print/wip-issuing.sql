-- Đã xác minh trực tiếp trên DB thật (2026-09-05), đối chiếu với mẫu in thực tế
-- của phiếu 2608002186 (BM 09 HD 10-02):
--   dbo.CUTTING_PhieuCapBTP: NguoiTao khớp "Người đề nghị", NguoiGui khớp
--   "Tổ trưởng", NguoiDuyet khớp "(P)Giám đốc xí nghiệp". NgayTao khớp đúng
--   ngày ký cuối mẫu (khác NgayDuyet - đó là ngày duyệt, dùng cho StepDate của
--   công đoạn 12 trong docs/TRACEABILITY-NEW-QUERY.sql, không phải ngày ở đây).
--   dbo.CUTTING_PhieuCapBTP_ChiTiet: SoLuongDaVaoChuyen/SoLuongMayRa/SoLuongTon
--   khớp đúng 3 cột đầu bảng; SoLuongCanCap khớp đúng "Số lượng cần cấp";
--   SoLuong khớp cột "Số lượng" cuối bảng.
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
    master.NgayTao AS RequestDate,
    CAST(NULL AS nvarchar(50))  AS Unit,               -- Đơn vị (vd "1") - chưa rõ nguồn
    CAST(NULL AS nvarchar(20))  AS FormNo,              -- vd "BM 09 HD 10-02" (renderer tự điền mặc định nếu NULL)
    CAST(NULL AS nvarchar(10))  AS RevisionNo,          -- Số lần sửa đổi (renderer mặc định "01" nếu NULL)
    CAST(NULL AS nvarchar(50))  AS QrCode,              -- renderer mặc định dùng SoPhieuCapBTP nếu NULL
    master.NguoiDuyet AS FactoryDirector,        -- (P)Giám đốc xí nghiệp
    master.NguoiGui AS TeamLeader,               -- Tổ trưởng
    master.NguoiTao AS Requester,                -- Người đề nghị
    JSON_QUERY((
        SELECT
            detail.PO,
            detail.SizeCode AS Size,
            detail.TenMau AS ColorDescription,
            detail.SoLuongDaVaoChuyen AS QuantityInLine,
            detail.SoLuongMayRa AS QuantitySewn,
            detail.SoLuongTon AS QuantityRemaining,
            detail.SoLuongCanCap AS QuantityNeeded,
            detail.SoLuong AS Quantity,
            detail.GhiChu AS Note
        FROM dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
        WHERE detail.IdCapBTP = master.IdCapBTP
        ORDER BY detail.Id
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.CUTTING_PhieuCapBTP AS master
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), master.SoPhieuCapBTP))) = @DocumentId;
