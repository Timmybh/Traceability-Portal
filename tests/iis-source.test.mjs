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
