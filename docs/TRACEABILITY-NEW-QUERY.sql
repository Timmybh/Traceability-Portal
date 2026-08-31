DECLARE @InputRFID nvarchar(255) = LTRIM(RTRIM(@RFID));
DECLARE @NormalizedRFID nvarchar(255) =
    REPLACE(REPLACE(REPLACE(@InputRFID, N'(', N''), N')', N''), N' ', N'');

WITH MappingRow AS (
    SELECT TOP (1)
        mp.RFID,
        mp.RFID_Hex,
        mp.BarcodeTachCay,
        mp.po AS PO,
        mp.productcode AS ProductCode,
        mp.ThoiGianMap,
        mp.NguoiMap
    FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp
    WHERE mp.RFID = @InputRFID
       OR mp.RFID = @NormalizedRFID
       OR mp.RFID_Hex = @InputRFID
       OR mp.RFID_Hex = @NormalizedRFID
       OR mp.Code_RFID = @InputRFID
       OR mp.Code_RFID = @NormalizedRFID
       OR mp.Code_RFID_Hex = @InputRFID
       OR mp.Code_RFID_Hex = @NormalizedRFID
       OR mp.RFID_Barcode = @InputRFID
       OR mp.RFID_Barcode = @NormalizedRFID
    ORDER BY
        CASE
            WHEN mp.RFID = @InputRFID THEN 0
            WHEN mp.RFID = @NormalizedRFID THEN 1
            WHEN mp.RFID_Hex = @InputRFID THEN 2
            WHEN mp.RFID_Hex = @NormalizedRFID THEN 3
            WHEN mp.Code_RFID = @InputRFID THEN 4
            WHEN mp.Code_RFID = @NormalizedRFID THEN 5
            WHEN mp.Code_RFID_Hex = @InputRFID THEN 6
            WHEN mp.Code_RFID_Hex = @NormalizedRFID THEN 7
            WHEN mp.RFID_Barcode = @InputRFID THEN 8
            ELSE 9
        END,
        mp.ThoiGianMap DESC
)
SELECT
    mp.RFID,
    customer.TenNgan,
    mp.PO,
    mp.ProductCode,
    CAST(NULL AS nvarchar(200)) AS ItemId,
    NULLIF(LTRIM(RTRIM(tc.TenSize)), N'') AS Size,
    CAST(NULL AS nvarchar(500)) AS Art,
    colorInfo.TenMau AS Color,
    NULLIF(REPLACE(LTRIM(RTRIM(COALESCE(tc.Mua, cap.SeasonCode))), N';', N''), N'') AS Season,
    COALESCE(NULLIF(LTRIM(RTRIM(cap.TenXiNghiep)), N''), NULLIF(LTRIM(RTRIM(cap.TenPhanXuong)), N'')) AS XiNghiep,
    NULLIF(LTRIM(RTRIM(cap.TenCum)), N'') AS ChuyenMay,
    NULLIF(REPLACE(LTRIM(RTRIM(COALESCE(tc.LenhSanXuat, cap.LenhSanXuat))), N';', N''), N'') AS LenhSanXuat,
    NULLIF(LTRIM(RTRIM(tc.BanMay)), N'') AS BanCat,
    NULLIF(LTRIM(RTRIM(tc.Lot)), N'') AS LotVaiChinh,
    contrast.LotVaiPhoi,
    mp.ThoiGianMap AS NgaySanXuat,
    mp.ThoiGianMap,
    mp.BarcodeTachCay,
    mp.NguoiMap,
    JSON_QUERY(N'[]') AS TimelineJson
FROM MappingRow AS mp
INNER JOIN dbo.CUTTING_TemBarcode_TachCay AS tc
    ON tc.Code = mp.BarcodeTachCay
OUTER APPLY (
    SELECT TOP (1)
        p.SoPhieuCapBTP,
        p.TenXiNghiep,
        p.TenPhanXuong,
        p.TenCum,
        p.SeasonCode,
        p.LenhSanXuat
    FROM dbo.CUTTING_PhieuCapBTP AS p
    WHERE REPLACE(LTRIM(RTRIM(p.ProductCode)), N';', N'') = REPLACE(LTRIM(RTRIM(mp.ProductCode)), N';', N'')
      AND REPLACE(LTRIM(RTRIM(p.LenhSanXuat)), N';', N'') = REPLACE(LTRIM(RTRIM(tc.LenhSanXuat)), N';', N'')
      AND EXISTS (
          SELECT 1
          FROM dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet AS d
          WHERE d.SoPhieuCapBTP = p.SoPhieuCapBTP
            AND d.PO = mp.PO
            AND ISNULL(d.TraBTP, 0) = 0
      )
    ORDER BY p.NgayTao DESC, p.IdCapBTP DESC
) AS cap
OUTER APPLY (
    SELECT STRING_AGG(CAST(l.Lot AS nvarchar(max)), N', ')
        WITHIN GROUP (ORDER BY l.Lot) AS LotVaiPhoi
    FROM (
        SELECT DISTINCT LTRIM(RTRIM(d.Lot)) AS Lot
        FROM dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet AS d
        WHERE d.SoPhieuCapBTP = cap.SoPhieuCapBTP
          AND d.PO = mp.PO
          AND NULLIF(LTRIM(RTRIM(d.Lot)), N'') IS NOT NULL
          AND LOWER(LTRIM(RTRIM(ISNULL(d.ChungLoai, N'')))) LIKE N'%phối%'
          AND ISNULL(d.TraBTP, 0) = 0
    ) AS l
) AS contrast
OUTER APPLY (
    SELECT TOP (1) NULLIF(LTRIM(RTRIM(detail.TenMau)), N'') AS TenMau
    FROM dbo.CUTTING_PhieuCapBTP AS colorCap
    INNER JOIN dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
        ON detail.IdCapBTP = colorCap.IdCapBTP
    WHERE REPLACE(LTRIM(RTRIM(colorCap.ProductCode)), N';', N'') = REPLACE(LTRIM(RTRIM(mp.ProductCode)), N';', N'')
      AND REPLACE(LTRIM(RTRIM(colorCap.LenhSanXuat)), N';', N'') = REPLACE(LTRIM(RTRIM(tc.LenhSanXuat)), N';', N'')
      AND detail.PO = mp.PO
      AND NULLIF(LTRIM(RTRIM(detail.TenMau)), N'') IS NOT NULL
    ORDER BY
        CASE WHEN LTRIM(RTRIM(detail.SizeCode)) = LTRIM(RTRIM(tc.TenSize)) THEN 0 ELSE 1 END,
        colorCap.NgayTao DESC,
        detail.Id DESC
) AS colorInfo
OUTER APPLY (
    SELECT TOP (1) kh.TenNgan
    FROM dbo.Bravo_DonDatHangBan_Master AS so
    INNER JOIN dbo.Lib_KhachHang AS kh
        ON kh.MaKhachHang = so.CustomerCode
    WHERE so.PO = mp.PO
      AND so.ProductCode = mp.ProductCode
      AND ISNULL(so.IsActive, 1) = 1
    ORDER BY so.Id DESC
) AS customer;
