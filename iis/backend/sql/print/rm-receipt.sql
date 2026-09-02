SELECT TOP (1)
    master.*,
    JSON_QUERY((
        SELECT detail.*
        FROM dbo.Bravo_PNK_Detail AS detail
        WHERE detail.PNKMasterId = master.ReceiptNotesId
        FOR JSON PATH
    )) AS DetailsJson
FROM dbo.Bravo_PNK_Master AS master
WHERE CONVERT(nvarchar(255), master.ReceiptNotesId) = @DocumentId;
