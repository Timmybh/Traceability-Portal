SELECT TOP (1)
    inspectionRow.*,
    JSON_QUERY((
        SELECT detail.*
        FROM dbo.Bravo_PNK_Detail AS detail
        WHERE detail.PNKMasterId = inspectionRow.ReceiptNotesId
        FOR JSON PATH
    )) AS ReceiptDetailsJson
FROM dbo.WH_PhieuGiamDinh AS inspectionRow
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.MaPhieu))) = @DocumentId;
