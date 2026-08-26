const SAMPLE_RFID = "(01)03608393748683(21)000000092192";
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
const state = { rfid: "", trackedRfid: null, side: "front", imageAvailability: { front: true, back: true } };

const byId = (id) => document.getElementById(id);

function renderSteps() {
  byId("steps-body").innerHTML = steps.map((step, index) => `
    <tr>
      <td><div class="step-name"><span class="chevron">›</span><span class="step-number" style="background:${colors[index % colors.length]}">${step[0]}</span><span><b>${step[1]}</b><small>${step[2]}</small></span></div></td>
      <td><span class="pending">Chờ dữ liệu</span></td><td>—</td><td>—</td>
    </tr>`).join("");
}

function field(data, ...names) {
  for (const name of names) {
    const key = Object.keys(data).find((candidate) => candidate.toLowerCase() === name.toLowerCase());
    if (key && data[key] != null) return String(data[key]);
  }
  return "—";
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
  byId("value-customer-code").textContent = field(data, "MaKhachHang");
  byId("value-po").textContent = field(data, "PO");
  byId("value-product-code").textContent = field(data, "ProductCode");
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

function imageUrl() {
  return `/api/traceability/image?rfid=${encodeURIComponent(state.rfid)}&side=${state.side}`;
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
  image.src = imageUrl();
}

async function loadImages() {
  try {
    state.imageAvailability = await getJson(`/api/traceability/images?rfid=${encodeURIComponent(state.rfid)}`);
  } catch (_) {
    state.imageAvailability = { front: false, back: false };
  }
  renderImage();
}

async function search(rfid, trackStatus = false) {
  state.rfid = rfid.trim();
  if (!state.rfid) return;
  state.trackedRfid = trackStatus ? state.rfid : null;
  setQueryStatus("Đang tra cứu ...");
  setNotice("Đang tải thông tin…", "loading");
  const url = new URL(window.location.href);
  url.searchParams.set("rfid", state.rfid);
  history.replaceState({}, "", url);
  try {
    const data = await getJson(`/api/traceability?rfid=${encodeURIComponent(state.rfid)}`);
    if (!data || Object.keys(data).length === 0) {
      setQueryStatus("Không tìm thấy dữ liệu");
      setNotice("Không tìm thấy dữ liệu cho RFID này", "error");
      return;
    }
    showData(data);
    setQueryStatus("Tải dữ liệu xong");
    setNotice("Đã tải dữ liệu RFID", "success");
    loadImages();
  } catch (error) {
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
byId("previous-image").addEventListener("click", () => { state.side = state.side === "front" ? "back" : "front"; renderImage(); });
byId("next-image").addEventListener("click", () => { state.side = state.side === "front" ? "back" : "front"; renderImage(); });
byId("product-image").addEventListener("load", () => { const image = byId("product-image"); byId("image-loading").hidden = true; image.classList.remove("loading"); if (image.src.includes("/api/traceability/image")) setQueryStatus("Tải ảnh xong"); });
byId("product-image").addEventListener("error", () => { byId("product-image").src = FALLBACK_IMAGE; byId("image-loading").textContent = "Không tải được ảnh"; byId("product-image").classList.remove("loading"); });

renderSteps();
const initialRfid = new URLSearchParams(location.search).get("rfid") || SAMPLE_RFID;
byId("rfid-input").value = initialRfid;
search(initialRfid);
