-- Đã xác minh trực tiếp trên DB thật (2026-09-05), đối chiếu với mẫu in thực tế
-- của phiếu 2608002186:
--   dbo.CUTTING_PhieuCapBTP: NguoiTao, NguoiGui, NguoiDuyet đúng là 3 người ký
--   ("Người đề nghị" = NguoiTao, "Tổ trưởng" = NguoiGui, "(P)Giám đốc xí nghiệp" = NguoiDuyet).
--   dbo.CUTTING_PhieuCapBTP_ChiTiet: SoLuongDaVaoChuyen/SoLuongMayRa/SoLuongTon
--   khớp đúng 3 cột đầu bảng; SoLuongThucXuat là số lượng ĐÃ XUẤT THỰC TẾ (khác
--   SoLuongCanCap dùng cho mẫu "Đặt BTP"/wip-issuing.sql); SoLuong là cột
--   "Số lượng" cuối bảng, giống nhau ở cả 2 mẫu.
--
-- Cấu trúc 1 phần tử DetailsJson:
-- {
--   "PO": "4524260955",
--   "Size": "UK10/EUM",
--   "ColorDescription": "8974285 T-SHIRT MH500 F VERT CEDAR FLEUR",
--   "QuantityInLine": 0, "QuantitySewn": 0, "QuantityRemaining": 0,
--   "QuantityNeeded": 130,   -- ở mẫu xuất, đây là "Số lượng xuất" (SoLuongThucXuat)
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
    master.NguoiDuyet AS FactoryDirector,
    master.NguoiGui AS TeamLeader,
    master.NguoiTao AS Requester,
    JSON_QUERY((
        SELECT
            detail.PO,
            detail.SizeCode AS Size,
            detail.TenMau AS ColorDescription,
            detail.SoLuongDaVaoChuyen AS QuantityInLine,
            detail.SoLuongMayRa AS QuantitySewn,
            detail.SoLuongTon AS QuantityRemaining,
            detail.SoLuongThucXuat AS QuantityNeeded,
            detail.SoLuong AS Quantity,
            detail.GhiChu AS Note
        FROM dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
        WHERE detail.IdCapBTP = master.IdCapBTP
        ORDER BY detail.Id
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.CUTTING_PhieuCapBTP AS master
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), master.SoPhieuCapBTP))) = @DocumentId;
