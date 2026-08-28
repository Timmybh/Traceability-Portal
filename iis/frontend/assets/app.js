const FALLBACK_IMAGE = "/assets/jacket-line.png";

const steps = [
  ["01", "Phát triển sản phẩm", "Product Development", ""],
  ["02", "Số invoice", "Invoice Number", ""],
  ["03", "Nhập kho NPL", "RM Inbound", ""],
  ["04", "Kiểm NPL", "RM Inspection", ""],
  ["05", "Xuất kho NPL", "RM Outbound", ""],
  ["06", "Nhận NPL từ kho", "Receive Materials", ""],
  ["07", "Xả vải", "Fabric Relaxing", ""],
  ["08", "Trải vải", "Fabric Spreading", ""],
  ["09", "Cắt vải", "Fabric Cutting", ""],
  ["10", "Kiểm BTP", "WIP Inspection", ""],
  ["11", "Nhập kho BTP", "WIP Inbound", ""],
  ["12", "Đặt BTP", "WIP Issuing", ""],
  ["13", "Xuất BTP", "WIP Outbound", ""],
  ["15", "Quét nhận BTP", "WIP Scanning", ""],
  ["16", "Kiểm Inline", "Inline Inspection", ""],
  ["17", "Biên bản kiểm sản phẩm đầu chuyền", "Start-of-Line Check", ""],
  ["18", "Kết quả kiểm sản phẩm cuối chuyền", "End-of-Line Check", ""],
  ["19", "Kiểm Enline", "Enline Inspection", ""],
  ["20", "Đóng gói", "Packing", ""],
  ["21", "Nhập Kho Thành phẩm", "FG Inbound", ""],
  ["22", "Kiểm final", "Final Inspection", ""],
  ["23", "Xuất kho thành phẩm", "FG Outbound", ""],
];

const colors = ["#4f7df3", "#e9be28", "#45ae7c", "#e59b28", "#ed7829", "#d93e83", "#8e45e8", "#596ee8", "#497fe0", "#2b9bb5", "#31a681", "#35a15a"];
const state = {
  rfid: "",
  trackedRfid: null,
  side: "front",
  imageAvailability: { front: false, back: false },
  searchId: 0,
};

