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
  assert.match(sqlQueryNew, /Bravo_LenhSanXuat_Detail_PO AS productionOrder/);
  assert.match(sqlQueryNew, /productionOrder\.ProductCode/);
  assert.match(sqlQueryNew, /productionOrder\.PO/);
  assert.match(sqlQueryNew, /productionOrder\.SizeCode/);
  assert.match(sqlQueryNew, /productionOrder\.Size_Item/);
  assert.match(sqlQueryNew, /productionItem\.ItemId/);
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
  const receiptStart = sqlQueryNew.indexOf("FROM dbo.WH_ChiTietPhieuGiamDinh_Cay AS receiptTree");
  const receiptEnd = sqlQueryNew.indexOf(") AS receiptNotes", receiptStart);
  const receiptCondition = sqlQueryNew.slice(receiptStart, receiptEnd);
  assert.match(receiptCondition, /WH_ChiTietPhieuGiamDinh_Cay AS receiptTree/);
  assert.match(receiptCondition, /WH_ChiTietPhieuGiamDinh AS receiptDetail/);
  assert.match(receiptCondition, /WH_PhieuGiamDinh AS receiptInspection/);
  assert.match(receiptCondition, /receiptDetail\.CTPGDId = receiptTree\.CTPGDId/);
  assert.match(receiptCondition, /receiptInspection\.PGDId = receiptDetail\.PGDId/);
  assert.match(receiptCondition, /receiptTree\.MaCay/);
  assert.match(receiptCondition, /tc\.MaCay/);
  assert.match(receiptCondition, /receiptInspection\.MaPhieu/);
  assert.match(receiptCondition, /receiptInspection\.LoaiGiamDinh/);
  assert.match(receiptCondition, /receipt\.NgayGiamDinh/);
  assert.doesNotMatch(receiptCondition, /Bravo_PNK_Master/);
  assert.doesNotMatch(receiptCondition, /Bravo_PNK_Detail/);
  assert.doesNotMatch(receiptCondition, /Bravo_PNK_Detail_DonHang/);
  assert.match(sqlQueryNew, /2, N'Số invoice', N'Invoice Number'/);
  assert.match(sqlQueryNew, /3, N'Nhập kho NPL', N'RM Inbound'/);
  assert.match(sqlQueryNew, /QM_PhieuKiemVai AS inspectionRow/);
  assert.match(sqlQueryNew, /QM_PhieuKiemVai_CayVai AS inspectionTree/);
  assert.match(sqlQueryNew, /inspectionRow\.PKVId = inspectionTree\.PKVId/);
  assert.match(sqlQueryNew, /inspectionTree\.Lot/);
  assert.match(sqlQueryNew, /inspectionRow\.LOT/);
  assert.match(sqlQueryNew, /inspectionRow\.Item/);
  assert.match(sqlQueryNew, /mp\.ProductCode/);
  assert.match(sqlQueryNew, /inspectionRow\.SoPhieuKiem/);
  assert.match(sqlQueryNew, /inspectionRow\.NgayKiemVai/);
  assert.equal(
    (sqlQueryNew.match(/inspectionRow\.TrangThai\)\)\)\), N''\) <> N'HUY'/g) || []).length,
    2,
    "cancelled inspections must be excluded from both details and summary",
  );
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
