SELECT TOP (1)
    relaxingRow.*,
    customer.TenDayDu AS CustomerName,
    stock.SL AS YardQuantity,
    stock.SLMet AS MeterQuantity,
    stock.AnhMau AS ShadeNo
FROM dbo.CUTTING_PhieuXaVai AS relaxingRow
LEFT JOIN dbo.Lib_KhachHang AS customer ON customer.KHId = relaxingRow.MaKH
OUTER APPLY (
    SELECT TOP (1) rp.SL, rp.SLMet, rp.AnhMau
    FROM dw.RPT_TONKHOVAI AS rp
    WHERE rp.MaCay = relaxingRow.MaCay
    ORDER BY rp.NgayTao DESC
) AS stock
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), relaxingRow.IdPhieuXaVai))) = @DocumentId;
