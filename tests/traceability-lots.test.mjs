import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("..", import.meta.url);

test("renders separate main and contrast fabric LOT fields", async () => {
  const html = await readFile(new URL("iis/frontend/index.html", root), "utf8");
  const app = await readFile(new URL("iis/frontend/assets/app.js", root), "utf8");

  assert.match(html, /LOT vải chính<small>Main Fabric LOT<\/small>/);
  assert.match(html, /id="value-main-lot"/);
  assert.match(html, /LOT vải phối<small>Contrast Fabric LOT<\/small>/);
  assert.match(html, /id="value-contrast-lot"/);
  assert.match(app, /field\(data, "LotVaiChinh", "Lot"\)/);
  assert.match(app, /field\(data, "LotVaiPhoi"\)/);
});

test("SQLQUERY uses tracking tables and SQLQUERY_NEW uses the cutting mapping chain", async () => {
  const [env, sqlQueryNew] = await Promise.all([
    readFile(new URL("iis/backend/.env.example", root), "utf8"),
    readFile(new URL("docs/TRACEABILITY-NEW-QUERY.sql", root), "utf8"),
  ]);
  const lines = env.split(/\r?\n/);
  const sqlQuery = lines.find((line) => line.startsWith("SQLQUERY=")) ?? "";

  assert.match(sqlQuery, /FROM dbo\.Tracking_RFID_Master AS m/);
  assert.match(sqlQuery, /FROM dbo\.Tracking_RFID_Master_TimeLine AS t/);
  assert.match(sqlQuery, /FROM dbo\.Tracking_RFID_Master_TimeLine_Detail AS d/);
  assert.match(sqlQuery, /m\.XiNghiep,m\.ChuyenMay/);
  assert.match(sqlQuery, /m\.BanCat,m\.Lot,m\.NgaySanXuat/);
  assert.doesNotMatch(sqlQuery, /CUTTING_PhieuCapBTP|LotVaiChinh|LotVaiPhoi/);
  assert.match(sqlQueryNew, /CUTTING_TemBarcode_TachCay_RFID_Mapping/);
  assert.match(sqlQueryNew, /tc\.Code\s*=\s*mp\.BarcodeTachCay/);
  assert.match(sqlQueryNew, /d\.SoPhieuCapBTP\s*=\s*cap\.SoPhieuCapBTP/);
  assert.match(sqlQueryNew, /d\.IdCapBTPCT\s*=\s*cap\.IdCapBTPCT/);
  assert.match(sqlQueryNew, /mainFabric\.LotVaiChinh/);
  assert.match(sqlQueryNew, /bc\.TemBarcodeBTP\s*=\s*tc\.Barcode/);
  assert.match(sqlQueryNew, /bc\.ChungLoai LIKE N'%phối%'/);
  assert.match(sqlQueryNew, /Bravo_DonDatHangBan_Master/);
  assert.match(sqlQueryNew, /Lib_KhachHang/);
  assert.match(sqlQueryNew, /CUTTING_PhieuCapBTP_ChiTiet/);
  assert.match(sqlQueryNew, /cap\.TenMau AS Color/);
  assert.match(sqlQueryNew, /CAST\(NULL AS nvarchar\(500\)\) AS Art/);
  assert.match(sqlQueryNew, /Cutting_PhieuDieuTietGiacSoDo_ChiTiet_BanMay AS bm/);
  assert.match(sqlQueryNew, /LEFT JOIN dbo\.Cutting_PhieuDieuTietGiacSoDo_ChiTiet_BanMay AS bm\s+ON CONVERT\(nvarchar\(100\), bm\.IdBanMay\)\s*=\s*CONVERT\(nvarchar\(100\), tc\.IdBanMay\)/);
  assert.match(sqlQueryNew, /bm\.BanCat/);
  assert.doesNotMatch(sqlQueryNew, /tc\.BanMay/);
  assert.doesNotMatch(sqlQueryNew, /cutTable\.BanCat/);
  assert.doesNotMatch(sqlQueryNew, /Lib_NguyenPhuLieu_Barvo/);
  assert.match(sqlQueryNew, /mp\.ThoiGianMap AS NgaySanXuat/);
  assert.match(sqlQueryNew, /TEC_ThongTinTaiLieukyThuat AS document/);
  assert.match(sqlQueryNew, /TEC_ProductInformation AS product/);
  assert.match(sqlQueryNew, /TEC_LoaiTaiLieuKyThuat AS documentTypeRow/);
  assert.match(sqlQueryNew, /TRY_CONVERT\(bigint, document\.IdMaster\)\s*=\s*product\.Id/);
  assert.equal(
    (sqlQueryNew.match(/LTRIM\(RTRIM\(document\.TrangThai\)\) = N'Đã ban hành'/g) || []).length,
    2,
    "published-document filtering must apply to both details and summary",
  );
  assert.match(sqlQueryNew, /product\.ProductCode/);
  assert.match(sqlQueryNew, /product\.SeasonCode/);
  assert.match(sqlQueryNew, /1 AS StepNo/);
  assert.match(sqlQueryNew, /N'Phát triển sản phẩm' AS StepTitle/);
  assert.match(sqlQueryNew, /Bravo_PNK_Detail AS detail/);
  assert.match(sqlQueryNew, /detail\.AtchDocNo/);
  assert.doesNotMatch(sqlQueryNew, /detail\.SalesContractsNo/);
  assert.match(sqlQueryNew, /detail\.CustomerCode/);
  assert.match(sqlQueryNew, /detail\.SizeCode/);
  assert.match(sqlQueryNew, /detail\.ProductCode/);
  assert.match(sqlQueryNew, /detail\.ProductionOrderNo/);
  assert.match(sqlQueryNew, /INNER JOIN dbo\.Bravo_PNK_Master AS master\s+ON detail\.PNKMasterId = master\.Id/);
  assert.match(sqlQueryNew, /master\.DocNo/);
  assert.match(sqlQueryNew, /master\.DocCode IN \(N'NK', N'NM'\)/);
  assert.match(sqlQueryNew, /master\.DocStatus = 4/);
  const receiptEnd = sqlQueryNew.indexOf(") AS receiptNotes");
  const receiptCondition = sqlQueryNew.slice(
    sqlQueryNew.lastIndexOf("FROM dbo.Bravo_PNK_Detail AS detail", receiptEnd),
    receiptEnd,
  );
  assert.match(receiptCondition, /Bravo_PNK_Detail AS detail/);
  assert.doesNotMatch(receiptCondition, /Bravo_PNK_Detail_DonHang/);
  assert.doesNotMatch(receiptCondition, /detail\.CustomerCode/);
  assert.match(receiptCondition, /master\.CustomerCode/);
  assert.match(receiptCondition, /Bravo_BCD_Detail AS balance/);
  assert.match(receiptCondition, /detail\.BalanceNo/);
  assert.match(receiptCondition, /balance\.BalanceNo/);
  assert.match(receiptCondition, /balance\.ProductCode/);
  assert.match(receiptCondition, /balance\.SeasonCode/);
  assert.match(receiptCondition, /COALESCE\(tc\.Mua, cap\.SeasonCode\)/);
  assert.doesNotMatch(receiptCondition, /detail\.SizeCode/);
  assert.doesNotMatch(receiptCondition, /detail\.ProductionOrderNo/);
  assert.match(sqlQueryNew, /WHEN N'NK' THEN N'Nguyên liệu'/);
  assert.match(sqlQueryNew, /WHEN N'NM' THEN N'Phụ liệu'/);
  assert.match(sqlQueryNew, /2, N'Số invoice', N'Invoice Number'/);
  assert.match(sqlQueryNew, /3, N'Nhập kho NPL', N'RM Inbound'/);
  assert.match(sqlQueryNew, /WH_PhieuGiamDinh AS inspectionRow/);
  assert.match(sqlQueryNew, /inspectionRow\.ReceiptNotesId = master\.ReceiptNotesId/);
  assert.match(sqlQueryNew, /inspectionRow\.LoaiGiamDinh/);
  assert.match(sqlQueryNew, /inspectionRow\.MaPhieu/);
  assert.match(sqlQueryNew, /inspectionRow\.NgayGiamDinh/);
  assert.equal(
    (sqlQueryNew.match(/inspectionRow\.TrangThai\)\)\)\), N''\) <> N'HUY'/g) || []).length,
    2,
    "cancelled inspections must be excluded from both details and summary",
  );
  assert.match(sqlQueryNew, /WHEN N'nl' THEN N'Nguyên liệu'/);
  assert.match(sqlQueryNew, /WHEN N'pl' THEN N'Phụ liệu'/);
  assert.match(sqlQueryNew, /4, N'Kiểm NPL', N'RM Inspection'/);
  assert.match(sqlQueryNew, /WH_PhieuSoanHang AS outboundRow/);
  assert.match(sqlQueryNew, /outboundRow\.ReceiptNotesId = master\.ReceiptNotesId/);
  assert.match(sqlQueryNew, /outboundRow\.MaSoPhieuSoan/);
  assert.match(sqlQueryNew, /outboundRow\.ThoiGianXacNhanXuat/);
  assert.match(sqlQueryNew, /LIKE N'\[NP\]A%'/);
  assert.match(sqlQueryNew, /5, N'Xuất kho NPL', N'RM Outbound'/);
  assert.match(sqlQueryNew, /MIN\(outboundRows\.ThoiGianXacNhanXuat\) AS FirstOutboundDate/);
  assert.match(sqlQueryNew, /6, N'Nhận NPL từ kho', N'Receive Materials', materialOutbound\.FirstOutboundDate/);
  assert.match(sqlQueryNew, /CUTTING_PhieuXaVai AS relaxingRow/);
  assert.match(sqlQueryNew, /relaxingRow\.MaCay/);
  assert.match(sqlQueryNew, /tc\.MaCay/);
  assert.match(sqlQueryNew, /relaxingRow\.IdPhieuXaVai/);
  assert.match(sqlQueryNew, /relaxingRow\.ThoiGianTaoPhieu/);
  assert.match(sqlQueryNew, /7, N'Xả vải', N'Fabric Relaxing'/);
  assert.match(sqlQueryNew, /CUTTING_PhieuHoachToan AS master/);
  assert.match(sqlQueryNew, /CUTTING_PhieuHoachToan_ChiTiet_NoiCay AS tree/);
  assert.match(sqlQueryNew, /tree\.PhieuHoachToanId = master\.PhieuHoachToanId/);
  assert.match(sqlQueryNew, /tree\.MaCay/);
  assert.match(sqlQueryNew, /master\.NgayThang/);
  assert.match(sqlQueryNew, /8, N'Trải vải', N'Fabric Spreading', fabricCutting\.StepDate/);
  assert.match(sqlQueryNew, /9, N'Cắt vải', N'Fabric Cutting', fabricCutting\.StepDate/);
  assert.match(sqlQueryNew, /CUTTING_PhieuKiemTraChatLuongBTP AS inspectionRow/);
  assert.match(sqlQueryNew, /inspectionRow\.IdPhieuHoachToan = master\.PhieuHoachToanId/);
  assert.match(sqlQueryNew, /inspectionRow\.IdPhieuKiemTra/);
  assert.match(sqlQueryNew, /inspectionRow\.NgayTao/);
  assert.match(sqlQueryNew, /10, N'Kiểm BTP', N'WIP Inspection'/);
  assert.match(sqlQueryNew, /CUTTING_PhieuHoachToan_TemBarCode AS barcodeRow/);
  assert.match(sqlQueryNew, /barcodeRow\.PhieuHoachToanId = master\.PhieuHoachToanId/);
  assert.match(sqlQueryNew, /barcodeRow\.NgayTao AS StepDate/);
  assert.match(sqlQueryNew, /ORDER BY barcodeRow\.NgayTao, barcodeRow\.PhieuHoachToanId/);
  assert.match(sqlQueryNew, /11, N'Nhập kho BTP', N'WIP Inbound'/);
  assert.match(sqlQueryNew, /p\.NgayDuyet/);
  assert.match(sqlQueryNew, /cap\.SoPhieuCapBTP/);
  assert.match(sqlQueryNew, /cap\.TenXiNghiep/);
  assert.match(sqlQueryNew, /cap\.TenCum/);
  assert.match(sqlQueryNew, /cap\.LenhSanXuat/);
  assert.match(sqlQueryNew, /12, N'Đặt BTP', N'WIP Issuing'/);
  assert.match(sqlQueryNew, /p\.NgayNhanBTP/);
  assert.match(sqlQueryNew, /cap\.NgayNhanBTP AS StepDate/);
  assert.match(sqlQueryNew, /13, N'Xuất BTP', N'WIP Outbound'/);
  assert.match(sqlQueryNew, /15, N'Quét nhận BTP', N'WIP Scanning', wipOutbound\.StepDate/);
  assert.match(sqlQueryNew, /COALESCE\(traceabilityTimeline\.TimelineJson, JSON_QUERY\(N'\[\]'\)\) AS TimelineJson/);
  assert.doesNotMatch(sqlQueryNew, /Tracking_RFID_Master(?:\s|AS)/);
  assert.doesNotMatch(sqlQueryNew, /Tracking_RFID_Master_TimeLine/);
  assert.match(sqlQueryNew, /Tracking_RFID_Master_Image/);
});
