SELECT TOP (1)
    outboundRow.*,
    outboundRow.MaSoPhieuSoan AS DocNo,
    outboundRow.NgaySoan AS DocDate,
    JSON_QUERY((
        SELECT
            detail.*,
            JSON_QUERY((
                SELECT
                    cay.*,
                    stock.ProductionOrderNo,
                    stock.MaHangPO,
                    stock.ArtCode,
                    stock.SizeCode
                FROM dbo.WH_ChiTietPhieuSoanHang_ChiTietCay AS cay
                OUTER APPLY (
                    SELECT TOP (1)
                        rp.ProductionOrderNo,
                        rp.MaHangPO,
                        rp.ArtCode,
                        rp.SizeCode
                    FROM dw.RPT_TONKHOVAI AS rp
                    WHERE rp.MaCay IN (cay.MaCay, cay.MaCayMoi)
                    ORDER BY
                        CASE WHEN rp.MaCay = cay.MaCay THEN 0 ELSE 1 END,
                        rp.NgayTao DESC
                ) AS stock
                WHERE cay.ChiTietPhieuSoanHangId = detail.ChiTietPhieuSoanHangId
                ORDER BY cay.CayId
                FOR JSON PATH
            )) AS RollsJson
        FROM dbo.WH_ChiTietPhieuSoanHang AS detail
        WHERE detail.PhieuSoanHangId = outboundRow.PhieuSoanHangId
        ORDER BY detail.ChiTietPhieuSoanHangId
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.WH_PhieuSoanHang AS outboundRow
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan))) = @DocumentId;
