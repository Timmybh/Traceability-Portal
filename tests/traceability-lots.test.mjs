import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("..", import.meta.url);

test("renders main and contrast fabric LOT fields", async () => {
  const html = await readFile(new URL("iis/frontend/index.html", root), "utf8");
  const app = await readFile(new URL("iis/frontend/assets/app.js", root), "utf8");

  assert.match(html, /LOT vải chính/);
  assert.match(html, /id="value-main-fabric-lot"/);
  assert.match(html, /LOT vải phối/);
  assert.match(html, /id="value-contrast-fabric-lot"/);
  assert.match(app, /field\(data, "LotVaiChinh", "Lot"\)/);
  assert.match(app, /field\(data, "LotVaiPhoi"\)/);
});

test("SQL query aggregates every distinct matching contrast-fabric LOT", async () => {
  const env = await readFile(new URL("iis/backend/.env.example", root), "utf8");
  const sqlQuery = env.split(/\r?\n/).find((line) => line.startsWith("SQLQUERY=")) ?? "";

  assert.match(sqlQuery, /m\.Lot AS LotVaiChinh/);
  assert.match(sqlQuery, /phoi\.LotVaiPhoi/);
  assert.match(sqlQuery, /SELECT DISTINCT LTRIM\(RTRIM\(ct\.Lot\)\) AS Lot/);
  assert.match(sqlQuery, /ct\.PO=m\.PO/);
  assert.match(sqlQuery, /cap\.ProductCode=m\.MaHang/);
  assert.match(sqlQuery, /cap\.TenCum=m\.ChuyenMay/);
  assert.match(sqlQuery, /LIKE N'%phối%'/);
});
