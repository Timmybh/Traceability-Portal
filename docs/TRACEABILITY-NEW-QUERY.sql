-- SSMS: chỉ cần thay giá trị RFID tại dòng DECLARE bên dưới.
DECLARE @rffid nvarchar(255) = N'NHAP_RFID_TAI_DAY';

DECLARE @InputRFID nvarchar(255) = LTRIM(RTRIM(@rffid));
DECLARE @NormalizedRFID nvarchar(255) =
    REPLACE(REPLACE(REPLACE(@InputRFID, N'(', N''), N')', N''), N' ', N'');

WITH MappingCandidates AS (
    SELECT 0 AS MatchPriority, mp.*
    FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp
    WHERE mp.RFID = @InputRFID
    UNION ALL
    SELECT 1, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.RFID = @NormalizedRFID AND @NormalizedRFID <> @InputRFID
    UNION ALL
    SELECT 2, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.RFID_Hex = @InputRFID
    UNION ALL
    SELECT 3, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.RFID_Hex = @NormalizedRFID AND @NormalizedRFID <> @InputRFID
    UNION ALL
    SELECT 4, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.Code_RFID = @InputRFID
    UNION ALL
    SELECT 5, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.Code_RFID = @NormalizedRFID AND @NormalizedRFID <> @InputRFID
    UNION ALL
    SELECT 6, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.Code_RFID_Hex = @InputRFID
    UNION ALL
    SELECT 7, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.Code_RFID_Hex = @NormalizedRFID AND @NormalizedRFID <> @InputRFID
    UNION ALL
    SELECT 8, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.RFID_Barcode = @InputRFID
    UNION ALL
    SELECT 9, mp.* FROM dbo.CUTTING_TemBarcode_TachCay_RFID_Mapping AS mp WHERE mp.RFID_Barcode = @NormalizedRFID AND @NormalizedRFID <> @InputRFID
),
MappingRow AS (
    SELECT TOP (1)
        mp.RFID,
        mp.RFID_Hex,
        mp.BarcodeTachCay,
        mp.po AS PO,
        mp.productcode AS ProductCode,
        mp.ThoiGianMap,
        mp.NguoiMap
    FROM MappingCandidates AS mp
    ORDER BY mp.MatchPriority, mp.ThoiGianMap DESC
)
SELECT
    mp.RFID,
    customer.TenNgan,
    mp.PO,
    mp.ProductCode,
    CAST(NULL AS nvarchar(200)) AS ItemId,
    NULLIF(LTRIM(RTRIM(tc.TenSize)), N'') AS Size,
    CAST(NULL AS nvarchar(500)) AS Art,
    cap.TenMau AS Color,
    NULLIF(REPLACE(LTRIM(RTRIM(COALESCE(tc.Mua, cap.SeasonCode))), N';', N''), N'') AS Season,
    COALESCE(NULLIF(LTRIM(RTRIM(cap.TenXiNghiep)), N''), NULLIF(LTRIM(RTRIM(cap.TenPhanXuong)), N'')) AS XiNghiep,
    NULLIF(LTRIM(RTRIM(cap.TenCum)), N'') AS ChuyenMay,
    NULLIF(REPLACE(LTRIM(RTRIM(COALESCE(tc.LenhSanXuat, cap.LenhSanXuat))), N';', N''), N'') AS LenhSanXuat,
    bm.BanCat,
    COALESCE(mainFabric.LotVaiChinh, NULLIF(LTRIM(RTRIM(tc.Lot)), N'')) AS LotVaiChinh,
    contrast.LotVaiPhoi,
    mp.ThoiGianMap AS NgaySanXuat,
    mp.ThoiGianMap,
    mp.BarcodeTachCay,
    mp.NguoiMap,
    COALESCE(productDevelopment.TimelineJson, JSON_QUERY(N'[]')) AS TimelineJson
FROM MappingRow AS mp
INNER JOIN dbo.CUTTING_TemBarcode_TachCay AS tc
    ON tc.Code = mp.BarcodeTachCay
LEFT JOIN dbo.Cutting_PhieuDieuTietGiacSoDo_ChiTiet_BanMay AS bm
    ON CONVERT(nvarchar(100), bm.IdBanMay) =
       CONVERT(nvarchar(100), tc.IdBanMay)
