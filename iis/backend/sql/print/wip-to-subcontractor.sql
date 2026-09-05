-- Công đoạn 14 "Xuất BTP gia công" (WIP to Subcontractor).
-- Đã xác minh trực tiếp trên DB thật (schema + dữ liệu mẫu, 2026-09-05):
--   - dbo.CUTTING_PhieuGiaCongXuatKho: phiếu xuất BTP cho đơn vị gia công ngoài,
--     khóa tra cứu là MaPhieu (vd "GRCBTP26090500002"), không phải Id nội bộ.
--   - dbo.CUTTING_PhieuGiaCongXuatKho_DaQuet: chi tiết từng tem BTP đã quét xuất,
--     nối bằng IdPhieuGiaCong = master.PhieuGiaCongXuatKhoId.
--   - dbo.Lib_DonViGiaCong: danh mục đơn vị gia công, khóa nối là
--     MaDVGC = master.DonVi (đã kiểm chứng: DonVi trong phiếu thật dùng đúng mã
--     trong Lib_DonViGiaCong, ví dụ "XN1".."XN4").
-- Enrichment PO/Size/MaHang cho từng tem lấy qua dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet
-- (khớp TemBarcodeBTP = detail.TemBarCodeBTP). Đã kiểm chứng có overlap thật giữa
-- hai bảng (không phải lúc nào cũng có: ETL đồng bộ có độ trễ), nên dùng OUTER APPLY
-- và chấp nhận NULL khi tem chưa được đồng bộ sang bảng CapBTP.
SELECT
    master.MaPhieu AS DocNo,
    master.PhieuGiaCongXuatKhoId AS DocId,
    master.TrangThai AS Status,
    master.LenhSanXuat AS ProductionOrder,
    master.CustomerCode AS CustomerCode,
    master.PhanHeGiaCong AS SubcontractGroup,
    master.DonVi AS UnitCode,
    COALESCE(NULLIF(LTRIM(RTRIM(subcontractor.TenDVGC)), N''), master.DonVi) AS UnitName,
    COALESCE(NULLIF(LTRIM(RTRIM(master.DiaChi)), N''), subcontractor.DiaChiDVGC) AS UnitAddress,
    master.NguoiTaoPhieu AS CreatedBy,
    master.NgayTaoPhieu AS CreatedDate,
    master.IsActive AS IsActive,
    master.DaChuyenBravo AS SyncedToBravo,
    JSON_QUERY((
        SELECT
            detail.Id AS DetailId,
            ROW_NUMBER() OVER (ORDER BY detail.ThoiGianQuetXuat, detail.Id) AS DetailNo,
            detail.TemBarCodeBTP AS Barcode,
            detail.TemBarCodeMoi AS NewBarcode,
            detail.LoaiGiaCong AS SubcontractType,
            detail.MaGiaCong AS SubcontractCode,
            detail.SLXuat AS QuantityOut,
            detail.SLNhan AS QuantityIn,
            detail.SoLuongConLai AS QuantityRemaining,
            detail.NguoiQuetXuat AS ScannedOutBy,
            detail.ThoiGianQuetXuat AS ScannedOutAt,
            detail.NguoiXacNhan AS ConfirmedBy,
            detail.ThoiGianXacNhan AS ConfirmedAt,
            detail.GhiChu AS Note,
            barcodeInfo.PO,
            barcodeInfo.Size,
            barcodeInfo.MaHang AS ProductCode,
            barcodeInfo.ChungLoai AS ItemType
        FROM dbo.CUTTING_PhieuGiaCongXuatKho_DaQuet AS detail
        OUTER APPLY (
            SELECT TOP (1) bc.PO, bc.Size, bc.MaHang, bc.ChungLoai
            FROM dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet AS bc
            WHERE bc.TemBarcodeBTP = detail.TemBarCodeBTP
            ORDER BY bc.ThoiGianQuetXuat DESC
        ) AS barcodeInfo
        WHERE detail.IdPhieuGiaCong = master.PhieuGiaCongXuatKhoId
        ORDER BY detail.ThoiGianQuetXuat, detail.Id
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.CUTTING_PhieuGiaCongXuatKho AS master
LEFT JOIN dbo.Lib_DonViGiaCong AS subcontractor
    ON subcontractor.MaDVGC = master.DonVi
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), master.MaPhieu))) = @DocumentId;
