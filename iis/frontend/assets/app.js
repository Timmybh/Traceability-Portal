const FALLBACK_IMAGE = "/assets/jacket-line.png?v=20260829-1";

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
  imageTimer: null,
  imageTransitioning: false,
  imageTransitionId: 0,
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

function formatDate(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : (value || "—");
}

function detailRows(stepNumber, details, initiallyOpen) {
  return details.map((detail) => {
    const content = detail.DetailContent || "—";
    const link = safeLink(detail.DetailLink);
    return `
      <tr class="step-detail-row" data-parent-step="${stepNumber}"${initiallyOpen ? "" : " hidden"}>
        <td>
          <div class="detail-title" title="${escapeHtml(content)}">
            <span class="document-icon" aria-hidden="true"></span>
            <strong>${escapeHtml(content)}</strong>
          </div>
        </td>
        <td class="detail-date">${escapeHtml(formatDate(detail.DetailDate))}</td>
        <td><div class="detail-content" title="${escapeHtml(content)}">${escapeHtml(content)}</div></td>
        <td>${link ? `<a class="document-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer"><span>Xem chứng từ</span><span aria-hidden="true">↗</span></a>` : "—"}</td>
      </tr>`;
  }).join("");
}

function renderSteps(timeline = []) {
  const records = timelineByStep(timeline);
  const firstOpenStep = steps.find((step) => (records.get(step[0])?.Details || []).length)?.[0];
  byId("steps-body").innerHTML = steps.map((step, index) => {
    const record = records.get(step[0]);
    const details = Array.isArray(record?.Details) ? record.Details : [];
    const canExpand = details.length > 0;
    const initiallyOpen = canExpand && step[0] === firstOpenStep;
    const date = formatDate(record?.StepDate);
    return `
      <tr class="step-parent-row${initiallyOpen ? " is-open" : ""}" data-step="${step[0]}">
        <td>
          <button class="step-toggle" type="button" data-step="${step[0]}" aria-expanded="${initiallyOpen}"${canExpand ? "" : " disabled"}>
            <span class="chevron" aria-hidden="true">${canExpand ? "⌄" : "›"}</span>
            <span class="step-number" style="background:${colors[index % colors.length]}">${step[0]}</span>
            <span class="step-label"><b>${step[1]}</b><small>${step[2]}</small></span>
          </button>
        </td>
        <td>${record ? `<span class="completed">${escapeHtml(date)}</span>` : `<span class="pending">Chờ dữ liệu</span>`}</td>
        <td>—</td>
        <td>—</td>
      </tr>
      ${detailRows(step[0], details, initiallyOpen)}`;
  }).join("");

  document.querySelectorAll(".step-toggle:not(:disabled)").forEach((button) => button.addEventListener("click", () => {
    const stepNumber = button.dataset.step;
    const expanded = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", String(expanded));
    button.closest(".step-parent-row").classList.toggle("is-open", expanded);
    document.querySelectorAll(`.step-detail-row[data-parent-step="${stepNumber}"]`).forEach((row) => {
      row.hidden = !expanded;
    });
  }));

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
  record.classList.toggle("is-running", message.startsWith("Đang"));
  record.hidden = false;
}

