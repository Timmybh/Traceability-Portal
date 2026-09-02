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
  traceMode: "rfid",
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

function previewLink(link) {
  if (!link) return "—";
  return `<a class="preview-link document-preview" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer" aria-label="Xem chứng từ" title="Xem chứng từ">
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M13 2H5a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h8"></path>
      <path d="M13 2v6h6"></path>
      <path d="m13 2 6 6v3"></path>
      <circle cx="16.5" cy="16.5" r="3.5"></circle>
      <path d="m19 19 3 3"></path>
    </svg>
  </a>`;
}

const lookupState = { po: [], lot: [] };

const lookupDemo = {
  po: { customer: "M&S", value: "4524453763", parents: [
    { ProductCode: "375707", Season: "AW26", CustomerName: "Marks & Spencer", Items: [
      { STT: 1, ItemName: "Nguyên liệu", Quantity: 12840, YardQuantity: 18652.5, DownloadKey: "materials" },
      { STT: 2, ItemName: "Phụ liệu", Quantity: 36800, YardQuantity: null, DownloadKey: "accessories" },
      { STT: 3, ItemName: "Tem RFID", Quantity: 6120, YardQuantity: null, DownloadKey: "rfid-tags" },
      { STT: 4, ItemName: "Tem SHU", Quantity: 6120, YardQuantity: null, DownloadKey: "shu-tags" },
      { STT: 5, ItemName: "Hồ sơ kỹ thuật", Quantity: 8, YardQuantity: null, DownloadKey: "technical-files" },
      { STT: 6, ItemName: "Hồ sơ thông quan", Quantity: 5, YardQuantity: null, DownloadKey: "customs-files" },
      { STT: 7, ItemName: "Hồ sơ chất lượng", Quantity: 12, YardQuantity: null, DownloadKey: "quality-files" },
    ] },
    { ProductCode: "375742", Season: "AW26", CustomerName: "Marks & Spencer", Items: [
      { STT: 1, ItemName: "Nguyên liệu", Quantity: 8240, YardQuantity: 11906.8, DownloadKey: "materials" },
      { STT: 2, ItemName: "Phụ liệu", Quantity: 21500, YardQuantity: null, DownloadKey: "accessories" },
      { STT: 3, ItemName: "Tem RFID", Quantity: 4050, YardQuantity: null, DownloadKey: "rfid-tags" },
      { STT: 4, ItemName: "Tem SHU", Quantity: 4050, YardQuantity: null, DownloadKey: "shu-tags" },
      { STT: 5, ItemName: "Hồ sơ kỹ thuật", Quantity: 6, YardQuantity: null, DownloadKey: "technical-files" },
      { STT: 6, ItemName: "Hồ sơ thông quan", Quantity: 4, YardQuantity: null, DownloadKey: "customs-files" },
      { STT: 7, ItemName: "Hồ sơ chất lượng", Quantity: 9, YardQuantity: null, DownloadKey: "quality-files" },
    ] },
  ] },
  lot: { customer: "M&S", value: "DE26030463", parents: [
    { Lot: "DE26030463", Items: [
      { STT: 1, ItemName: "Phiếu kiểm định", Quantity: 3, YardQuantity: 4258.4, DownloadKey: "inspection-receipts" },
      { STT: 2, ItemName: "Phiếu nhập hàng", Quantity: 2, YardQuantity: 4258.4, DownloadKey: "goods-receipts" },
      { STT: 3, ItemName: "Sản phẩm", Quantity: 2, YardQuantity: null, DownloadKey: "products" },
      { STT: 4, ItemName: "PO", Quantity: 2, YardQuantity: null, DownloadKey: "purchase-orders" },
      { STT: 5, ItemName: "Hồ sơ chất lượng", Quantity: 9, YardQuantity: null, DownloadKey: "quality-files" },
    ] },
    { Lot: "E26030774", Items: [
      { STT: 1, ItemName: "Phiếu kiểm định", Quantity: 1, YardQuantity: 1680, DownloadKey: "inspection-receipts" },
      { STT: 2, ItemName: "Phiếu nhập hàng", Quantity: 1, YardQuantity: 1680, DownloadKey: "goods-receipts" },
      { STT: 3, ItemName: "Sản phẩm", Quantity: 1, YardQuantity: null, DownloadKey: "products" },
      { STT: 4, ItemName: "PO", Quantity: 1, YardQuantity: null, DownloadKey: "purchase-orders" },
      { STT: 5, ItemName: "Hồ sơ chất lượng", Quantity: 4, YardQuantity: null, DownloadKey: "quality-files" },
    ] },
  ] },
};

