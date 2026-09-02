SELECT barcodeRow.*
FROM dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet AS barcodeRow
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), barcodeRow.SoPhieuCapBTP))) = @DocumentId
ORDER BY barcodeRow.ThoiGianQuetXuat;
