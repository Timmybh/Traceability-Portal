-- CHƯA XÁC MINH VỚI DB THẬT (viết lúc DB đang off).
-- Chỉ 3 cột dưới đây là chắc chắn đúng vì đã dùng ở nơi khác trong hệ thống
-- (xem docs/TRACEABILITY-NEW-QUERY.sql, nhánh timeline "Kiểm BTP"):
--   inspectionRow.IdPhieuKiemTra, inspectionRow.NgayTao, inspectionRow.IdPhieuHoachToan
-- Tất cả các cột còn lại đang là CAST(NULL...)/mảng rỗng placeholder, cần thay
-- bằng bảng/cột thật khi có DB. GIỮ NGUYÊN TÊN CỘT OUTPUT (Factory, Line, Style,
-- ... DetailsJson, RecheckDetailsJson) vì hàm _wip_inspection_print_html() trong
-- iis/backend/app/main.py đọc đúng các tên này để render mẫu BM 02 HD 10-03.
--
-- Cấu trúc 1 phần tử của DetailsJson / RecheckDetailsJson (mảng chi tiết cắt):
-- {
--   "PartName": "TAY PHẢI",
--   "Sheets": [                          -- tối đa 3 "lá kiểm", mỗi lá 1 size
--     {"Size": "UK6-8/EUS", "T": "OK", "G": "OK", "D": "OK"},
--     {"Size": null, "T": null, "G": null, "D": null},
--     {"Size": null, "T": null, "G": null, "D": null}
--   ],
--   "DefectDescription": "",             -- Mô tả lỗi (lần 1)
--   "QcLeaderConfirm": "NGUYỄN THỊ THÙY TRANG",  -- Tổ trưởng ký xác nhận lỗi
--   "Recheck": {"T": null, "G": null, "D": null}, -- Kiểm lần 2
--   "RecheckDefectDescription": "",      -- Mô tả lỗi (kiểm lần 2)
--   "ReplacementConfirm": "NGUYỄN THỊ THÙY TRANG" -- Thay thân xác nhận
-- }
-- Quy ước giá trị T/G/D: null/"" = chưa kiểm; "OK" = đạt (renderer vẽ ✓);
-- chuỗi khác = mã lỗi, hiển thị nguyên văn (không đạt).
SELECT
    inspectionRow.IdPhieuKiemTra,
    inspectionRow.IdPhieuHoachToan,
    inspectionRow.NgayTao AS InspectionDate,
    CAST(NULL AS nvarchar(50))  AS Factory,           -- Xí nghiệp
    CAST(NULL AS nvarchar(50))  AS Line,              -- Tổ
    CAST(NULL AS nvarchar(100)) AS Style,             -- Mã hàng
    CAST(NULL AS nvarchar(50))  AS Season,            -- Mùa
    CAST(NULL AS nvarchar(100)) AS ProductionOrder,   -- Lệnh
    CAST(NULL AS nvarchar(50))  AS CuttingTable,      -- Bàn cắt
    CAST(NULL AS nvarchar(50))  AS SewingTable,       -- Bàn may
    CAST(NULL AS nvarchar(50))  AS Quantities,        -- Số lượng, vd "10 x 3"
    CAST(NULL AS nvarchar(50))  AS FabricArt,         -- Art vải
    CAST(NULL AS nvarchar(100)) AS Voc,               -- Vóc
    CAST(NULL AS nvarchar(20))  AS FormNo,            -- vd "BM 02 HD 10-03" (renderer tự điền mặc định nếu NULL)
    CAST(NULL AS nvarchar(10))  AS RevisionNo,        -- Số lần sửa đổi (renderer mặc định "08" nếu NULL)
    CAST(NULL AS nvarchar(100)) AS Inspector,         -- Người kiểm (QC)
    CAST(NULL AS nvarchar(100)) AS QcLeader,          -- Tổ trưởng QC
    CAST(N'[]' AS nvarchar(max)) AS DetailsJson,         -- TODO: mảng chi tiết cắt + lá kiểm, xem cấu trúc ở trên
    CAST(N'[]' AS nvarchar(max)) AS RecheckDetailsJson   -- TODO: mảng "Kiểm lại (sau khi thay thân)", cùng cấu trúc
FROM dbo.CUTTING_PhieuKiemTraChatLuongBTP AS inspectionRow
WHERE LTRIM(RTRIM(CONVERT(nvarchar(255), inspectionRow.IdPhieuKiemTra))) = @DocumentId;
