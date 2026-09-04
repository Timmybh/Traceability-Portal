SELECT TOP (1)
    inspectionRow.*,
    inspectionRow.SoPhieuKiem AS DocNo,
    inspectionRow.NgayKiemVai AS DocDate,
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
WHERE CONVERT(nvarchar(255), inspectionRow.PKVId) = @DocumentId
  AND ISNULL(UPPER(LTRIM(RTRIM(CONVERT(nvarchar(50), inspectionRow.TrangThai)))), N'') <> N'HUY';