OUTER APPLY (
    SELECT TOP (1)
        p.SoPhieuCapBTP,
        p.TenXiNghiep,
        p.TenPhanXuong,
        p.TenCum,
        p.SeasonCode,
        p.LenhSanXuat,
        detail.TenMau,
        detail.Id AS IdCapBTPCT
    FROM dbo.CUTTING_PhieuCapBTP AS p
    INNER JOIN dbo.CUTTING_PhieuCapBTP_ChiTiet AS detail
        ON detail.IdCapBTP = p.IdCapBTP
    WHERE REPLACE(LTRIM(RTRIM(p.ProductCode)), N';', N'') = REPLACE(LTRIM(RTRIM(mp.ProductCode)), N';', N'')
      AND detail.PO = mp.PO
    ORDER BY
        CASE WHEN LTRIM(RTRIM(detail.SizeCode)) = LTRIM(RTRIM(tc.TenSize)) THEN 0 ELSE 1 END,
        p.NgayTao DESC,
        detail.Id DESC
) AS cap
OUTER APPLY (
    SELECT TOP (1)
        NULLIF(LTRIM(RTRIM(d.Lot)), N'') AS LotVaiChinh
    FROM dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet AS d
    WHERE d.SoPhieuCapBTP = cap.SoPhieuCapBTP
      AND d.PO = mp.PO
      AND d.IdCapBTPCT = cap.IdCapBTPCT
      AND NULLIF(LTRIM(RTRIM(d.Lot)), N'') IS NOT NULL
      AND ISNULL(d.TraBTP, 0) = 0
    ORDER BY d.ThoiGianQuetXuat DESC, d.IdPhieuXuatKhoBTP DESC
) AS mainFabric
OUTER APPLY (
    SELECT STRING_AGG(CAST(l.Lot AS nvarchar(max)), N', ')
        WITHIN GROUP (ORDER BY l.Lot) AS LotVaiPhoi
    FROM (
        SELECT DISTINCT LTRIM(RTRIM(bc.Lot)) AS Lot
        FROM dbo.CUTTING_PhieuCapBTP_BarcodeChiTiet AS bc
        WHERE bc.TemBarcodeBTP = tc.Barcode
          AND bc.ChungLoai LIKE N'%phối%'
          AND NULLIF(LTRIM(RTRIM(bc.Lot)), N'') IS NOT NULL
          AND ISNULL(bc.TraBTP, 0) = 0
    ) AS l
) AS contrast
OUTER APPLY (
    SELECT TOP (1) kh.TenNgan
    FROM dbo.Bravo_DonDatHangBan_Master AS so
    INNER JOIN dbo.Lib_KhachHang AS kh
        ON kh.MaKhachHang = so.CustomerCode
    WHERE so.PO = mp.PO
      AND so.ProductCode = mp.ProductCode
      AND ISNULL(so.IsActive, 1) = 1
    ORDER BY so.Id DESC
) AS customer
OUTER APPLY (
    SELECT JSON_QUERY((
        SELECT
            product.Id AS TimelineId,
            1 AS StepNo,
            N'Phát triển sản phẩm' AS StepTitle,
            N'Product Development' AS StepTitleEnglish,
            documentSummary.StepDate,
            CONCAT(documentSummary.DocumentCount, N' tài liệu kỹ thuật') AS StepContent,
            CAST(NULL AS nvarchar(max)) AS StepLink,
            JSON_QUERY((
                SELECT
                    document.Id AS DetailId,
                    ROW_NUMBER() OVER (
                        ORDER BY
                            COALESCE(document.NgayBanHanh, document.NgayTao),
                            document.Id
                    ) AS DetailNo,
                    COALESCE(document.NgayBanHanh, document.NgayTao) AS DetailDate,
                    COALESCE(
                        NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(max), document.TenTaiLieu))), N''),
                        NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(max), documentType.TenLoai))), N''),
                        NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(max), document.TenLoaiTaiLieu))), N''),
                        CONVERT(nvarchar(max), document.MaLoaiTaiLieu)
                    ) AS DetailContent,
                    CONCAT(N'/api/traceability/document?id=', document.Id) AS DetailLink,
                    CONVERT(nvarchar(100), document.MaLoaiTaiLieu) AS DocumentCode,
                    document.IdMaster AS DocumentId,
                    document.TrangThai AS DocumentStatus
                FROM dbo.TEC_ThongTinTaiLieukyThuat AS document
                OUTER APPLY (
                    SELECT TOP (1) documentTypeRow.TenLoai
                    FROM dbo.TEC_LoaiTaiLieuKyThuat AS documentTypeRow
                    WHERE CONVERT(nvarchar(100), documentTypeRow.MaLoai) =
                          CONVERT(nvarchar(100), document.MaLoaiTaiLieu)
                    ORDER BY documentTypeRow.Id
                ) AS documentType
                WHERE TRY_CONVERT(bigint, document.IdMaster) = product.Id
                  AND LTRIM(RTRIM(document.TrangThai)) = N'Đã ban hành'
                ORDER BY
                    COALESCE(document.NgayBanHanh, document.NgayTao),
                    document.Id
                FOR JSON PATH
            )) AS Details
        FOR JSON PATH
    )) AS TimelineJson
    FROM dbo.TEC_ProductInformation AS product
    CROSS APPLY (
        SELECT
            MAX(COALESCE(document.NgayBanHanh, document.NgayTao)) AS StepDate,
            COUNT_BIG(*) AS DocumentCount
        FROM dbo.TEC_ThongTinTaiLieukyThuat AS document
        WHERE TRY_CONVERT(bigint, document.IdMaster) = product.Id
          AND LTRIM(RTRIM(document.TrangThai)) = N'Đã ban hành'
    ) AS documentSummary
    WHERE REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), product.ProductCode))), N';', N'') =
          REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), mp.ProductCode))), N';', N'')
      AND REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), product.SeasonCode))), N';', N'') =
          REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), COALESCE(tc.Mua, cap.SeasonCode)))), N';', N'')
      AND documentSummary.DocumentCount > 0
) AS productDevelopment
OPTION (RECOMPILE);
