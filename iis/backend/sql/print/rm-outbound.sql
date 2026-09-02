SELECT TOP (1)
    outboundRow.*,
    JSON_QUERY((
        SELECT detail.*
        FROM dbo.Bravo_PNK_Detail AS detail
        WHERE detail.PNKMasterId = outboundRow.ReceiptNotesId
        FOR JSON PATH
    )) AS ReceiptDetailsJson
FROM dbo.WH_PhieuSoanHang AS outboundRow
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), outboundRow.MaSoPhieuSoan))) = @DocumentId;
