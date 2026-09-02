-- SSMS: chỉ cần thay giá trị RFID tại dòng DECLARE bên dưới.
DECLARE @rffid nvarchar(255) = N'NHAP_RFID_TAI_DAY';

DECLARE @InputRFID nvarchar(255) = LTRIM(RTRIM(@rffid));
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
    WHERE mp.RFID IN (@InputRFID, @NormalizedRFID)
       OR mp.Code_RFID IN (@InputRFID, @NormalizedRFID)
       OR mp.RFID_Hex IN (@InputRFID, @NormalizedRFID)
    ORDER BY mp.ThoiGianMap DESC
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
    COALESCE(traceabilityTimeline.TimelineJson, JSON_QUERY(N'[]')) AS TimelineJson
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
        p.NgayDuyet,
        p.NgayNhanBTP,
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
    SELECT
        cap.NgayDuyet AS StepDate,
        JSON_QUERY((
            SELECT
                1 AS DetailId,
                1 AS DetailNo,
                cap.NgayDuyet AS DetailDate,
                CONCAT(N'Mã phiếu: ', cap.SoPhieuCapBTP) AS DetailContent,
                CONCAT(N'/api/traceability/print/wip-issuing?id=', cap.SoPhieuCapBTP) AS DetailLink
            FOR JSON PATH
        )) AS DetailsJson
    WHERE NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), cap.SoPhieuCapBTP))), N'') IS NOT NULL
      AND cap.NgayDuyet IS NOT NULL
) AS wipOrder
OUTER APPLY (
    SELECT
        cap.NgayNhanBTP AS StepDate,
        JSON_QUERY((
            SELECT
                1 AS DetailId,
                1 AS DetailNo,
                cap.NgayNhanBTP AS DetailDate,
                CONCAT(N'Mã phiếu: ', cap.SoPhieuCapBTP) AS DetailContent,
                CONCAT(N'/api/traceability/print/wip-outbound?id=', cap.SoPhieuCapBTP) AS DetailLink
            FOR JSON PATH
        )) AS DetailsJson,
        JSON_QUERY((
            SELECT
                1 AS DetailId,
                1 AS DetailNo,
                cap.NgayNhanBTP AS DetailDate,
                CONCAT(N'Mã phiếu: ', cap.SoPhieuCapBTP) AS DetailContent,
                CONCAT(N'/api/traceability/print/wip-scanning?id=', cap.SoPhieuCapBTP) AS DetailLink
            FOR JSON PATH
        )) AS ScanningDetailsJson
    WHERE NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), cap.SoPhieuCapBTP))), N'') IS NOT NULL
      AND cap.NgayNhanBTP IS NOT NULL
) AS wipOutbound
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
    SELECT TOP (1) kh.TenNgan, so.CustomerCode
    FROM dbo.Bravo_DonDatHangBan_Master AS so
    INNER JOIN dbo.Lib_KhachHang AS kh
        ON kh.MaKhachHang = so.CustomerCode
    WHERE so.PO = mp.PO
      AND so.ProductCode = mp.ProductCode
      AND ISNULL(so.IsActive, 1) = 1
    ORDER BY so.Id DESC
) AS customer
OUTER APPLY (
    SELECT TOP (1)
        product.Id AS TimelineId,
        documentSummary.StepDate,
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
        )) AS DetailsJson
    FROM dbo.TEC_ProductInformation AS product
    CROSS APPLY (
        SELECT
            MAX(COALESCE(document.NgayBanHanh, document.NgayTao)) AS StepDate
        FROM dbo.TEC_ThongTinTaiLieukyThuat AS document
        WHERE TRY_CONVERT(bigint, document.IdMaster) = product.Id
          AND LTRIM(RTRIM(document.TrangThai)) = N'Đã ban hành'
    ) AS documentSummary
    WHERE REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), product.ProductCode))), N';', N'') =
          REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), mp.ProductCode))), N';', N'')
      AND REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), product.SeasonCode))), N';', N'') =
          REPLACE(LTRIM(RTRIM(CONVERT(nvarchar(255), COALESCE(tc.Mua, cap.SeasonCode)))), N';', N'')
      AND EXISTS (
          SELECT 1
          FROM dbo.TEC_ThongTinTaiLieukyThuat AS publishedDocument
          WHERE TRY_CONVERT(bigint, publishedDocument.IdMaster) = product.Id
            AND LTRIM(RTRIM(publishedDocument.TrangThai)) = N'Đã ban hành'
      )
    ORDER BY product.Id DESC
) AS productDevelopment
OUTER APPLY (
    SELECT
        JSON_QUERY((
            SELECT
                ROW_NUMBER() OVER (ORDER BY invoice.AtchDocNo) AS DetailId,
                ROW_NUMBER() OVER (ORDER BY invoice.AtchDocNo) AS DetailNo,
                CAST(NULL AS datetime2) AS DetailDate,
                CONCAT(N'Số Invoice: ', invoice.AtchDocNo) AS DetailContent,
                CONCAT(N'/api/traceability/print/invoice?id=', invoice.AtchDocNo) AS DetailLink
            FROM (
                SELECT DISTINCT LTRIM(RTRIM(CONVERT(nvarchar(255), detail.AtchDocNo))) AS AtchDocNo
                FROM dbo.Bravo_PNK_Detail AS detail
                WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), detail.CustomerCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), customer.CustomerCode)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.SizeCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), tc.TenSize)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), mp.ProductCode)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductionOrderNo))) = LTRIM(RTRIM(CONVERT(nvarchar(255), COALESCE(tc.LenhSanXuat, cap.LenhSanXuat))))
                  AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), detail.AtchDocNo))), N'') IS NOT NULL
            ) AS invoice
            ORDER BY invoice.AtchDocNo
            FOR JSON PATH
        )) AS DetailsJson
) AS invoiceNumbers
OUTER APPLY (
    SELECT
        JSON_QUERY((
            SELECT
                receipt.ReceiptNotesId AS DetailId,
                ROW_NUMBER() OVER (ORDER BY receipt.DocNo) AS DetailNo,
                CAST(NULL AS datetime2) AS DetailDate,
                CONCAT(N'Mã phiếu: ', receipt.DocNo) AS DetailContent,
                CONCAT(N'/api/traceability/print/rm-receipt?id=', receipt.ReceiptNotesId) AS DetailLink,
                receipt.Department
            FROM (
                SELECT DISTINCT
                    master.ReceiptNotesId,
                    LTRIM(RTRIM(CONVERT(nvarchar(255), master.DocNo))) AS DocNo,
                    CASE master.DocCode
                        WHEN N'NK' THEN N'Nguyên liệu'
                        WHEN N'NM' THEN N'Phụ liệu'
                    END AS Department
                FROM dbo.Bravo_PNK_Detail AS detail
                INNER JOIN dbo.Bravo_PNK_Master AS master
                    ON detail.PNKMasterId = master.ReceiptNotesId
                WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), detail.CustomerCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), customer.CustomerCode)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.SizeCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), tc.TenSize)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), mp.ProductCode)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductionOrderNo))) = LTRIM(RTRIM(CONVERT(nvarchar(255), COALESCE(tc.LenhSanXuat, cap.LenhSanXuat))))
                  AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), master.DocNo))), N'') IS NOT NULL
                  AND master.DocCode IN (N'NK', N'NM')
                  AND master.DocStatus = 4
            ) AS receipt
            ORDER BY receipt.Department, receipt.DocNo
            FOR JSON PATH
        )) AS DetailsJson
) AS receiptNotes
OUTER APPLY (
    SELECT
        MAX(inspectionRows.NgayGiamDinh) AS StepDate,
        JSON_QUERY((
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY inspection.Department, inspection.NgayGiamDinh, inspection.MaPhieu
                ) AS DetailId,
                ROW_NUMBER() OVER (
                    ORDER BY inspection.Department, inspection.NgayGiamDinh, inspection.MaPhieu
                ) AS DetailNo,
                inspection.NgayGiamDinh AS DetailDate,
                CONCAT(N'Mã phiếu: ', inspection.MaPhieu) AS DetailContent,
                CONCAT(N'/api/traceability/print/rm-inspection?id=', inspection.MaPhieu) AS DetailLink,
                inspection.Department
            FROM (
                SELECT DISTINCT
                    LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.MaPhieu))) AS MaPhieu,
                    inspectionRow.NgayGiamDinh,
                    CASE LOWER(LTRIM(RTRIM(CONVERT(nvarchar(20), inspectionRow.LoaiGiamDinh))))
                        WHEN N'nl' THEN N'Nguyên liệu'
                        WHEN N'pl' THEN N'Phụ liệu'
                    END AS Department
                FROM dbo.Bravo_PNK_Detail AS detail
                INNER JOIN dbo.Bravo_PNK_Master AS master
                    ON detail.PNKMasterId = master.ReceiptNotesId
                INNER JOIN dbo.WH_PhieuGiamDinh AS inspectionRow
                    ON inspectionRow.ReceiptNotesId = master.ReceiptNotesId
                WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), detail.CustomerCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), customer.CustomerCode)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.SizeCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), tc.TenSize)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), mp.ProductCode)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductionOrderNo))) = LTRIM(RTRIM(CONVERT(nvarchar(255), COALESCE(tc.LenhSanXuat, cap.LenhSanXuat))))
                  AND master.DocCode IN (N'NK', N'NM')
                  AND master.DocStatus = 4
                  AND LOWER(LTRIM(RTRIM(CONVERT(nvarchar(20), inspectionRow.LoaiGiamDinh)))) IN (N'nl', N'pl')
                  AND ISNULL(UPPER(LTRIM(RTRIM(CONVERT(nvarchar(50), inspectionRow.TrangThai)))), N'') <> N'HUY'
                  AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.MaPhieu))), N'') IS NOT NULL
            ) AS inspection
            ORDER BY inspection.Department, inspection.NgayGiamDinh, inspection.MaPhieu
            FOR JSON PATH
        )) AS DetailsJson
    FROM (
        SELECT DISTINCT
            LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.MaPhieu))) AS MaPhieu,
            inspectionRow.NgayGiamDinh,
            LOWER(LTRIM(RTRIM(CONVERT(nvarchar(20), inspectionRow.LoaiGiamDinh)))) AS LoaiGiamDinh
        FROM dbo.Bravo_PNK_Detail AS detail
        INNER JOIN dbo.Bravo_PNK_Master AS master
            ON detail.PNKMasterId = master.ReceiptNotesId
        INNER JOIN dbo.WH_PhieuGiamDinh AS inspectionRow
            ON inspectionRow.ReceiptNotesId = master.ReceiptNotesId
        WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), detail.CustomerCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), customer.CustomerCode)))
          AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.SizeCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), tc.TenSize)))
          AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), mp.ProductCode)))
          AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductionOrderNo))) = LTRIM(RTRIM(CONVERT(nvarchar(255), COALESCE(tc.LenhSanXuat, cap.LenhSanXuat))))
          AND master.DocCode IN (N'NK', N'NM')
          AND master.DocStatus = 4
          AND LOWER(LTRIM(RTRIM(CONVERT(nvarchar(20), inspectionRow.LoaiGiamDinh)))) IN (N'nl', N'pl')
          AND ISNULL(UPPER(LTRIM(RTRIM(CONVERT(nvarchar(50), inspectionRow.TrangThai)))), N'') <> N'HUY'
          AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.MaPhieu))), N'') IS NOT NULL
    ) AS inspectionRows
) AS materialInspections
OUTER APPLY (
    SELECT
        MAX(outboundRows.ThoiGianXacNhanXuat) AS StepDate,
        MIN(outboundRows.ThoiGianXacNhanXuat) AS FirstOutboundDate,
        JSON_QUERY((
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY outbound.Department, outbound.ThoiGianXacNhanXuat, outbound.MaSoPhieuSoan
                ) AS DetailId,
                ROW_NUMBER() OVER (
                    ORDER BY outbound.Department, outbound.ThoiGianXacNhanXuat, outbound.MaSoPhieuSoan
                ) AS DetailNo,
                outbound.ThoiGianXacNhanXuat AS DetailDate,
                CONCAT(N'Mã phiếu: ', outbound.MaSoPhieuSoan) AS DetailContent,
                CONCAT(N'/api/traceability/print/rm-outbound?id=', outbound.MaSoPhieuSoan) AS DetailLink,
                outbound.Department
            FROM (
                SELECT DISTINCT
                    LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan))) AS MaSoPhieuSoan,
                    outboundRow.ThoiGianXacNhanXuat,
                    CASE
                        WHEN UPPER(LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan)))) LIKE N'NA%' THEN N'Nguyên liệu'
                        WHEN UPPER(LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan)))) LIKE N'PA%' THEN N'Phụ liệu'
                    END AS Department
                FROM dbo.Bravo_PNK_Detail AS detail
                INNER JOIN dbo.Bravo_PNK_Master AS master
                    ON detail.PNKMasterId = master.ReceiptNotesId
                INNER JOIN dbo.WH_PhieuSoanHang AS outboundRow
                    ON outboundRow.ReceiptNotesId = master.ReceiptNotesId
                WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), detail.CustomerCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), customer.CustomerCode)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.SizeCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), tc.TenSize)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), mp.ProductCode)))
                  AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductionOrderNo))) = LTRIM(RTRIM(CONVERT(nvarchar(255), COALESCE(tc.LenhSanXuat, cap.LenhSanXuat))))
                  AND master.DocCode IN (N'NK', N'NM')
                  AND master.DocStatus = 4
                  AND UPPER(LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan)))) LIKE N'[NP]A%'
                  AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan))), N'') IS NOT NULL
            ) AS outbound
            ORDER BY outbound.Department, outbound.ThoiGianXacNhanXuat, outbound.MaSoPhieuSoan
            FOR JSON PATH
        )) AS DetailsJson
    FROM (
        SELECT DISTINCT
            LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan))) AS MaSoPhieuSoan,
            outboundRow.ThoiGianXacNhanXuat
        FROM dbo.Bravo_PNK_Detail AS detail
        INNER JOIN dbo.Bravo_PNK_Master AS master
            ON detail.PNKMasterId = master.ReceiptNotesId
        INNER JOIN dbo.WH_PhieuSoanHang AS outboundRow
            ON outboundRow.ReceiptNotesId = master.ReceiptNotesId
        WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), detail.CustomerCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), customer.CustomerCode)))
          AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.SizeCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), tc.TenSize)))
          AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductCode))) = LTRIM(RTRIM(CONVERT(nvarchar(255), mp.ProductCode)))
          AND LTRIM(RTRIM(CONVERT(nvarchar(255), detail.ProductionOrderNo))) = LTRIM(RTRIM(CONVERT(nvarchar(255), COALESCE(tc.LenhSanXuat, cap.LenhSanXuat))))
          AND master.DocCode IN (N'NK', N'NM')
          AND master.DocStatus = 4
          AND UPPER(LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan)))) LIKE N'[NP]A%'
          AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan))), N'') IS NOT NULL
    ) AS outboundRows
) AS materialOutbound
OUTER APPLY (
    SELECT
        MAX(relaxingRows.ThoiGianTaoPhieu) AS StepDate,
        JSON_QUERY((
            SELECT
                ROW_NUMBER() OVER (ORDER BY relaxing.ThoiGianTaoPhieu, relaxing.IdPhieuXaVai) AS DetailId,
                ROW_NUMBER() OVER (ORDER BY relaxing.ThoiGianTaoPhieu, relaxing.IdPhieuXaVai) AS DetailNo,
                relaxing.ThoiGianTaoPhieu AS DetailDate,
                CONCAT(N'Mã phiếu: ', relaxing.IdPhieuXaVai) AS DetailContent,
                CONCAT(N'/api/traceability/print/fabric-relaxing?id=', relaxing.IdPhieuXaVai) AS DetailLink
            FROM (
                SELECT DISTINCT
                    LTRIM(RTRIM(CONVERT(nvarchar(255), relaxingRow.IdPhieuXaVai))) AS IdPhieuXaVai,
                    relaxingRow.ThoiGianTaoPhieu
                FROM dbo.CUTTING_PhieuXaVai AS relaxingRow
                WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), relaxingRow.MaCay))) =
                      LTRIM(RTRIM(CONVERT(nvarchar(255), tc.MaCay)))
                  AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), relaxingRow.IdPhieuXaVai))), N'') IS NOT NULL
            ) AS relaxing
            ORDER BY relaxing.ThoiGianTaoPhieu, relaxing.IdPhieuXaVai
            FOR JSON PATH
        )) AS DetailsJson
    FROM (
        SELECT DISTINCT
            LTRIM(RTRIM(CONVERT(nvarchar(255), relaxingRow.IdPhieuXaVai))) AS IdPhieuXaVai,
            relaxingRow.ThoiGianTaoPhieu
        FROM dbo.CUTTING_PhieuXaVai AS relaxingRow
        WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), relaxingRow.MaCay))) =
              LTRIM(RTRIM(CONVERT(nvarchar(255), tc.MaCay)))
          AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), relaxingRow.IdPhieuXaVai))), N'') IS NOT NULL
    ) AS relaxingRows
) AS fabricRelaxing
OUTER APPLY (
    SELECT
        MAX(cuttingRows.NgayThang) AS StepDate,
        JSON_QUERY((
            SELECT
                ROW_NUMBER() OVER (ORDER BY cutting.NgayThang, cutting.PhieuHoachToanId) AS DetailId,
                ROW_NUMBER() OVER (ORDER BY cutting.NgayThang, cutting.PhieuHoachToanId) AS DetailNo,
                cutting.NgayThang AS DetailDate,
                CONCAT(N'Mã phiếu: ', cutting.PhieuHoachToanId) AS DetailContent,
                CONCAT(N'/api/traceability/print/fabric-cutting?id=', cutting.PhieuHoachToanId) AS DetailLink
            FROM (
                SELECT DISTINCT
                    LTRIM(RTRIM(CONVERT(nvarchar(255), master.PhieuHoachToanId))) AS PhieuHoachToanId,
                    master.NgayThang
                FROM dbo.CUTTING_PhieuHoachToan AS master
                INNER JOIN dbo.CUTTING_PhieuHoachToan_ChiTiet_NoiCay AS tree
                    ON tree.PhieuHoachToanId = master.PhieuHoachToanId
                WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), tree.MaCay))) =
                      LTRIM(RTRIM(CONVERT(nvarchar(255), tc.MaCay)))
                  AND master.NgayThang IS NOT NULL
            ) AS cutting
            ORDER BY cutting.NgayThang, cutting.PhieuHoachToanId
            FOR JSON PATH
        )) AS DetailsJson
    FROM (
        SELECT DISTINCT
            LTRIM(RTRIM(CONVERT(nvarchar(255), master.PhieuHoachToanId))) AS PhieuHoachToanId,
            master.NgayThang
        FROM dbo.CUTTING_PhieuHoachToan AS master
        INNER JOIN dbo.CUTTING_PhieuHoachToan_ChiTiet_NoiCay AS tree
            ON tree.PhieuHoachToanId = master.PhieuHoachToanId
        WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), tree.MaCay))) =
              LTRIM(RTRIM(CONVERT(nvarchar(255), tc.MaCay)))
          AND master.NgayThang IS NOT NULL
    ) AS cuttingRows
) AS fabricCutting
OUTER APPLY (
    SELECT
        MAX(wipInspectionRows.NgayTao) AS StepDate,
        JSON_QUERY((
            SELECT
                ROW_NUMBER() OVER (ORDER BY wipInspection.NgayTao, wipInspection.IdPhieuKiemTra) AS DetailId,
                ROW_NUMBER() OVER (ORDER BY wipInspection.NgayTao, wipInspection.IdPhieuKiemTra) AS DetailNo,
                wipInspection.NgayTao AS DetailDate,
                CONCAT(N'Mã phiếu: ', wipInspection.IdPhieuKiemTra) AS DetailContent,
                CONCAT(N'/api/traceability/print/wip-inspection?id=', wipInspection.IdPhieuKiemTra) AS DetailLink
            FROM (
                SELECT DISTINCT
                    LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.IdPhieuKiemTra))) AS IdPhieuKiemTra,
                    inspectionRow.NgayTao
                FROM dbo.CUTTING_PhieuHoachToan AS master
                INNER JOIN dbo.CUTTING_PhieuHoachToan_ChiTiet_NoiCay AS tree
                    ON tree.PhieuHoachToanId = master.PhieuHoachToanId
                INNER JOIN dbo.CUTTING_PhieuKiemTraChatLuongBTP AS inspectionRow
                    ON inspectionRow.IdPhieuHoachToan = master.PhieuHoachToanId
                WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), tree.MaCay))) =
                      LTRIM(RTRIM(CONVERT(nvarchar(255), tc.MaCay)))
                  AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.IdPhieuKiemTra))), N'') IS NOT NULL
            ) AS wipInspection
            ORDER BY wipInspection.NgayTao, wipInspection.IdPhieuKiemTra
            FOR JSON PATH
        )) AS DetailsJson
    FROM (
        SELECT DISTINCT
            LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.IdPhieuKiemTra))) AS IdPhieuKiemTra,
            inspectionRow.NgayTao
        FROM dbo.CUTTING_PhieuHoachToan AS master
        INNER JOIN dbo.CUTTING_PhieuHoachToan_ChiTiet_NoiCay AS tree
            ON tree.PhieuHoachToanId = master.PhieuHoachToanId
        INNER JOIN dbo.CUTTING_PhieuKiemTraChatLuongBTP AS inspectionRow
            ON inspectionRow.IdPhieuHoachToan = master.PhieuHoachToanId
        WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), tree.MaCay))) =
              LTRIM(RTRIM(CONVERT(nvarchar(255), tc.MaCay)))
          AND NULLIF(LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.IdPhieuKiemTra))), N'') IS NOT NULL
    ) AS wipInspectionRows
) AS wipInspections
OUTER APPLY (
    SELECT TOP (1)
        LTRIM(RTRIM(CONVERT(nvarchar(255), barcodeRow.PhieuHoachToanId))) AS PhieuHoachToanId,
        barcodeRow.NgayTao AS StepDate,
        JSON_QUERY((
            SELECT
                1 AS DetailId,
                1 AS DetailNo,
                barcodeRow.NgayTao AS DetailDate,
                CONCAT(N'Mã phiếu: ', barcodeRow.PhieuHoachToanId) AS DetailContent,
                CONCAT(N'/api/traceability/print/wip-inbound?id=', barcodeRow.PhieuHoachToanId) AS DetailLink
            FOR JSON PATH
        )) AS DetailsJson
    FROM dbo.CUTTING_PhieuHoachToan AS master
    INNER JOIN dbo.CUTTING_PhieuHoachToan_ChiTiet_NoiCay AS tree
        ON tree.PhieuHoachToanId = master.PhieuHoachToanId
    INNER JOIN dbo.CUTTING_PhieuHoachToan_TemBarCode AS barcodeRow
        ON barcodeRow.PhieuHoachToanId = master.PhieuHoachToanId
    WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), tree.MaCay))) =
          LTRIM(RTRIM(CONVERT(nvarchar(255), tc.MaCay)))
      AND barcodeRow.NgayTao IS NOT NULL
    ORDER BY barcodeRow.NgayTao, barcodeRow.PhieuHoachToanId
) AS wipInbound
OUTER APPLY (
    SELECT JSON_QUERY((
        SELECT
            timeline.TimelineId,
            timeline.StepNo,
            timeline.StepTitle,
            timeline.StepTitleEnglish,
            timeline.StepDate,
            timeline.StepContent,
            CAST(NULL AS nvarchar(max)) AS StepLink,
            JSON_QUERY(timeline.DetailsJson) AS Details
        FROM (
            SELECT
                productDevelopment.TimelineId,
                1 AS StepNo,
                N'Phát triển sản phẩm' AS StepTitle,
                N'Product Development' AS StepTitleEnglish,
                productDevelopment.StepDate,
                N'Danh sách tài liệu kỹ thuật' AS StepContent,
                productDevelopment.DetailsJson
            WHERE productDevelopment.DetailsJson <> N'[]'
            UNION ALL
            SELECT
                CAST(2 AS bigint), 2, N'Số invoice', N'Invoice Number', CAST(NULL AS datetime2),
                N'Danh sách Invoice', invoiceNumbers.DetailsJson
            WHERE invoiceNumbers.DetailsJson <> N'[]'
            UNION ALL
            SELECT
                CAST(3 AS bigint), 3, N'Nhập kho NPL', N'RM Inbound', CAST(NULL AS datetime2),
                N'Danh sách phiếu nhập kho', receiptNotes.DetailsJson
            WHERE receiptNotes.DetailsJson <> N'[]'
            UNION ALL
            SELECT
                CAST(4 AS bigint), 4, N'Kiểm NPL', N'RM Inspection', materialInspections.StepDate,
                N'Danh sách phiếu giám định', materialInspections.DetailsJson
            WHERE materialInspections.DetailsJson <> N'[]'
            UNION ALL
            SELECT
                CAST(5 AS bigint), 5, N'Xuất kho NPL', N'RM Outbound', materialOutbound.StepDate,
                N'Danh sách phiếu xuất kho', materialOutbound.DetailsJson
            WHERE materialOutbound.DetailsJson <> N'[]'
            UNION ALL
            SELECT
                CAST(6 AS bigint), 6, N'Nhận NPL từ kho', N'Receive Materials', materialOutbound.FirstOutboundDate,
                N'Ngày nhận NPL đầu tiên', CAST(N'[]' AS nvarchar(max))
            WHERE materialOutbound.FirstOutboundDate IS NOT NULL
            UNION ALL
            SELECT
                CAST(7 AS bigint), 7, N'Xả vải', N'Fabric Relaxing', fabricRelaxing.StepDate,
                N'Danh sách phiếu xả vải', fabricRelaxing.DetailsJson
            WHERE fabricRelaxing.DetailsJson <> N'[]'
            UNION ALL
            SELECT
                CAST(8 AS bigint), 8, N'Trải vải', N'Fabric Spreading', fabricCutting.StepDate,
                N'Ngày trải vải theo ngày cắt', CAST(N'[]' AS nvarchar(max))
            WHERE fabricCutting.StepDate IS NOT NULL
            UNION ALL
            SELECT
                CAST(9 AS bigint), 9, N'Cắt vải', N'Fabric Cutting', fabricCutting.StepDate,
                N'Danh sách phiếu hoạch toán', fabricCutting.DetailsJson
            WHERE fabricCutting.DetailsJson <> N'[]'
            UNION ALL
            SELECT
                CAST(10 AS bigint), 10, N'Kiểm BTP', N'WIP Inspection', wipInspections.StepDate,
                N'Danh sách phiếu kiểm BTP', wipInspections.DetailsJson
            WHERE wipInspections.DetailsJson <> N'[]'
            UNION ALL
            SELECT
                CAST(11 AS bigint), 11, N'Nhập kho BTP', N'WIP Inbound', wipInbound.StepDate,
                N'Bản ghi nhập kho BTP sớm nhất', wipInbound.DetailsJson
            WHERE wipInbound.StepDate IS NOT NULL
            UNION ALL
            SELECT
                CAST(12 AS bigint), 12, N'Đặt BTP', N'WIP Issuing', wipOrder.StepDate,
                CONCAT(N'Phiếu cấp BTP: ', cap.SoPhieuCapBTP), wipOrder.DetailsJson
            WHERE wipOrder.StepDate IS NOT NULL
            UNION ALL
            SELECT
                CAST(13 AS bigint), 13, N'Xuất BTP', N'WIP Outbound', wipOutbound.StepDate,
                CONCAT(N'Phiếu cấp BTP: ', cap.SoPhieuCapBTP), wipOutbound.DetailsJson
            WHERE wipOutbound.StepDate IS NOT NULL
            UNION ALL
            SELECT
                CAST(15 AS bigint), 15, N'Quét nhận BTP', N'WIP Scanning', wipOutbound.StepDate,
                CONCAT(N'Phiếu cấp BTP: ', cap.SoPhieuCapBTP), wipOutbound.ScanningDetailsJson
            WHERE wipOutbound.StepDate IS NOT NULL
        ) AS timeline
        ORDER BY timeline.StepNo
        FOR JSON PATH
    )) AS TimelineJson
) AS traceabilityTimeline
OPTION (RECOMPILE);
