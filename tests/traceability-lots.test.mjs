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
  assert.match(sqlQueryNew, /INNER JOIN dbo\.Cutting_PhieuDieuTietGiacSoDo_ChiTiet_BanMay AS bm\s+ON bm\.IdBanMay = tc\.IdBanMay/);
  assert.match(sqlQueryNew, /bm\.BanCat/);
  assert.doesNotMatch(sqlQueryNew, /tc\.BanMay/);
  assert.doesNotMatch(sqlQueryNew, /cutTable\.BanCat/);
  assert.doesNotMatch(sqlQueryNew, /Lib_NguyenPhuLieu_Barvo/);
  assert.match(sqlQueryNew, /mp\.ThoiGianMap AS NgaySanXuat/);
  assert.match(sqlQueryNew, /TEC_ThongTinTaiLieukyThuat AS document/);
  assert.match(sqlQueryNew, /TEC_ProductInformation AS product/);
  assert.match(sqlQueryNew, /TEC_LoaiTaiLieuKyThuat AS documentTypeRow/);
  assert.match(sqlQueryNew, /document\.IdMaster\s*=\s*product\.Id/);
  assert.match(sqlQueryNew, /product\.ProductCode/);
  assert.match(sqlQueryNew, /product\.SeasonCode/);
  assert.match(sqlQueryNew, /1 AS StepNo/);
  assert.match(sqlQueryNew, /N'Phát triển sản phẩm' AS StepTitle/);
  assert.match(sqlQueryNew, /COALESCE\(productDevelopment\.TimelineJson, JSON_QUERY\(N'\[\]'\)\) AS TimelineJson/);
  assert.doesNotMatch(sqlQueryNew, /Tracking_RFID/);
});