const byId = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function safeLink(value) {
  if (!value) return "";
  try {
    const url = new URL(String(value), window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (_) {
    return "";
  }
}

function timelineByStep(timeline) {
  const records = Array.isArray(timeline) ? timeline : [];
  const grouped = new Map();
  records.forEach((record) => {
    const stepNumber = Number(record.StepNo);
    if (!Number.isFinite(stepNumber)) return;
    const key = String(stepNumber).padStart(2, "0");
    const current = grouped.get(key);
    if (!current) {
      grouped.set(key, { ...record, Details: Array.isArray(record.Details) ? record.Details : [] });
      return;
    }
    current.Details.push(...(Array.isArray(record.Details) ? record.Details : []));
    current.StepDate ||= record.StepDate;
    current.StepContent ||= record.StepContent;
    current.StepLink ||= record.StepLink;
  });
  return grouped;
}

function detailMarkup(record) {
  const details = Array.isArray(record?.Details) ? record.Details : [];
  if (!details.length) return escapeHtml(record?.StepContent || "—");
  return `
    ${record?.StepContent ? `<div class="step-content">${escapeHtml(record.StepContent)}</div>` : ""}
    <details class="step-details">
      <summary>${details.length} chi tiết</summary>
      <div class="step-detail-list">${details.map((detail) => {
        const link = safeLink(detail.DetailLink);
        return `<div class="step-detail-item"><b>${escapeHtml(detail.DetailDate || "—")}</b><span>${escapeHtml(detail.DetailContent || "—")}</span>${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Mở tài liệu</a>` : ""}</div>`;
      }).join("")}</div>
    </details>`;
}

function renderSteps(timeline = []) {
  const records = timelineByStep(timeline);
  byId("steps-body").innerHTML = steps.map((step, index) => {
    const record = records.get(step[0]);
    const details = Array.isArray(record?.Details) ? record.Details : [];
    const latest = details.at(-1);
    const date = latest?.DetailDate || record?.StepDate || "—";
    const link = safeLink(record?.StepLink || latest?.DetailLink);
    return `
    <tr>
      <td><div class="step-name"><span class="chevron">›</span><span class="step-number" style="background:${colors[index % colors.length]}">${step[0]}</span><span><b>${step[1]}</b><small>${step[2]}</small></span></div></td>
      <td>${record ? `<span class="completed">${escapeHtml(date)}</span>` : `<span class="pending">Chờ dữ liệu</span>`}</td>
      <td>${record ? detailMarkup(record) : "—"}</td>
      <td>${link ? `<a class="step-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Mở liên kết</a>` : "—"}</td>
    </tr>`;
  }).join("");

  byId("steps-diagram").innerHTML = steps.map((step, index) => {
    const record = records.get(step[0]);
    const details = Array.isArray(record?.Details) ? record.Details : [];
    const latest = details.at(-1);
    const summary = latest?.DetailContent || record?.StepContent || "Chưa có dữ liệu chi tiết cho công đoạn này.";
    return `
    <article class="diagram-step" style="--step-color:${colors[index % colors.length]}">
      <span class="diagram-line" aria-hidden="true"></span>
      <span class="diagram-number">${step[0]}</span>
      <button class="diagram-card" type="button" aria-expanded="false">
        <span class="diagram-heading"><span><b>${step[1]}</b><small>${step[2]}</small></span><span class="${record ? "completed" : "pending"}">${record ? "Đã có dữ liệu" : "Chờ dữ liệu"}</span></span>
        <span class="diagram-detail">${escapeHtml(summary)}${details.length ? ` (${details.length} chi tiết)` : ""}</span>
      </button>
    </article>`;
  }).join("");

  document.querySelectorAll(".diagram-card").forEach((card) => card.addEventListener("click", () => {
    const step = card.closest(".diagram-step");
    const open = step.classList.toggle("open");
    card.setAttribute("aria-expanded", String(open));
  }));
}

function field(data, ...names) {
  for (const name of names) {
    const key = Object.keys(data).find((candidate) => candidate.toLowerCase() === name.toLowerCase());
    if (key && data[key] != null) return String(data[key]);
  }
  return "N/A";
}

function setNotice(message, type = "") {
  const notice = byId("notice");
  notice.textContent = message;
  notice.className = `notice ${type}`;
}

function currentTime() {
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date());
}

function setQueryStatus(message, rfid = state.rfid) {
  if (!rfid || state.trackedRfid !== rfid) return;
  const record = byId("search-record");
  record.textContent = `[${currentTime()}] - ${message} - QR/RFID : ${rfid}`;
  record.hidden = false;
}

function showData(data) {
  byId("value-rfid").textContent = field(data, "RFID");
  byId("value-customer").textContent = field(data, "TenNgan");
  byId("value-po").textContent = field(data, "PO");
  byId("value-product-code").textContent = field(data, "ProductCode");
  byId("value-item").textContent = field(data, "ItemId", "Item", "ItemCode");
  byId("value-size").textContent = field(data, "Size");
  byId("value-art").textContent = field(data, "Art", "ArtCode");
  byId("value-color").textContent = field(data, "Color", "MauSac");
  byId("value-season").textContent = field(data, "Season", "Mua");
  byId("value-factory").textContent = field(data, "XiNghiep", "Factory");
  byId("value-line").textContent = field(data, "ChuyenMay", "Chuyen", "Line");
  byId("value-production-order").textContent = field(data, "LenhSanXuat", "ProductionOrder");
  byId("value-cut-table").textContent = field(data, "BanCat", "CutTable");
  byId("value-lot").textContent = field(data, "Lot");
  byId("value-sewing-date").textContent = field(data, "NgaySanXuat", "NgayMay", "SewingDate");
  renderSteps(data.Timeline);
}

async function getJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let message = "Không thể tải dữ liệu";
    try { message = (await response.json()).detail || message; } catch (_) { /* giữ thông báo mặc định */ }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function imageUrl(side = state.side, rfid = state.rfid) {
  return `/api/traceability/image?rfid=${encodeURIComponent(rfid)}&side=${side}`;
}

function renderImage() {
  document.querySelectorAll(".image-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.side === state.side));
  const image = byId("product-image");
  const loading = byId("image-loading");
  loading.hidden = false;
  image.classList.add("loading");
  if (!state.imageAvailability[state.side]) {
    image.src = FALLBACK_IMAGE;
    loading.textContent = "Không có ảnh";
    image.classList.remove("loading");
    return;
  }
  loading.textContent = "Đang tải ảnh…";
  image.src = imageUrl(state.side);
}

function preloadImage(url) {
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve(true);
    image.onerror = () => resolve(false);
    image.src = url;
  });
}

async function loadImages(rfid, searchId) {
  setQueryStatus("Đang kiểm tra 2 ảnh ...", rfid);
  let available;
  try {
    available = await getJson(`/api/traceability/images?rfid=${encodeURIComponent(rfid)}`);
  } catch (_) {
    available = { front: false, back: false };
  }

  const sides = ["front", "back"];
  const loaded = await Promise.all(sides.map((side) => (
    available[side] ? preloadImage(imageUrl(side, rfid)) : Promise.resolve(false)
  )));
  if (searchId !== state.searchId || rfid !== state.rfid) return;

  state.imageAvailability = { front: loaded[0], back: loaded[1] };
  renderImage();
  const loadedCount = loaded.filter(Boolean).length;
  setQueryStatus(loadedCount ? `Tải ${loadedCount}/2 ảnh xong` : "Không tìm thấy ảnh", rfid);
}

async function search(rfid, trackStatus = false) {
  state.rfid = rfid.trim();
  if (!state.rfid) return;
  const searchId = ++state.searchId;
  state.trackedRfid = trackStatus ? state.rfid : null;
  state.side = "front";
  state.imageAvailability = { front: false, back: false };
  setQueryStatus("Đang tra cứu ...");
  setNotice("Đang tải thông tin…", "loading");
  try {
    const data = await getJson(`/api/traceability?rfid=${encodeURIComponent(state.rfid)}`);
    if (searchId !== state.searchId) return;
    if (!data || Object.keys(data).length === 0) {
      setQueryStatus("Không tìm thấy dữ liệu");
      setNotice("Không tìm thấy dữ liệu cho RFID này", "error");
      return;
    }
    showData(data);
    setQueryStatus("Tải dữ liệu xong");
    setNotice("Đã tải dữ liệu RFID", "success");
    loadImages(state.rfid, searchId);
  } catch (error) {
    if (searchId !== state.searchId) return;
    if (error.status === 404 || /không tìm thấy/i.test(error.message)) setQueryStatus("Không tìm thấy dữ liệu");
    setNotice(error.message, "error");
  }
}

byId("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = byId("rfid-input");
  const value = input.value.trim();
  if (!value) return;
  input.value = "";
  search(value, true);
});
document.querySelectorAll(".image-tab").forEach((tab) => tab.addEventListener("click", () => { state.side = tab.dataset.side; renderImage(); }));
document.querySelectorAll(".view-switch button").forEach((tab) => tab.addEventListener("click", () => {
  const selectedView = tab.dataset.view;
  document.querySelectorAll(".view-switch button").forEach((button) => {
    const active = button === tab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".process-view").forEach((view) => { view.hidden = view.id !== `${selectedView}-view`; });
}));
byId("previous-image").addEventListener("click", () => { state.side = state.side === "front" ? "back" : "front"; renderImage(); });
byId("next-image").addEventListener("click", () => { state.side = state.side === "front" ? "back" : "front"; renderImage(); });
byId("product-image").addEventListener("load", () => { const image = byId("product-image"); byId("image-loading").hidden = true; image.classList.remove("loading"); });
byId("product-image").addEventListener("error", () => { byId("product-image").src = FALLBACK_IMAGE; byId("image-loading").textContent = "Không tải được ảnh"; byId("product-image").classList.remove("loading"); });

renderSteps();
const initialUrl = new URL(window.location.href);
if (initialUrl.searchParams.has("rfid")) {
  initialUrl.searchParams.delete("rfid");
  history.replaceState({}, "", `${initialUrl.pathname}${initialUrl.search}${initialUrl.hash}`);
}
byId("rfid-input").value = "";