function showLookupDemo(type) {
  const demo = lookupDemo[type];
  const form = byId(`${type}-search-form`);
  form.elements.customer_code.value = demo.customer;
  form.elements[type].value = demo.value;
  renderLookupResults(type, demo.parents, { customer: demo.customer, value: demo.value });
  const status = byId(`${type}-status`);
  status.innerHTML = `<span class="demo-badge">Dữ liệu minh họa</span> Số liệu dùng để trình diễn giao diện, chưa phải dữ liệu hệ thống.`;
  status.className = "lookup-status demo";
}

function activateTraceTab(name) {
  byId("trace-mode-select").value = name;
  const isRfid = name === "rfid" || name === "rfid-new";
  document.querySelectorAll(".trace-panel").forEach((panel) => { panel.hidden = panel.id !== (isRfid ? "trace-panel-rfid" : `trace-panel-${name}`); });
  byId("search-form").hidden = !isRfid;
  if (!isRfid) byId("search-record").hidden = true;
  if (isRfid) {
    state.traceMode = name;
    state.searchId += 1;
    clearCurrentData();
    setNotice("", "");
    focusScannerInput();
  }
  else if (!lookupState[name].length) showLookupDemo(name);
}

function quantity(value) {
  if (value == null || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(number) : escapeHtml(value);
}

function lookupItems(parent) {
  return Array.isArray(parent?.Items) ? parent.Items : [];
}

function renderLookupResults(type, parents, context) {
  const target = byId(`${type}-results`);
  lookupState[type] = parents;
  if (!parents.length) {
    target.innerHTML = `<div class="lookup-empty">Không tìm thấy dữ liệu phù hợp</div>`;
    return;
  }

  target.innerHTML = parents.map((parent, parentIndex) => {
    const items = lookupItems(parent);
    const isPo = type === "po";
    const primary = isPo ? (parent.ProductCode || "—") : (parent.Lot || context.value || "—");
    const secondary = isPo ? (parent.Season || "—") : context.customer;
    const customer = isPo ? (parent.CustomerName || context.customer) : `Khách hàng: ${context.customer}`;
    const itemHeader = isPo ? "Tên hạng mục" : "Hạng mục";
    return `
      <article class="lookup-parent" data-lookup-parent="${type}-${parentIndex}">
        <button class="lookup-parent-toggle" type="button" data-lookup-toggle="${type}-${parentIndex}" aria-expanded="false">
          <span class="lookup-chevron" aria-hidden="true">›</span>
          <strong>${escapeHtml(isPo ? `Mã hàng: ${primary}` : `LOT: ${primary}`)}</strong>
          <span>${escapeHtml(secondary)}</span>
          <span>${escapeHtml(customer)}</span>
          <small>${items.length} hạng mục</small>
        </button>
        <div class="lookup-children" hidden>
          <table class="lookup-table">
            <thead><tr><th>STT</th><th>${itemHeader}</th><th>${isPo ? "Số lượng" : "SL"}</th><th>SL Yard</th><th>Tải danh sách</th></tr></thead>
            <tbody>${items.map((item, itemIndex) => `
              <tr>
                <td>${escapeHtml(item.STT ?? itemIndex + 1)}</td>
                <td><strong>${escapeHtml(item.ItemName || "—")}</strong></td>
                <td>${quantity(item.Quantity)}</td>
                <td>${quantity(item.YardQuantity)}</td>
                <td><button class="download-list" type="button" data-download-type="${type}" data-parent-index="${parentIndex}" data-item-index="${itemIndex}">Tải danh sách</button></td>
              </tr>`).join("")}</tbody>
          </table>
        </div>
      </article>`;
  }).join("");
}

function downloadLookupItem(type, parentIndex, itemIndex) {
  const parent = lookupState[type][parentIndex];
  const item = lookupItems(parent)[itemIndex];
  if (!parent || !item) return;
  const rows = [
    ["STT", "Hạng mục", "Số lượng", "SL Yard"],
    [item.STT ?? itemIndex + 1, item.ItemName || "", item.Quantity ?? "", item.YardQuantity ?? ""],
  ];
  const csv = `\uFEFF${rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\r\n")}`;
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${type}-${item.DownloadKey || itemIndex + 1}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function searchLookup(type, form) {
  const formData = new FormData(form);
  const customer = String(formData.get("customer_code") || "").trim();
  const valueName = type === "po" ? "po" : "lot";
  const value = String(formData.get(valueName) || "").trim();
  const status = byId(`${type}-status`);
  if (!customer || !value) {
    status.textContent = "Khách hàng và giá trị truy suất đều bắt buộc.";
    status.className = "lookup-status error";
    return;
  }
  status.textContent = "Đang tra cứu dữ liệu chính xác…";
  status.className = "lookup-status";
  byId(`${type}-results`).innerHTML = `<div class="lookup-empty">Đang tải dữ liệu…</div>`;
  try {
    const data = await getJson(`/api/traceability/${type}?customer_code=${encodeURIComponent(customer)}&${valueName}=${encodeURIComponent(value)}`);
    const parents = type === "po" ? (data.Products || []) : (data.Lots || []);
    renderLookupResults(type, parents, { customer, value });
    status.textContent = `Đã tải ${parents.length} kết quả cho ${value}.`;
    status.className = "lookup-status success";
  } catch (error) {
    renderLookupResults(type, [], { customer, value });
    status.textContent = error.message;
    status.className = "lookup-status error";
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
        <td>${previewLink(link)}</td>
      </tr>`;
  }).join("");
}

const inspectionDepartments = [
  { key: "materials", label: "BỘ PHẬN: NGUYÊN LIỆU", icon: "🧵" },
  { key: "accessories", label: "BỘ PHẬN: PHỤ LIỆU", icon: "📦" },
];

function normalizedText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

function inspectionDepartment(detail) {
  const department = normalizedText(detail.Department);
  if (department.includes("phu lieu")) return "accessories";
  if (department.includes("nguyen lieu")) return "materials";

  // Legacy records may omit Department; content is used only as a grouping fallback.
  const content = normalizedText(detail.DetailContent);
  return content.includes("phu lieu") ? "accessories" : "materials";
}

function inspectionDepartmentRows(stepNumber, details, initiallyOpen) {
  const grouped = new Map(inspectionDepartments.map((department) => [department.key, []]));
  details.forEach((detail) => grouped.get(inspectionDepartment(detail)).push(detail));

  return inspectionDepartments.map((department) => {
    const departmentDetails = grouped.get(department.key);
    const canExpand = departmentDetails.length > 0;
    return `
      <tr class="department-row" data-parent-step="${stepNumber}" data-department="${department.key}"${initiallyOpen ? "" : " hidden"}>
        <td colspan="2">
          <button class="department-toggle" type="button" data-step="${stepNumber}" data-department="${department.key}" aria-expanded="false"${canExpand ? "" : " disabled"}>
            <span class="department-chevron" aria-hidden="true">›</span>
            <span class="department-icon" aria-hidden="true">${department.icon}</span>
            <strong>${department.label}</strong>
          </button>
        </td>
        <td><span class="department-count">${departmentDetails.length} bản ghi</span></td>
      </tr>
      ${departmentDetails.map((detail) => {
        const content = detail.DetailContent || "—";
        const link = safeLink(detail.DetailLink);
        return `
          <tr class="step-detail-row department-detail-row" data-parent-step="${stepNumber}" data-department="${department.key}" hidden>
            <td>
              <div class="detail-title" title="${escapeHtml(content)}">
                <span class="document-icon" aria-hidden="true"></span>
                <strong>${escapeHtml(content)}</strong>
              </div>
            </td>
            <td class="detail-date">${escapeHtml(formatDate(detail.DetailDate))}</td>
            <td>${previewLink(link)}</td>
          </tr>`;
      }).join("")}`;
  }).join("");
}

function renderSteps(timeline = []) {
  const records = timelineByStep(timeline);
  byId("steps-body").innerHTML = steps.map((step, index) => {
    const record = records.get(step[0]);
    const details = Array.isArray(record?.Details) ? record.Details : [];
    const canExpand = details.length > 0;
    const initiallyOpen = false;
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
        <td>${previewLink(safeLink(record?.StepLink))}</td>
      </tr>
      ${["03", "04", "05"].includes(step[0])
        ? inspectionDepartmentRows(step[0], details, initiallyOpen)
        : detailRows(step[0], details, initiallyOpen)}`;
  }).join("");

  document.querySelectorAll(".step-toggle:not(:disabled)").forEach((button) => button.addEventListener("click", () => {
    const stepNumber = button.dataset.step;
    const expanded = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", String(expanded));
    button.closest(".step-parent-row").classList.toggle("is-open", expanded);
    document.querySelectorAll(`[data-parent-step="${stepNumber}"]`).forEach((row) => {
      row.hidden = !expanded;
    });
    if (expanded && ["03", "04", "05"].includes(stepNumber)) {
      document.querySelectorAll(`.department-detail-row[data-parent-step="${stepNumber}"]`).forEach((row) => {
        const groupButton = document.querySelector(`.department-toggle[data-step="${stepNumber}"][data-department="${row.dataset.department}"]`);
        row.hidden = groupButton?.getAttribute("aria-expanded") !== "true";
      });
    }
  }));

  document.querySelectorAll(".department-toggle:not(:disabled)").forEach((button) => button.addEventListener("click", () => {
    const expanded = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", String(expanded));
    button.closest(".department-row").classList.toggle("is-open", expanded);
    document.querySelectorAll(`.department-detail-row[data-parent-step="${button.dataset.step}"][data-department="${button.dataset.department}"]`).forEach((row) => {
      row.hidden = !expanded;
    });
  }));

  byId("steps-diagram").innerHTML = steps.map((step, index) => {
    const record = records.get(step[0]);
    const details = Array.isArray(record?.Details) ? record.Details : [];
    const latest = details.at(-1);
    const summary = latest?.DetailContent || record?.StepContent || "";
    return `
    <article class="diagram-step" style="--step-color:${colors[index % colors.length]}">
      <span class="diagram-line" aria-hidden="true"></span>
      <span class="diagram-number">${step[0]}</span>
      <button class="diagram-card" type="button" aria-expanded="false"${details.length ? "" : " disabled"}>
        <span class="diagram-heading"><span><b>${step[1]}</b><small>${step[2]}</small></span><span class="${record ? "completed" : "pending"}">${record ? "Đã có dữ liệu" : "Chờ dữ liệu"}</span></span>
        ${summary ? `<span class="diagram-detail">${escapeHtml(summary)}${details.length ? ` (${details.length} chi tiết)` : ""}</span>` : ""}
      </button>
    </article>`;
  }).join("");

  document.querySelectorAll(".diagram-card:not(:disabled)").forEach((card) => card.addEventListener("click", () => {
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

function setQueryStatus(message, rfid = state.rfid, phase = "loading") {
  if (!rfid || state.trackedRfid !== rfid) return;
  const record = byId("search-record");
  record.textContent = `[${currentTime()}] - ${message} - QR/RFID : ${rfid}`;
  record.classList.toggle("has-data", phase === "data" || phase === "complete");
  record.classList.toggle("is-complete", phase === "complete");
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
  byId("value-main-lot").textContent = field(data, "LotVaiChinh", "Lot");
  byId("value-contrast-lot").textContent = field(data, "LotVaiPhoi");
  const sewingDate = field(data, "NgaySanXuat", "NgayMay", "SewingDate");
  byId("value-sewing-date").textContent = state.traceMode === "rfid-new" ? formatDate(sewingDate) : sewingDate;
  renderSteps(data.Timeline);
}

function clearCurrentData() {
  [
    "value-rfid", "value-customer", "value-po", "value-product-code", "value-item",
    "value-size", "value-art", "value-color", "value-season", "value-factory",
    "value-line", "value-production-order", "value-cut-table", "value-main-lot",
    "value-contrast-lot",
    "value-sewing-date",
  ].forEach((id) => { byId(id).textContent = "—"; });
  renderSteps([]);
  const image = byId("product-image");
  image.removeAttribute("src");
  image.hidden = true;
  image.classList.remove("loading", "run-out-left", "run-out-right", "run-in-left", "run-in-right");
  image.closest(".image-stage").style.removeProperty("--image-aspect");
  byId("image-loading").hidden = true;
  byId("image-empty").hidden = false;
  byId("image-empty").querySelector("strong").textContent = "Chưa có ảnh sản phẩm";
  byId("image-tabs").hidden = true;
  byId("previous-image").hidden = true;
  byId("next-image").hidden = true;
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
  if (!state.imageAvailability[state.side]) {
    image.removeAttribute("src");
    image.hidden = true;
    loading.hidden = true;
    byId("image-empty").hidden = false;
    byId("image-empty").querySelector("strong").textContent = "Không tìm thấy ảnh sản phẩm";
    byId("image-tabs").hidden = true;
    byId("previous-image").hidden = true;
    byId("next-image").hidden = true;
    return;
  }
  const canRotate = state.imageAvailability.front && state.imageAvailability.back;
  byId("image-empty").hidden = true;
  byId("image-tabs").hidden = false;
  byId("previous-image").hidden = !canRotate;
  byId("next-image").hidden = !canRotate;
  document.querySelectorAll(".image-tab").forEach((tab) => { tab.disabled = !state.imageAvailability[tab.dataset.side]; });
  image.hidden = false;
  loading.hidden = false;
  image.classList.add("loading");
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

async function loadImages(rfid, searchId, dataDurationMs) {
  const imageStarted = performance.now();
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
  if (!state.imageAvailability.front && state.imageAvailability.back) state.side = "back";
  renderImage();
  startImageRotation();
  const loadedCount = loaded.filter(Boolean).length;
  const imageSeconds = ((performance.now() - imageStarted) / 1000).toFixed(1);
  const dataSeconds = (dataDurationMs / 1000).toFixed(1);
  setQueryStatus(
    loadedCount
      ? `Dữ liệu ${dataSeconds}s; ảnh ${loadedCount}/2 tải nền ${imageSeconds}s`
      : `Dữ liệu ${dataSeconds}s; không tìm thấy ảnh (${imageSeconds}s)`,
    rfid,
    "complete",
  );
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
  const dataStarted = performance.now();
  try {
    const endpoint = state.traceMode === "rfid-new" ? "/api/traceability/new" : "/api/traceability";
    const data = await getJson(`${endpoint}?rfid=${encodeURIComponent(state.rfid)}`);
    if (searchId !== state.searchId) return;
    if (!data || Object.keys(data).length === 0) {
      setQueryStatus("Không tìm thấy dữ liệu", state.rfid, "complete");
      setNotice("Không tìm thấy dữ liệu cho RFID này", "error");
      return;
    }
    showData(data);
    const dataDurationMs = performance.now() - dataStarted;
    setQueryStatus(`Tải dữ liệu xong (${(dataDurationMs / 1000).toFixed(1)}s)`, state.rfid, "data");
    setNotice("Đã tải dữ liệu RFID", "success");
    loadImages(state.rfid, searchId, dataDurationMs);
  } catch (error) {
    if (searchId !== state.searchId) return;
    if (error.status === 404 || /không tìm thấy/i.test(error.message)) setQueryStatus("Không tìm thấy dữ liệu", state.rfid, "complete");
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
byId("trace-mode-select").addEventListener("change", (event) => activateTraceTab(event.currentTarget.value));
["po", "lot"].forEach((type) => {
  byId(`${type}-search-form`).addEventListener("submit", (event) => {
    event.preventDefault();
    searchLookup(type, event.currentTarget);
  });
  byId(`${type}-results`).addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-lookup-toggle]");
    if (toggle) {
      const parent = toggle.closest(".lookup-parent");
      const expanded = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(expanded));
      parent.classList.toggle("open", expanded);
      parent.querySelector(".lookup-children").hidden = !expanded;
      return;
    }
    const download = event.target.closest("[data-download-type]");
    if (download) downloadLookupItem(download.dataset.downloadType, Number(download.dataset.parentIndex), Number(download.dataset.itemIndex));
  });
});
byId("product-image").addEventListener("load", () => {
  const image = byId("product-image");
  byId("image-loading").hidden = true;
  image.classList.remove("loading");
  if (image.naturalWidth && image.naturalHeight) {
    image.closest(".image-stage").style.setProperty("--image-aspect", `${image.naturalWidth} / ${image.naturalHeight}`);
  }
});
byId("product-image").addEventListener("error", () => {
  const image = byId("product-image");
  image.removeAttribute("src");
  image.hidden = true;
  image.classList.remove("loading");
  byId("image-loading").hidden = true;
  byId("image-empty").hidden = false;
  byId("image-empty").querySelector("strong").textContent = "Không tải được ảnh sản phẩm";
  byId("image-tabs").hidden = true;
  byId("previous-image").hidden = true;
  byId("next-image").hidden = true;
});

renderSteps();
const initialUrl = new URL(window.location.href);
if (initialUrl.searchParams.has("rfid")) {
  initialUrl.searchParams.delete("rfid");
  history.replaceState({}, "", `${initialUrl.pathname}${initialUrl.search}${initialUrl.hash}`);
}
byId("rfid-input").value = "";
focusScannerInput();
