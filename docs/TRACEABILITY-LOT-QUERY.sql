DECLARE @InputCustomer nvarchar(50) = LTRIM(RTRIM(@CustomerCode));
DECLARE @InputLOT nvarchar(250) = LTRIM(RTRIM(@LOT));

IF NULLIF(@InputCustomer, N'') IS NULL OR NULLIF(@InputLOT, N'') IS NULL
BEGIN
    SELECT CAST(NULL AS nvarchar(50)) AS CustomerCode,
           CAST(NULL AS nvarchar(250)) AS LOT,
           CAST(NULL AS nvarchar(max)) AS LotsJson
    WHERE 1 = 0;
    RETURN;
END;

WITH LotReferences AS (
    SELECT
        w.MaKhachHang AS CustomerCode,
        w.TenKhachHangNew AS CustomerName,
        w.MaHang AS ProductCode,
        w.PONo AS PO,
        CAST(NULL AS nvarchar(250)) AS Season
    FROM dbo.WH_InBarcode_Report_NL AS w
    WHERE w.MaKhachHang = @InputCustomer
      AND w.LOT = @InputLOT
    UNION
    SELECT m.MaKhachHang, m.KhachHang, m.MaHang, m.PO, m.Season
    FROM dbo.Tracking_RFID_Master AS m
    WHERE m.MaKhachHang = @InputCustomer
      AND m.Lot = @InputLOT
    UNION
    SELECT m.MaKhachHang, m.KhachHang, m.MaHang, m.PO, m.Season
    FROM dbo.Tracking_RFID_Master AS m
    INNER JOIN dbo.CUTTING_PhieuCapBTP AS cap
        ON cap.ProductCode = m.MaHang
       AND cap.TenCum = m.ChuyenMay
    INNER JOIN dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet AS ct
        ON ct.SoPhieuCapBTP = cap.SoPhieuCapBTP
       AND ct.PO = m.PO
    WHERE m.MaKhachHang = @InputCustomer
      AND ct.Lot = @InputLOT
      AND LOWER(LTRIM(RTRIM(ISNULL(ct.ChungLoai, N'')))) LIKE N'%phối%'
      AND ISNULL(ct.TraBTP, 0) = 0
)
SELECT
    @InputCustomer AS CustomerCode,
    @InputLOT AS LOT,
    JSON_QUERY((
        SELECT
            @InputLOT AS Lot,
            JSON_QUERY((
                SELECT item.STT, item.ItemName, item.Quantity, item.YardQuantity, item.DownloadKey
                FROM (
                    SELECT
                        1 AS STT,
                        N'Phiếu kiểm định' AS ItemName,
                        CAST((
                            SELECT COUNT_BIG(DISTINCT w.MaPhieu)
                            FROM dbo.WH_InBarcode_Report_NL AS w
                            WHERE w.MaKhachHang = @InputCustomer
                              AND w.LOT = @InputLOT
                              AND NULLIF(LTRIM(RTRIM(w.MaPhieu)), N'') IS NOT NULL
                        ) AS decimal(18, 2)) AS Quantity,
                        CAST(ISNULL((
                            SELECT SUM(CONVERT(decimal(18, 2), ISNULL(w.SLY, 0)))
                            FROM dbo.WH_InBarcode_Report_NL AS w
                            WHERE w.MaKhachHang = @InputCustomer
                              AND w.LOT = @InputLOT
                        ), 0) AS decimal(18, 2)) AS YardQuantity,
                        N'inspection-receipts' AS DownloadKey
                    UNION ALL
                    SELECT
                        2,
                        N'Phiếu nhập hàng',
                        CAST((
                            SELECT COUNT_BIG(DISTINCT w.MaPhieuNhap)
                            FROM dbo.WH_InBarcode_Report_NL AS w
                            WHERE w.MaKhachHang = @InputCustomer
                              AND w.LOT = @InputLOT
                              AND NULLIF(LTRIM(RTRIM(w.MaPhieuNhap)), N'') IS NOT NULL
                        ) AS decimal(18, 2)),
                        CAST(ISNULL((
                            SELECT SUM(CONVERT(decimal(18, 2), ISNULL(w.SLY, 0)))
                            FROM dbo.WH_InBarcode_Report_NL AS w
                            WHERE w.MaKhachHang = @InputCustomer
                              AND w.LOT = @InputLOT
                        ), 0) AS decimal(18, 2)),
                        N'goods-receipts'
                    UNION ALL
                    SELECT
                        3,
                        N'Sản phẩm',
                        CAST((SELECT COUNT_BIG(DISTINCT r.ProductCode) FROM LotReferences AS r) AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'products'
                    UNION ALL
                    SELECT
                        4,
                        N'PO',
                        CAST((SELECT COUNT_BIG(DISTINCT r.PO) FROM LotReferences AS r) AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'purchase-orders'
                    UNION ALL
                    SELECT
                        5,
                        N'Hồ sơ chất lượng',
                        CAST((
                            SELECT COUNT_BIG(DISTINCT q.ID)
                            FROM dbo.TEC_BaoCaoChatLuong_TaiLieu AS q
                            WHERE EXISTS (
                                SELECT 1
                                FROM LotReferences AS r
                                WHERE r.CustomerName IS NOT NULL
                                  AND r.Season IS NOT NULL
                                  AND r.CustomerName = q.KhachHang
                                  AND r.ProductCode = q.MaHang
                                  AND r.Season = q.Mua
                            )
                        ) AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'quality-files'
                ) AS item
                ORDER BY item.STT
                FOR JSON PATH
            )) AS Items
        WHERE EXISTS (SELECT 1 FROM LotReferences)
        FOR JSON PATH
    )) AS LotsJson
WHERE EXISTS (SELECT 1 FROM LotReferences);
