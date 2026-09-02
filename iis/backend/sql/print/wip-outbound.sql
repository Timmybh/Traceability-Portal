SELECT TOP (1)
    master.*,
    JSON_QUERY((
        SELECT barcodeRow.*
        FROM dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet AS barcodeRow
        WHERE barcodeRow.SoPhieuCapBTP = master.SoPhieuCapBTP
        FOR JSON PATH
    )) AS BarcodesJson
FROM dbo.CUTTING_PhieuCapBTP AS master
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), master.SoPhieuCapBTP))) = @DocumentId;
