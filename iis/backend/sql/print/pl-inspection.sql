SELECT TOP (1)
    inspection.*,
    inspection.MaPhieu AS DocNo,
    N'NM' AS DocCode,
    CAST(inspection.NgayGiamDinh AS date) AS DocDate,
    CAST(inspection.NgayNhanNL AS date) AS ReceivedDate,
    customer.TenDayDu AS CustomerName,
    JSON_QUERY((
        SELECT
            detail.*,
            detail.TenNPL AS ItemName,
            detail.MaNPL AS ItemCode,
            detail.ProductCodeB AS StyleCode,
            detail.TongGiamDinh AS DocumentQuantity,
            COALESCE(detail.SLDat, detail.TongGiamDinh) AS ReceivedQuantity,
            supplier.TenDayDu AS SupplierName,
            JSON_QUERY((
                SELECT
                    defect.*,
                    defectLib.TenLoi AS DefectName
                FROM dbo.WH_ChiTietPhieuGiamDinh_KiemPhuLieu AS defect
                LEFT JOIN dbo.Lib_DSLoi_PhuLieu AS defectLib ON defectLib.MaLoi = defect.MaLoi
                WHERE defect.CTPGDId = detail.CTPGDId
                ORDER BY defect.Id
                FOR JSON PATH
            )) AS DefectsJson
        FROM dbo.WH_ChiTietPhieuGiamDinh AS detail
        LEFT JOIN dbo.Lib_NhaCungCap AS supplier ON supplier.NCCId = detail.NCCId
        WHERE detail.PGDId = inspection.PGDId
        ORDER BY detail.CTPGDId
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.WH_PhieuGiamDinh AS inspection
LEFT JOIN dbo.Lib_KhachHang AS customer ON customer.KHId = inspection.KHId
WHERE CONVERT(nvarchar(255), inspection.PGDId) = @DocumentId
  AND LOWER(LTRIM(RTRIM(CONVERT(nvarchar(20), inspection.LoaiGiamDinh)))) = N'pl'
  AND ISNULL(UPPER(LTRIM(RTRIM(CONVERT(nvarchar(50), inspection.TrangThai)))), N'') <> N'HUY';
