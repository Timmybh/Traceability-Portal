SELECT TOP (1)
    master.*,
    JSON_QUERY((
        SELECT tree.*
        FROM dbo.CUTTING_PhieuHoachToan_ChiTiet_NoiCay AS tree
        WHERE tree.PhieuHoachToanId = master.PhieuHoachToanId
        FOR JSON PATH
    )) AS FabricTreesJson,
    JSON_QUERY((
        SELECT barcodeRow.*
        FROM dbo.CUTTING_PhieuHoachToan_TemBarCode AS barcodeRow
        WHERE barcodeRow.PhieuHoachToanId = master.PhieuHoachToanId
        FOR JSON PATH
    )) AS BarcodesJson
FROM dbo.CUTTING_PhieuHoachToan AS master
WHERE CONVERT(nvarchar(255), master.PhieuHoachToanId) = @DocumentId;
