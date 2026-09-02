SELECT inspectionRow.*
FROM dbo.CUTTING_PhieuKiemTraChatLuongBTP AS inspectionRow
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.IdPhieuKiemTra))) = @DocumentId;
