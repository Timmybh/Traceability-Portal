DECLARE @InputRFID nvarchar(255) = LTRIM(RTRIM(@RFID));
DECLARE @NormalizedRFID nvarchar(255) = REPLACE(REPLACE(REPLACE(@InputRFID, N'(', N''), N')', N''), N' ', N'');

WITH MappingRow AS (
    SELECT TOP (1)
        mp.productcode AS ProductCode,
        COALESCE(tc.Mua, cap.SeasonCode) AS SeasonCode
    FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp
    LEFT JOIN dbo.CUTTING_TemBarcode_TachCay AS tc
        ON tc.Code = mp.BarcodeTachCay
    OUTER APPLY (
        SELECT TOP (1) p.SeasonCode
        FROM dbo.CUTTING_PhieuCapBTP AS p
        INNER JOIN dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
            ON detail.IdCapBTP = p.IdCapBTP
        WHERE REPLACE(LTRIM(RTRIM(p.ProductCode)), N';', N'') =
              REPLACE(LTRIM(RTRIM(mp.productcode)), N';', N'')
          AND detail.PO = mp.po
        ORDER BY p.NgayTao DESC, detail.Id DESC
    ) AS cap
    WHERE mp.RFID IN (@InputRFID, @NormalizedRFID)
       OR mp.RFID_Hex IN (@InputRFID, @NormalizedRFID)
       OR mp.Code_RFID IN (@InputRFID, @NormalizedRFID)
       OR mp.Code_RFID_Hex IN (@InputRFID, @NormalizedRFID)
       OR mp.RFID_Barcode IN (@InputRFID, @NormalizedRFID)
    ORDER BY mp.ThoiGianMap DESC
), ProductRow AS (
    SELECT TOP (1)
        product.Id,
        product.URLFrontImage,
        product.URLBackImage
    FROM dbo.TEC_ProductInformation AS product
    INNER JOIN MappingRow AS mapping
        ON REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), product.ProductCode))), N';', N'') =
           REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), mapping.ProductCode))), N';', N'')
       AND REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), product.SeasonCode))), N';', N'') =
           REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), mapping.SeasonCode))), N';', N'')
    ORDER BY product.Id DESC
)
SELECT
    product.Id,
    @InputRFID AS RFID,
    imageRow.Url,
    imageRow.Side
FROM ProductRow AS product
CROSS APPLY (VALUES
    (NULLIF(LTRIM(RTRIM(product.URLFrontImage)), N''), N'front'),
    (NULLIF(LTRIM(RTRIM(product.URLBackImage)), N''), N'back')
) AS imageRow(Url, Side)
WHERE imageRow.Url IS NOT NULL;
