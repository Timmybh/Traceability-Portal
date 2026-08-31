import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("SQL Server reads explicitly use READ COMMITTED", async () => {
  const source = await read("iis/backend/app/database.py");
  assert.match(source, /SET TRANSACTION ISOLATION LEVEL READ COMMITTED/);
});

test("a new lookup clears the previous result before requesting data", async () => {
  const source = await read("iis/frontend/assets/app.js");
  const searchBody = source.slice(source.indexOf("async function search("), source.indexOf('byId("search-form")'));
  assert.ok(searchBody.indexOf("clearCurrentData();") < searchBody.indexOf("await getJson("));
  assert.match(source, /function clearCurrentData\(\)/);
  assert.match(source, /renderSteps\(\[\]\)/);
});

test("running status uses the larger green heartbeat treatment", async () => {
  const [script, styles] = await Promise.all([
    read("iis/frontend/assets/app.js"),
    read("iis/frontend/assets/styles.css"),
  ]);
  assert.match(script, /classList\.toggle\("is-running"/);
  assert.match(styles, /\.search-record\s*\{[^}]*color:\s*#16845b[^}]*font-size:\s*14px/);
  assert.match(styles, /@keyframes status-heartbeat/);
  assert.match(styles, /\.search-record\.is-running\s*\{[^}]*status-heartbeat/);
});

test("RM inspection splits details into material and accessory departments", async () => {
  const [script, styles, env] = await Promise.all([
    read("iis/frontend/assets/app.js"),
    read("iis/frontend/assets/styles.css"),
    read("iis/backend/.env.example"),
  ]);

  assert.match(script, /BỘ PHẬN: NGUYÊN LIỆU/);
  assert.match(script, /BỘ PHẬN: PHỤ LIỆU/);
  assert.match(script, /step\[0\] === "04"/);
  assert.match(script, /detail\.Department/);
  assert.match(script, /department-count/);
  assert.match(styles, /\.department-row/);
  assert.match(env, /d\.BoPhan AS Department/);
});

test("IIS frontend uses the Dong Tien logo, empty image state, and three trace tabs", async () => {
  const [html, script] = await Promise.all([
    read("iis/frontend/index.html"),
    read("iis/frontend/assets/app.js"),
  ]);

  assert.match(html, /dong-tien-logo\.png/);
  assert.match(html, /Truy suất RFID/);
  assert.match(html, /Truy suất PO/);
  assert.match(html, /Truy suất LOT/);
  assert.match(html, /id="image-empty"/);
  assert.doesNotMatch(html, /jacket-line\.png/);
  assert.doesNotMatch(script, /FALLBACK_IMAGE|jacket-line\.png/);
  assert.match(script, /\/api\/traceability\/\$\{type\}/);
});

test("timeline hides the content column and uses an icon-only document preview", async () => {
  const [html, script, styles] = await Promise.all([
    read("iis/frontend/index.html"),
    read("iis/frontend/assets/app.js"),
    read("iis/frontend/assets/styles.css"),
  ]);

  assert.doesNotMatch(html, /NỘI DUNG\s*\/\s*CONTENT/);
  assert.doesNotMatch(script, /<span>Xem chứng từ<\/span>/);
  assert.match(script, /class="preview-link"/);
  assert.match(script, /aria-label="Xem chứng từ"/);
  assert.match(styles, /\.preview-link/);
});

test("PO and LOT tabs include clearly labelled presentation demo data", async () => {
  const [script, styles] = await Promise.all([
    read("iis/frontend/assets/app.js"),
    read("iis/frontend/assets/styles.css"),
  ]);
  assert.match(script, /const lookupDemo =/);
  assert.match(script, /function showLookupDemo\(type\)/);
  assert.match(script, /Dữ liệu minh họa/);
  assert.match(script, /Phiếu kiểm định/);
  assert.match(script, /Hồ sơ thông quan/);
  assert.match(styles, /\.demo-badge/);
});

test("general information uses compact bilingual rows without an inner scrollbar", async () => {
  const styles = await read("iis/frontend/assets/styles.css");
  assert.match(styles, /grid-template-rows:\s*repeat\(16,minmax\(0,1fr\)\)/);
  assert.match(styles, /\.info-row small::before\s*\{\s*content:\s*" \/ "/);
  assert.match(styles, /\.info-card\s*\{[^}]*overflow:\s*hidden/);
  assert.match(styles, /height:\s*clamp\(440px,calc\(100vh - 265px\),780px\)/);
});
