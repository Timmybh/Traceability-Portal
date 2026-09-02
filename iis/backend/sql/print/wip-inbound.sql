SELECT barcodeRow.*
FROM dbo.CUTTING_PhieuHoachToan_TemBarCode AS barcodeRow
WHERE CONVERT(nvarchar(255), barcodeRow.PhieuHoachToanId) = @DocumentId
ORDER BY barcodeRow.NgayTao;
