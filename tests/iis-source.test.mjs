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
  const searchStart = source.indexOf("async function search(");
  const searchBody = source.slice(searchStart, source.indexOf('byId("search-form").addEventListener', searchStart));
  assert.ok(searchBody.indexOf("clearCurrentData();") < searchBody.indexOf("await getJson("));
  assert.match(source, /function clearCurrentData\(\)/);
  assert.match(source, /renderSteps\(\[\]\)/);
});

test("lookup status transitions from gray heartbeat to navy data heartbeat then complete", async () => {
  const [script, styles] = await Promise.all([
    read("iis/frontend/assets/app.js"),
    read("iis/frontend/assets/styles.css"),
  ]);
  assert.match(script, /classList\.toggle\("has-data", phase === "data" \|\| phase === "complete"\)/);
  assert.match(script, /classList\.toggle\("is-complete", phase === "complete"\)/);
  assert.match(styles, /\.search-record\s*\{[^}]*color:\s*#94a3b8[^}]*status-heartbeat/);
  assert.match(styles, /\.search-record\.has-data\s*\{[^}]*color:\s*#4b55c7[^}]*status-found-zoom \.5s[^}]*status-heartbeat 1\.15s[^}]*\.5s infinite/);
  assert.match(styles, /@keyframes status-heartbeat\s*\{/);
  assert.match(styles, /50%\s*\{\s*opacity:\s*\.52;\s*\}/);
  assert.doesNotMatch(styles, /@keyframes status-heartbeat\s*\{[^@]*scale\(/);
  assert.match(styles, /@keyframes status-found-zoom\s*\{/);
  assert.match(styles, /from\s*\{[^}]*scale\(1\.2\)/);
  assert.match(styles, /to\s*\{[^}]*scale\(1\)/);
  assert.match(styles, /\.search-record\.is-complete\s*\{[^}]*animation:\s*none/);
});

test("RM inspection splits details into material and accessory departments", async () => {
  const [script, styles, env] = await Promise.all([
    read("iis/frontend/assets/app.js"),
    read("iis/frontend/assets/styles.css"),
    read("iis/backend/.env.example"),
  ]);

  assert.match(script, /BỘ PHẬN: NGUYÊN LIỆU/);
  assert.match(script, /BỘ PHẬN: PHỤ LIỆU/);
  assert.match(script, /detail\.Department/);
  assert.match(script, /department-count/);
  assert.match(styles, /\.department-row/);
  assert.match(script, /\["03", "04", "05"\]\.includes\(step\[0\]\)/);
  assert.match(env, /d\.BoPhan AS Department/);
});

test("IIS frontend uses the Dong Tien logo, empty image state, and trace-mode selector", async () => {
  const [html, script, styles] = await Promise.all([
    read("iis/frontend/index.html"),
    read("iis/frontend/assets/app.js"),
    read("iis/frontend/assets/styles.css"),
  ]);

  assert.match(html, /dong-tien-logo\.png/);
  assert.match(html, /Truy suất RFID/);
  assert.match(html, /Truy suất RFID mới/);
  assert.match(html, /Truy suất PO/);
  assert.match(html, /Truy suất LOT/);
  assert.match(html, /id="trace-mode-select"/);
  assert.doesNotMatch(html, /class="trace-tabs"/);
  assert.match(html, /id="image-empty"/);
  assert.doesNotMatch(html, /jacket-line\.png/);
  assert.doesNotMatch(script, /FALLBACK_IMAGE|jacket-line\.png/);
  assert.match(script, /\/api\/traceability\/\$\{type\}/);
  assert.match(script, /state\.traceMode === "rfid-new"/);
  assert.match(script, /"\/api\/traceability\/new"/);
  assert.doesNotMatch(script, /Tab này sử dụng SQLQUERY_NEW/);
  assert.match(script, /trace-mode-select/);
  assert.match(styles, /\.step-parent-row td \{ height: 66px/);
  assert.match(styles, /\.step-detail-row td \{ height: 48px/);
  assert.match(styles, /\.department-row td \{ height: 44px/);
});

test("new RFID endpoint executes SQLQUERY_NEW", async () => {
  const [api, config] = await Promise.all([
    read("iis/backend/app/main.py"),
    read("iis/backend/app/config.py"),
  ]);
  assert.match(config, /sqlquery_new: str \| None = None/);
  assert.match(config, /sqlquery_new_file: str \| None = None/);
  assert.match(api, /@app\.get\("\/api\/traceability\/new"\)/);
  assert.match(api, /_traceability_by_query\(rfid, _new_traceability_query\(\), response, image_source="new"\)/);
});

test("new RFID query is seek-oriented and has a production index script", async () => {
  const [query, indexes, deploy, env] = await Promise.all([
    read("docs/TRACEABILITY-NEW-QUERY.sql"),
    read("docs/TRACEABILITY-NEW-INDEXES.sql"),
    read("iis/deploy/windows/deploy-iis.ps1"),
    read("iis/backend/.env.example"),
  ]);
  assert.match(query, /WITH MappingRow AS/);
  assert.doesNotMatch(query, /WITH MappingCandidates AS/);
  assert.match(query, /mp\.RFID IN \(@InputRFID, @NormalizedRFID\)/);
  assert.match(query, /OPTION \(RECOMPILE\)/);
  assert.match(indexes, /IX_RFIDMapping_RFID/);
  assert.match(indexes, /IX_BarcodeChiTiet_SoPhieu_PO/);
  assert.match(deploy, /TRACEABILITY-NEW-QUERY\.sql/);
  assert.match(env, /^SQLQUERY_NEW_FILE=sql\/TRACEABILITY-NEW-QUERY\.sql$/m);
});

test("non-PDF timeline documents use named parameterized print queries", async () => {
  const [query, api, invoice, receipt, inspection, outbound] = await Promise.all([
    read("docs/TRACEABILITY-NEW-QUERY.sql"),
    read("iis/backend/app/main.py"),
    read("iis/backend/sql/print/invoice.sql"),
    read("iis/backend/sql/print/rm-receipt.sql"),
    read("iis/backend/sql/print/rm-inspection.sql"),
    read("iis/backend/sql/print/rm-outbound.sql"),
  ]);
  assert.match(api, /_PRINT_QUERY_TYPES/);
  assert.match(api, /@app\.get\("\/api\/traceability\/print\/\{document_type\}"/);
  assert.match(api, /\{"DocumentId": value\}/);
  assert.match(query, /\/api\/traceability\/print\/invoice\?id=/);
  assert.match(query, /\/api\/traceability\/print\/wip-scanning\?id=/);
  assert.match(query, /\/api\/traceability\/document\?id=/);
  for (const detailQuery of [invoice, receipt, inspection, outbound]) {
    assert.match(detailQuery, /@DocumentId/);
  }
});

test("RM receipt has a dedicated print layout without pricing columns", async () => {
  const [api, query] = await Promise.all([
    read("iis/backend/app/main.py"),
    read("iis/backend/sql/print/rm-receipt.sql"),
  ]);
  assert.match(api, /def _receipt_print_html\(row: dict\)/);
  assert.match(api, /PHIẾU NHẬP KHO/);
  assert.match(api, /doc_code == "NK"/);
  assert.match(api, /Tên, nhãn hiệu quy cách phẩm chất vật tư/);
  assert.match(api, /Của khách hàng:/);
  assert.match(api, /reference_label = "Invoice" if is_material else "HĐGTGT"/);
  assert.match(api, /Theo chứng từ/);
  assert.match(api, /Thực nhập/);
  assert.match(api, /strftime\("%d\/%m\/%Y"\)/);
  const receiptTemplate = api.slice(api.indexOf("def _receipt_print_html"), api.indexOf("@app.get(\"/health\")"));
  assert.doesNotMatch(receiptTemplate, /Đơn giá|Thành tiền|Thuế GTGT|Tổng tiền thanh toán/);
  assert.match(query, /WH_ChiTietPhieuGiamDinh AS detail/);
  assert.match(query, /detail\.TenNPL AS ItemName/);
  assert.match(query, /detail\.MaNPL AS ItemCode/);
  assert.match(query, /CAST\(inspection\.NgayGiamDinh AS date\) AS DocDate/);
  assert.doesNotMatch(query, /Bravo_PNK/);
});

test("RM inspection reads QM inspection trees and their defect details", async () => {
  const query = await read("iis/backend/sql/print/rm-inspection.sql");
  assert.match(query, /QM_PhieuKiemVai AS inspectionRow/);
  assert.match(query, /QM_PhieuKiemVai_CayVai AS inspectionTree/);
  assert.match(query, /QM_PhieuKiemVai_Cay_ChiTiet AS defect/);
  assert.match(query, /defect\.CTId = inspectionTree\.CTId/);
  assert.match(query, /inspectionTree\.PKVId = inspectionRow\.PKVId/);
  assert.match(query, /inspectionRow\.PKVId\) = @DocumentId/);
  assert.doesNotMatch(query, /WH_PhieuGiamDinh|Bravo_PNK/);
});

test("RFID image metadata is queried once and reused by both image requests", async () => {
  const [api, config] = await Promise.all([
    read("iis/backend/app/main.py"),
    read("iis/backend/app/config.py"),
  ]);
  assert.match(api, /def _image_rows\(rfid: str, source:/);
  assert.match(api, /_image_metadata_cache/);
  assert.match(api, /rows = _image_rows\(value, source\)/);
  assert.equal((api.match(/query_rows\(settings, query, \{"RFID": rfid\}\)/g) || []).length, 1);
  assert.match(api, /_new_traceability_query\(\) if source == "new" else settings\.sqlquery/);
  assert.doesNotMatch(config, /sqlquery_image/);
  assert.match(config, /image_metadata_cache_seconds/);
});

test("both RFID modes stream tracking images independently from rendered data", async () => {
  const [env, script] = await Promise.all([
    read("iis/backend/.env.example"),
    read("iis/frontend/assets/app.js"),
  ]);
  assert.doesNotMatch(env, /^SQLQUERY_IMAGE=/m);
  assert.doesNotMatch(env, /^SQLQUERY_IMAGE_NEW=/m);
  assert.match(env, /SQLQUERY=.*Tracking_RFID_Master_Image.*URLFrontImage.*URLBackImage/);
  assert.match(env, /SQLQUERY_NEW=.*Tracking_RFID_Master_Image.*image\.RFID=mp\.RFID.*URLFrontImage.*URLBackImage/);
  assert.match(script, /source=\$\{source\}/);
  assert.match(script, /state\.traceMode === "rfid-new" \? "new" : "legacy"/);
  assert.match(script, /showData\(data\);[\s\S]*loadImages\(/);
});

test("timeline hides the content column and uses an icon-only document preview", async () => {
  const [html, script, styles] = await Promise.all([
    read("iis/frontend/index.html"),
    read("iis/frontend/assets/app.js"),
    read("iis/frontend/assets/styles.css"),
  ]);

  assert.doesNotMatch(html, /NỘI DUNG\s*\/\s*CONTENT/);
  assert.doesNotMatch(script, /<span>Xem chứng từ<\/span>/);
  assert.match(script, /class="preview-link document-preview"/);
  assert.match(script, /aria-label="Xem chứng từ"/);
  assert.match(styles, /\.preview-link/);
  assert.match(script, /<circle cx="16\.5" cy="16\.5" r="3\.5"><\/circle>/);
});

test("RFID timelines start collapsed after each lookup", async () => {
  const script = await read("iis/frontend/assets/app.js");
  assert.match(script, /const initiallyOpen = false/);
  assert.doesNotMatch(script, /firstOpenStep/);
  assert.match(script, /aria-expanded="\$\{initiallyOpen\}"/);
});

test("new RFID view keeps the cut table label and formats sewing date without time", async () => {
  const [html, script] = await Promise.all([
    read("iis/frontend/index.html"),
    read("iis/frontend/assets/app.js"),
  ]);
  assert.match(html, /Bàn cắt<small>Cut Table<\/small>/);
  assert.doesNotMatch(html, /Bàn may|Sewing Table/);
  assert.match(script, /state\.traceMode === "rfid-new" \? formatDate\(sewingDate\) : sewingDate/);
});

test("both RFID views use the document search preview icon", async () => {
  const script = await read("iis/frontend/assets/app.js");
  assert.match(script, /class="preview-link document-preview"/);
  assert.match(script, /<circle cx="16\.5" cy="16\.5" r="3\.5"><\/circle>/);
  assert.doesNotMatch(script, /M2\.5 12s3\.5-6 9\.5-6/);
});

test("new technical-document previews are proxied as inline PDF or images", async () => {
  const [query, api] = await Promise.all([
    read("docs/TRACEABILITY-NEW-QUERY.sql"),
    read("iis/backend/app/main.py"),
  ]);
  assert.match(query, /CONCAT\(N'\/api\/traceability\/document\?id=', document\.Id\) AS DetailLink/);
  assert.match(api, /@app\.get\("\/api\/traceability\/document"\)/);
  assert.match(api, /FROM dbo\.TEC_ThongTinTaiLieukyThuat/);
  assert.match(api, /WHERE Id = @DocumentId/);
  assert.match(api, /Content-Disposition": f"inline;/);
  assert.match(api, /f"http:\/\/{settings\.hostfile}\/PhieuDieTiet"/);
  assert.match(api, /if upstream\.status_code == 404 and not urlparse\(source\)\.scheme/);
  assert.match(api, /f"http:\/\/{settings\.hostfile}\/PhieuDieuTiet"/);
  assert.match(api, /source, fallback_base_url, settings\.hostfile/);
  assert.match(api, /settings\.hostfile/);
  assert.match(api, /base_url\.rstrip\('\/'\)/);
  assert.match(api, /part in \{"\.", "\.\."\} or ":" in part/);
  assert.match(api, /"\.pdf", "\.jpg", "\.jpeg", "\.png"/);
  assert.match(api, /_validate_internal_url\(url, allowed_host\)/);
});

test("Windows deploy preserves Vietnamese SQL literals as UTF-8", async () => {
  const source = await read("iis/deploy/windows/deploy-iis.ps1");
  assert.match(source, /Get-Content \$SourcePath -Encoding UTF8/);
  assert.match(source, /Get-Content \$TargetPath -Encoding UTF8/);
  assert.match(source, /Set-Content -Path \$TargetPath -Value \$targetLines -Encoding UTF8/);
});

test("Windows deploy uses the Traceability-Portal directories", async () => {
  const source = await read("iis/deploy/windows/deploy-iis.ps1");
  assert.match(source, /D:\\Apps\\Traceability-Portal/);
  assert.match(source, /C:\\inetpub\\wwwroot\\Traceability-Portal/);
  assert.doesNotMatch(source, /[CD]:\\Apps\\WebTruySuat/);
  assert.doesNotMatch(source, /wwwroot\\WebTruySuat/);
  assert.match(source, /\$SiteName = "Traceability-Portal"/);
  assert.match(source, /\$ServiceName = "TraceabilityPortalBackend"/);
  assert.match(source, /Set-Service -Name \$LegacyServiceName -StartupType Disabled/);
  assert.match(source, /stop site "\/site\.name:\$LegacySiteName"/);
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