function focusScannerInput() {
  window.requestAnimationFrame(() => {
    const input = byId("rfid-input");
    input.focus({ preventScroll: true });
  });
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

function clearCurrentData() {
  [
    "value-rfid", "value-customer", "value-po", "value-product-code", "value-item",
    "value-size", "value-art", "value-color", "value-season", "value-factory",
    "value-line", "value-production-order", "value-cut-table", "value-lot",
    "value-sewing-date",
  ].forEach((id) => { byId(id).textContent = "—"; });
  renderSteps([]);
  const image = byId("product-image");
  image.src = FALLBACK_IMAGE;
  image.classList.remove("loading", "run-out-left", "run-out-right", "run-in-left", "run-in-right");
  image.closest(".image-stage").style.removeProperty("--image-aspect");
  byId("image-loading").hidden = true;
  setNotice("");
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

function stopImageRotation() {
  if (state.imageTimer) window.clearInterval(state.imageTimer);
  state.imageTimer = null;
}

function startImageRotation() {
  stopImageRotation();
  if (!state.imageAvailability.front || !state.imageAvailability.back) return;
  state.imageTimer = window.setInterval(() => {
    transitionImage(state.side === "front" ? "back" : "front", 1, false);
  }, 3000);
}

function cancelImageTransition() {
  state.imageTransitionId += 1;
  state.imageTransitioning = false;
  byId("product-image").classList.remove("run-out-left", "run-out-right", "run-in-left", "run-in-right");
}

function transitionImage(nextSide, direction = 1, restartTimer = true) {
  if (nextSide === state.side || !state.imageAvailability[nextSide] || state.imageTransitioning) {
    if (restartTimer) startImageRotation();
    return;
  }

  if (restartTimer) stopImageRotation();
  state.imageTransitioning = true;
  const transitionId = ++state.imageTransitionId;
  const image = byId("product-image");
  const outClass = direction > 0 ? "run-out-left" : "run-out-right";
  const inClass = direction > 0 ? "run-in-right" : "run-in-left";
  image.classList.add(outClass);

  window.setTimeout(() => {
    if (transitionId !== state.imageTransitionId) return;
    state.side = nextSide;
    image.classList.remove(outClass);
    renderImage();
    image.classList.add(inClass);
    window.setTimeout(() => {
      if (transitionId !== state.imageTransitionId) return;
      image.classList.remove(inClass);
      state.imageTransitioning = false;
      if (restartTimer) startImageRotation();
    }, 380);
  }, 260);
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
  startImageRotation();
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
  stopImageRotation();
  cancelImageTransition();
  clearCurrentData();
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
  } finally {
    if (searchId === state.searchId) focusScannerInput();
  }
}

byId("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = byId("rfid-input");
  const value = input.value.trim();
  if (!value) return;
  input.value = "";
  focusScannerInput();
  search(value, true);
});
byId("rfid-input").addEventListener("keydown", (event) => {
  if (event.key !== "Tab" || !event.currentTarget.value.trim()) return;
  event.preventDefault();
  byId("search-form").requestSubmit();
});
document.querySelectorAll(".image-tab").forEach((tab) => tab.addEventListener("click", () => {
  transitionImage(tab.dataset.side, tab.dataset.side === "front" ? -1 : 1);
}));
document.querySelectorAll(".view-switch button").forEach((tab) => tab.addEventListener("click", () => {
  const selectedView = tab.dataset.view;
  document.querySelectorAll(".view-switch button").forEach((button) => {
    const active = button === tab;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".process-view").forEach((view) => { view.hidden = view.id !== `${selectedView}-view`; });
}));
byId("previous-image").addEventListener("click", () => transitionImage(state.side === "front" ? "back" : "front", -1));
byId("next-image").addEventListener("click", () => transitionImage(state.side === "front" ? "back" : "front", 1));
byId("product-image").addEventListener("load", () => {
  const image = byId("product-image");
  byId("image-loading").hidden = true;
  image.classList.remove("loading");
  if (image.naturalWidth && image.naturalHeight) {
    image.closest(".image-stage").style.setProperty("--image-aspect", `${image.naturalWidth} / ${image.naturalHeight}`);
  }
});
byId("product-image").addEventListener("error", () => { byId("product-image").src = FALLBACK_IMAGE; byId("image-loading").textContent = "Không tải được ảnh"; byId("product-image").classList.remove("loading"); });

renderSteps();
const initialUrl = new URL(window.location.href);
if (initialUrl.searchParams.has("rfid")) {
  initialUrl.searchParams.delete("rfid");
  history.replaceState({}, "", `${initialUrl.pathname}${initialUrl.search}${initialUrl.hash}`);
}
byId("rfid-input").value = "";
focusScannerInput();
