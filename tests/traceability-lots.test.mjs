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
  assert.match(sqlQueryNew, /LIKE N'%phối%'/);
  assert.match(sqlQueryNew, /Bravo_DonDatHangBan_Master/);
  assert.match(sqlQueryNew, /Lib_KhachHang/);
  assert.match(sqlQueryNew, /CUTTING_PhieuCapBTP_ChiTiet/);
  assert.match(sqlQueryNew, /cap\.TenMau AS Color/);
  assert.match(sqlQueryNew, /CAST\(NULL AS nvarchar\(500\)\) AS Art/);
  assert.match(sqlQueryNew, /cutTable\.BanCat/);
  assert.match(sqlQueryNew, /exportBarcode\.BarCode = tc\.Barcode/);
  assert.match(sqlQueryNew, /cutDetail\.Id = exportBarcode\.ChiTietPhieuDieuTietId/);
  assert.doesNotMatch(sqlQueryNew, /Lib_NguyenPhuLieu_Barvo/);
  assert.match(sqlQueryNew, /mp\.ThoiGianMap AS NgaySanXuat/);
  assert.match(sqlQueryNew, /JSON_QUERY\(N'\[\]'\) AS TimelineJson/);
  assert.doesNotMatch(sqlQueryNew, /Tracking_RFID/);
});
