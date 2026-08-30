DECLARE @InputCustomer nvarchar(50) = LTRIM(RTRIM(@CustomerCode));
DECLARE @InputPO nvarchar(250) = LTRIM(RTRIM(@PO));

IF NULLIF(@InputCustomer, N'') IS NULL OR NULLIF(@InputPO, N'') IS NULL
BEGIN
    SELECT CAST(NULL AS nvarchar(50)) AS CustomerCode,
           CAST(NULL AS nvarchar(250)) AS PO,
           CAST(NULL AS nvarchar(max)) AS ProductsJson
    WHERE 1 = 0;
    RETURN;
END;

WITH Products AS (
    SELECT
        m.MaHang AS ProductCode,
        m.Season,
        m.KhachHang AS CustomerName,
        COUNT_BIG(DISTINCT m.RFID) AS RFIDCount
    FROM dbo.Tracking_RFID_Master AS m
    WHERE m.MaKhachHang = @InputCustomer
      AND m.PO = @InputPO
    GROUP BY m.MaHang, m.Season, m.KhachHang
)
SELECT
    @InputCustomer AS CustomerCode,
    @InputPO AS PO,
    JSON_QUERY((
        SELECT
            p.ProductCode,
            p.Season,
            p.CustomerName,
            JSON_QUERY((
                SELECT item.STT, item.ItemName, item.Quantity, item.YardQuantity, item.DownloadKey
                FROM (
                    SELECT
                        1 AS STT,
                        N'Nguyên liệu' AS ItemName,
                        CAST(ISNULL((
                            SELECT SUM(CONVERT(decimal(18, 2), ISNULL(w.SL, 0)))
                            FROM dbo.WH_InBarcode_Report_NL AS w
                            WHERE w.MaKhachHang = @InputCustomer
                              AND w.PONo = @InputPO
                              AND w.MaHang = p.ProductCode
                        ), 0) AS decimal(18, 2)) AS Quantity,
                        CAST(ISNULL((
                            SELECT SUM(CONVERT(decimal(18, 2), ISNULL(w.SLY, 0)))
                            FROM dbo.WH_InBarcode_Report_NL AS w
                            WHERE w.MaKhachHang = @InputCustomer
                              AND w.PONo = @InputPO
                              AND w.MaHang = p.ProductCode
                        ), 0) AS decimal(18, 2)) AS YardQuantity,
                        N'materials' AS DownloadKey
                    UNION ALL
                    SELECT
                        2,
                        N'Phụ liệu',
                        CAST(ISNULL((
                            SELECT SUM(CONVERT(decimal(18, 2), ISNULL(a.Quantity, 0)))
                            FROM dbo.TEC_TheoDoi_PhuLieu AS a
                            WHERE a.MaHang = p.ProductCode
                              AND a.Mua = p.Season
                        ), 0) AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'accessories'
                    UNION ALL
                    SELECT
                        3,
                        N'Tem RFID',
                        CAST(p.RFIDCount AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'rfid-tags'
                    UNION ALL
                    SELECT
                        4,
                        N'Tem SHU',
                        CAST((
                            SELECT COUNT_BIG(DISTINCT s.SHU)
                            FROM dbo.FG_Map_SHU_RFID_DongGoi AS s
                            WHERE s.PONo = @InputPO
                              AND s.ProductCode = p.ProductCode
                        ) AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'shu-tags'
                    UNION ALL
                    SELECT
                        5,
                        N'Hồ sơ kỹ thuật',
                        CAST((
                            SELECT COUNT_BIG(DISTINCT d.IdTimeLine_Detail)
                            FROM dbo.Tracking_RFID_Master AS m
                            INNER JOIN dbo.Tracking_RFID_Master_TimeLine AS t ON t.RFID = m.RFID
                            INNER JOIN dbo.Tracking_RFID_Master_TimeLine_Detail AS d ON d.IdTimeLine = t.IdTimeLine
                            WHERE m.MaKhachHang = @InputCustomer
                              AND m.PO = @InputPO
                              AND m.MaHang = p.ProductCode
                              AND (LOWER(ISNULL(t.TieuDe, N'')) LIKE N'%kỹ thuật%'
                                   OR LOWER(ISNULL(t.TieuDeTiengAnh, N'')) LIKE N'%technical%'
                                   OR LOWER(ISNULL(d.BoPhan, N'')) LIKE N'%kỹ thuật%')
                        ) AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'technical-files'
                    UNION ALL
                    SELECT
                        6,
                        N'Hồ sơ thông quan',
                        CAST((
                            SELECT COUNT_BIG(DISTINCT d.IdTimeLine_Detail)
                            FROM dbo.Tracking_RFID_Master AS m
                            INNER JOIN dbo.Tracking_RFID_Master_TimeLine AS t ON t.RFID = m.RFID
                            INNER JOIN dbo.Tracking_RFID_Master_TimeLine_Detail AS d ON d.IdTimeLine = t.IdTimeLine
                            WHERE m.MaKhachHang = @InputCustomer
                              AND m.PO = @InputPO
                              AND m.MaHang = p.ProductCode
                              AND (LOWER(ISNULL(t.TieuDe, N'')) LIKE N'%thông quan%'
                                   OR LOWER(ISNULL(t.TieuDe, N'')) LIKE N'%hải quan%'
                                   OR LOWER(ISNULL(t.TieuDeTiengAnh, N'')) LIKE N'%custom%'
                                   OR LOWER(ISNULL(d.BoPhan, N'')) LIKE N'%thông quan%'
                                   OR LOWER(ISNULL(d.BoPhan, N'')) LIKE N'%hải quan%')
                        ) AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'customs-files'
                    UNION ALL
                    SELECT
                        7,
                        N'Hồ sơ chất lượng',
                        CAST((
                            SELECT COUNT_BIG(*)
                            FROM dbo.TEC_BaoCaoChatLuong_TaiLieu AS q
                            WHERE q.KhachHang = p.CustomerName
                              AND q.MaHang = p.ProductCode
                              AND q.Mua = p.Season
                        ) AS decimal(18, 2)),
                        CAST(NULL AS decimal(18, 2)),
                        N'quality-files'
                ) AS item
                ORDER BY item.STT
                FOR JSON PATH
            )) AS Items
        FROM Products AS p
        ORDER BY p.ProductCode, p.Season
        FOR JSON PATH
    )) AS ProductsJson
WHERE EXISTS (SELECT 1 FROM Products);
