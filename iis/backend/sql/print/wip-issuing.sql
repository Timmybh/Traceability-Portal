SELECT TOP (1)
    master.*,
    JSON_QUERY((
        SELECT detail.*
        FROM dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
        WHERE detail.IdCapBTP = master.IdCapBTP
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.CUTTING_PhieuCapBTP AS master
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), master.SoPhieuCapBTP))) = @DocumentId;
