SELECT relaxingRow.*
FROM dbo.CUTTING_PhieuXaVai AS relaxingRow
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), relaxingRow.IdPhieuXaVai))) = @DocumentId;
