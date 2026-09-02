SELECT detail.*
FROM dbo.Bravo_PNK_Detail AS detail
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), detail.AtchDocNo))) = @DocumentId;
