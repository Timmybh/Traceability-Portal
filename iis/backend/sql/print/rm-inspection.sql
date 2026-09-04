SELECT TOP (1)
    inspectionRow.*,
    inspectionRow.SoPhieuKiem AS DocNo,
    inspectionRow.NgayKiemVai AS DocDate,
    customer.TenDayDu AS CustomerName,
    supplier.TenDayDu AS SupplierName,
    batch.MaHang AS MaHang,
    (
        SELECT COUNT(*)
        FROM dbo.QM_PhieuKiemVai_CayVai AS rollCount
        WHERE rollCount.PKVId = inspectionRow.PKVId
    ) AS RollCount,
    JSON_QUERY((
        SELECT legend.MaLoi, legend.TenLoi
        FROM dbo.Lib_DSLoi_KiemVai AS legend
        WHERE legend.NId = 8
        ORDER BY legend.LId
        FOR JSON PATH
    )) AS DefectLegendJson,
    JSON_QUERY((
        SELECT
            inspectionTree.*,
            JSON_QUERY((
                SELECT defect.*
                FROM dbo.QM_PhieuKiemVai_Cay_ChiTiet AS defect
                WHERE defect.CTId = inspectionTree.CTId
                ORDER BY defect.CTLId
                FOR JSON PATH
            )) AS DefectsJson
        FROM dbo.QM_PhieuKiemVai_CayVai AS inspectionTree
        WHERE inspectionTree.PKVId = inspectionRow.PKVId
        ORDER BY inspectionTree.CTId
        FOR JSON PATH
    )) AS InspectionTreesJson
FROM dbo.QM_PhieuKiemVai AS inspectionRow
LEFT JOIN dbo.Lib_KhachHang AS customer ON customer.KHId = inspectionRow.KHId
LEFT JOIN dbo.Lib_NhaCungCap AS supplier ON supplier.NCCId = inspectionRow.NCCId
OUTER APPLY (
    SELECT TOP (1) batchRow.MaHang
    FROM dbo.WH_PhieuGiamDinh AS batchRow
    WHERE batchRow.DHId = inspectionRow.DHId
    ORDER BY batchRow.NgayGiamDinh DESC
) AS batch
WHERE CONVERT(nvarchar(255), inspectionRow.PKVId) = @DocumentId
  AND ISNULL(UPPER(LTRIM(RTRIM(CONVERT(nvarchar(50), inspectionRow.TrangThai)))), N'') <> N'HUY';
