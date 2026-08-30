import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("..", import.meta.url);
const read = (path) => readFile(new URL(path, root), "utf8");

test("PO query requires exact customer and PO values", async () => {
  const sql = await read("docs/TRACEABILITY-PO-QUERY.sql");

  assert.match(sql, /NULLIF\(@InputCustomer, N''\) IS NULL/);
  assert.match(sql, /NULLIF\(@InputPO, N''\) IS NULL/);
  assert.match(sql, /m\.MaKhachHang = @InputCustomer/);
  assert.match(sql, /m\.PO = @InputPO/);
  assert.doesNotMatch(sql, /(?:MaKhachHang|m\.PO)\s+LIKE\s+@Input/i);

  for (const item of [
    "Nguyên liệu",
    "Phụ liệu",
    "Tem RFID",
    "Tem SHU",
    "Hồ sơ kỹ thuật",
    "Hồ sơ thông quan",
    "Hồ sơ chất lượng",
  ]) {
    assert.match(sql, new RegExp(item));
  }
});

test("LOT query requires exact customer and LOT values", async () => {
  const sql = await read("docs/TRACEABILITY-LOT-QUERY.sql");

  assert.match(sql, /NULLIF\(@InputCustomer, N''\) IS NULL/);
  assert.match(sql, /NULLIF\(@InputLOT, N''\) IS NULL/);
  assert.match(sql, /w\.MaKhachHang = @InputCustomer/);
  assert.match(sql, /w\.LOT = @InputLOT/);
  assert.doesNotMatch(sql, /(?:MaKhachHang|\.LOT)\s+LIKE\s+@Input/i);

  for (const item of [
    "Phiếu kiểm định",
    "Phiếu nhập hàng",
    "Sản phẩm",
    "PO",
    "Hồ sơ chất lượng",
  ]) {
    assert.match(sql, new RegExp(item));
  }
});

test("API rejects blank lookup values and binds named parameters", async () => {
  const [main, database, config, env] = await Promise.all([
    read("iis/backend/app/main.py"),
    read("iis/backend/app/database.py"),
    read("iis/backend/app/config.py"),
    read("iis/backend/.env.example"),
  ]);

  assert.match(main, /if not exact_value:/);
  assert.match(main, /"CustomerCode": customer_value, "PO": po_value/);
  assert.match(main, /"CustomerCode": customer_value, "LOT": lot_value/);
  assert.match(database, /pattern\.sub\(replace, query\)/);
  assert.match(database, /return "\?"/);
  assert.match(config, /sqlquery_po: str/);
  assert.match(config, /sqlquery_lot: str/);
  assert.match(env, /^SQLQUERY_PO=/m);
  assert.match(env, /^SQLQUERY_LOT=/m);
});
