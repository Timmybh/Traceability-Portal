DECLARE @InputRFID nvarchar(255) = LTRIM(RTRIM(@RFID));
DECLARE @NormalizedRFID nvarchar(255) =
    REPLACE(REPLACE(REPLACE(@InputRFID, N'(', N''), N')', N''), N' ', N'');

WITH MasterRow AS (
    SELECT TOP (1)
        m.Id, m.RFID, m.RFID_Hex, m.PO, m.LenhSanXuat, m.KhachHang,
        m.MaHang, m.Color, m.Size, m.SizeCode, m.Season, m.MaKhachHang,
        m.ColorCode, m.Lot, m.NgaySanXuat, m.BanCat, m.ChuyenMay,
        m.ItemId, m.XiNghiep, m.Art, m.ThoiGianTao,
        m.ThoiGianCapNhatMoiNhat, m.NormalizeRFID
    FROM dbo.Tracking_RFID_Master AS m
    WHERE m.RFID = @InputRFID
       OR m.RFID = @NormalizedRFID
       OR m.NormalizeRFID = @NormalizedRFID
       OR m.RFID_Hex = @InputRFID
       OR m.RFID_Hex = @NormalizedRFID
       OR m.RFID_Copy = @InputRFID
       OR m.RFID_Copy = @NormalizedRFID
    ORDER BY
        CASE
            WHEN m.RFID = @InputRFID THEN 0
            WHEN m.RFID = @NormalizedRFID THEN 1
            WHEN m.NormalizeRFID = @NormalizedRFID THEN 2
            WHEN m.RFID_Hex = @InputRFID THEN 3
            WHEN m.RFID_Hex = @NormalizedRFID THEN 4
            WHEN m.RFID_Copy = @InputRFID THEN 5
            ELSE 6
        END,
        m.ThoiGianCapNhatMoiNhat DESC,
        m.Id DESC
)
SELECT
    m.RFID,
    m.KhachHang AS TenNgan,
    m.PO,
    m.MaHang AS ProductCode,
    m.ItemId,
    m.Size,
    m.Art,
    m.Color,
    m.Season,
    m.XiNghiep,
    m.ChuyenMay,
    m.LenhSanXuat,
    m.BanCat,
    m.Lot,
    m.NgaySanXuat,
    JSON_QUERY((
        SELECT
            t.IdTimeLine AS TimelineId,
            t.STT AS StepNo,
            t.TieuDe AS StepTitle,
            RTRIM(t.TieuDeTiengAnh) AS StepTitleEnglish,
            t.Ngay AS StepDate,
            t.NoiDung AS StepContent,
            t.LinkTimeLine AS StepLink,
            JSON_QUERY((
                SELECT
                    d.IdTimeLine_Detail AS DetailId,
                    d.STT AS DetailNo,
                    d.Ngay AS DetailDate,
                    d.NoiDung AS DetailContent,
                    d.Link AS DetailLink,
                    d.BoPhan AS Department,
                    d.MaPhieu AS DocumentCode,
                    d.IdPhieu AS DocumentId
                FROM dbo.Tracking_RFID_Master_TimeLine_Detail AS d
                WHERE d.IdTimeLine = t.IdTimeLine
                ORDER BY d.STT, d.IdTimeLine_Detail
                FOR JSON PATH
            )) AS Details
        FROM dbo.Tracking_RFID_Master_TimeLine AS t
        WHERE t.RFID = m.RFID
        ORDER BY t.STT, t.IdTimeLine
        FOR JSON PATH
    )) AS TimelineJson
FROM MasterRow AS m;
