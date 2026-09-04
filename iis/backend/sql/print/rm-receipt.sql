SELECT TOP (1)
    inspection.*,
    inspection.MaPhieu AS DocNo,
    CASE LOWER(LTRIM(RTRIM(CONVERT(nvarchar(20), inspection.LoaiGiamDinh))))
        WHEN N'nl' THEN N'NK'
        WHEN N'pl' THEN N'NM'
    END AS DocCode,
    CAST(inspection.NgayGiamDinh AS date) AS DocDate,
    JSON_QUERY((
        SELECT
            detail.*,
            detail.TenNPL AS ItemName,
            detail.MaNPL AS ItemCode,
            detail.TongGiamDinh AS DocumentQuantity,
            COALESCE(detail.SLDat, detail.TongGiamDinh) AS ReceivedQuantity
        FROM dbo.WH_ChiTietPhieuGiamDinh AS detail
        WHERE detail.PGDId = inspection.PGDId
        ORDER BY detail.CTPGDId
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.WH_PhieuGiamDinh AS inspection
WHERE CONVERT(nvarchar(255), inspection.PGDId) = @DocumentId;
