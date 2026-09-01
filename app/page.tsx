"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowRight, ChevronDown, ChevronLeft, ChevronRight, Clipboard, Copy, FileSearch, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type DepartmentGroup = { name: string; count: number; icon: string; summary: string };
type TraceStep = { no: string; name: string; english: string; date?: string; content?: string; link?: string; color: string; detail?: string; departments?: DepartmentGroup[] };
type QueryStatus = { time: string; message: string; rfid: string };
type TraceMode = "rfid" | "rfid-new" | "po" | "lot";

function currentTime() {
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date());
}

const steps: TraceStep[] = [
  { no: "01", name: "Phát triển sản phẩm", english: "Product Development", date: "12/11/2025", color: "#4f7df3", detail: "Mẫu và tài liệu kỹ thuật đã được xác nhận." },
  { no: "02", name: "Số invoice", english: "Invoice Number", content: "TNKM26070050", color: "#e9be28", detail: "Chứng từ nhập nguyên phụ liệu." },
  { no: "03", name: "Nhập kho NPL", english: "RM Inbound", date: "09/05/2026", color: "#45ae7c", detail: "Nguyên phụ liệu đã được nhập kho." },
  { no: "04", name: "Kiểm NPL", english: "RM Inspection", date: "01/08/2026", color: "#e59b28", detail: "Hoàn tất kiểm tra chất lượng đầu vào.", departments: [
    { name: "BỘ PHẬN: NGUYÊN LIỆU", count: 1, icon: "🧵", summary: "Danh sách chứng từ kiểm nguyên liệu." },
    { name: "BỘ PHẬN: PHỤ LIỆU", count: 10, icon: "📦", summary: "Danh sách chứng từ kiểm phụ liệu." },
  ] },
  { no: "05", name: "Xuất kho NPL", english: "RM Outbound", date: "15/08/2026", color: "#ed7829", detail: "Nguyên phụ liệu đã xuất cho sản xuất." },
  { no: "06", name: "Nhận NPL từ kho", english: "Receive Materials", date: "15/08/2026", color: "#d93e83", detail: "Chuyền sản xuất đã xác nhận nhận vật tư." },
  { no: "07", name: "Xả vải", english: "Fabric Relaxing", date: "15/08/2026", color: "#8e45e8", detail: "Vải đã đủ thời gian xả theo tiêu chuẩn." },
  { no: "08", name: "Trải vải", english: "Fabric Spreading", date: "15/08/2026", color: "#596ee8", detail: "Hoàn tất trải vải theo sơ đồ cắt." },
  { no: "09", name: "Cắt vải", english: "Fabric Cutting", date: "15/08/2026", color: "#497fe0", detail: "Tem RFID được gắn với cây vải và bàn cắt." },
  { no: "10", name: "Kiểm BTP", english: "WIP Inspection", color: "#2b9bb5", detail: "Kiểm tra chất lượng bán thành phẩm." },
  { no: "11", name: "Nhập kho BTP", english: "WIP Inbound", color: "#31a681", detail: "Bán thành phẩm được nhập kho." },
  { no: "12", name: "Đặt BTP", english: "WIP Issuing", color: "#35a15a", detail: "Bán thành phẩm được cấp phát cho sản xuất." },
  { no: "13", name: "Xuất BTP", english: "WIP Outbound", color: "#4f7df3", detail: "Bán thành phẩm được xuất khỏi kho." },
  { no: "15", name: "Quét nhận BTP", english: "WIP Scanning", color: "#45ae7c", detail: "Chuyền sản xuất quét nhận bán thành phẩm." },
  { no: "16", name: "Kiểm Inline", english: "Inline Inspection", color: "#fb923c", detail: "Kiểm tra chất lượng trong chuyền." },
  { no: "17", name: "Biên bản kiểm sản phẩm đầu chuyền", english: "Start-of-Line Check", color: "#fb923c", detail: "Ghi nhận kết quả kiểm sản phẩm đầu chuyền." },
  { no: "18", name: "Kết quả kiểm sản phẩm cuối chuyền", english: "End-of-Line Check", color: "#596ee8", detail: "Ghi nhận kết quả kiểm sản phẩm cuối chuyền." },
  { no: "19", name: "Kiểm Enline", english: "Enline Inspection", color: "#8e45e8", detail: "Kiểm tra chất lượng Enline." },
  { no: "20", name: "Đóng gói", english: "Packing", color: "#d93e83", detail: "Sản phẩm được hoàn thiện và đóng gói." },
  { no: "21", name: "Nhập Kho Thành phẩm", english: "FG Inbound", color: "#31a681", detail: "Thành phẩm được nhập kho." },
  { no: "22", name: "Kiểm final", english: "Final Inspection", color: "#e9be28", detail: "Kiểm tra chất lượng cuối cùng." },
  { no: "23", name: "Xuất kho thành phẩm", english: "FG Outbound", color: "#ed7829", detail: "Thành phẩm được xuất khỏi kho." },
];

const info = [
  ["Khách hàng", "Customer", "CÔNG TY DESIPRO"], ["PO", "PO Number", "4524274909"],
  ["Mã hàng", "Style-CC", "376252"], ["Item", "Item Code", "5726661"], ["Size", "Size", "L"],
  ["Art", "Art Code", "8858322 = 9810034293 LIGHTY RPET BR PAO MM"], ["Màu sắc", "Color", "8977710-LS JERSEY DISCOVER"],
  ["Mùa", "Season", "AW26"], ["Xí nghiệp", "Factory", "1"], ["Chuyền", "Line", "1"], ["Lệnh sản xuất", "Production Order", "NHITY-0386-2026"],
  ["Bàn cắt", "Cut Table", "N/A"], ["LOT vải chính", "Main Fabric LOT", "N/A"],
  ["LOT vải phối", "Contrast Fabric LOT", "N/A"], ["Ngày may", "Sewing Date", "N/A"],
];

export default function Home() {
  const [traceMode, setTraceMode] = useState<TraceMode>("rfid");
  const [rfid, setRfid] = useState("");
  const [activeRfid, setActiveRfid] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [imageSide, setImageSide] = useState<"front" | "back">("front");
  const [imageFailed, setImageFailed] = useState(false);
  const [queryStatus, setQueryStatus] = useState<QueryStatus | null>(null);
  const normalized = useMemo(() => activeRfid.trim(), [activeRfid]);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.has("rfid")) {
      url.searchParams.delete("rfid");
      window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    }
  }, []);
  useEffect(() => { setImageFailed(false); }, [normalized, imageSide]);
  function search(event: FormEvent) { event.preventDefault(); const value = rfid.trim(); if (!value) return; setExpanded(null); setQueryStatus({ time: currentTime(), message: "Đang tra cứu ...", rfid: value }); setActiveRfid(value); setRfid(""); window.setTimeout(() => setQueryStatus((current) => current?.rfid === value && current.message === "Đang tra cứu ..." ? { time: currentTime(), message: "Tải dữ liệu xong", rfid: value } : current), 350); }
  function imageLoaded(source: string) { if (!source.includes("/api/traceability/image")) return; setQueryStatus((current) => current?.rfid === normalized ? { time: currentTime(), message: "Tải ảnh xong", rfid: normalized } : current); }
  async function copyRfid() { await navigator.clipboard.writeText(normalized); setCopied(true); window.setTimeout(() => setCopied(false), 1400); }

  return (
    <main className="min-h-screen bg-[#f8fafc] text-[#15213b]">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 shadow-[0_1px_12px_rgba(15,23,42,.05)] backdrop-blur">
        <div className="mx-auto flex max-w-[1900px] flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex min-w-fit items-center gap-4">
            <img src="/dong-tien-logo.png" alt="Công ty Cổ phần Đồng Tiến" className="h-auto w-[min(360px,62vw)]" />
            <div className="hidden border-l border-slate-200 pl-5 sm:block"><p className="text-sm font-bold leading-6">CỔNG TRUY XUẤT NGUỒN GỐC</p><p className="text-xs leading-5 text-slate-500">Product Traceability Portal</p></div>
          </div>
          {(traceMode === "rfid" || traceMode === "rfid-new") && <div className="w-full max-w-[760px]">
            <form onSubmit={search} className="flex w-full items-center rounded-full border-2 border-[#4c75f2] bg-white p-1.5 shadow-[0_0_0_5px_rgba(76,117,242,.09)]">
              <Search className="ml-3 size-5 shrink-0 text-[#3564ea]" /><input aria-label="Mã RFID" value={rfid} onChange={(e) => setRfid(e.target.value)} placeholder="Nhập hoặc quét mã RFID ..." className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm font-medium outline-none placeholder:text-slate-400 md:text-base" />
              <Button type="submit" className="rounded-full bg-[#3f63e9] px-5 hover:bg-[#3152d1]">Tra cứu <ArrowRight /></Button>
            </form>
            {queryStatus && <p className="mt-2 px-4 text-sm text-slate-500" role="status" aria-live="polite" aria-label="Dòng tình trạng truy vấn"><time className="font-semibold text-slate-700">[{queryStatus.time}]</time><span className="mx-2">- {queryStatus.message} - QR/RFID :</span><strong className="break-all font-semibold text-[#4164e8]">{queryStatus.rfid}</strong></p>}
          </div>}
        </div>
      </header>

      <nav className="mx-auto mt-5 flex max-w-[1900px] gap-1 overflow-x-auto border-b border-slate-200 px-5 lg:px-8" aria-label="Loại truy suất">{(["rfid", "rfid-new", "po", "lot"] as TraceMode[]).map((mode) => <button key={mode} type="button" onClick={() => { setTraceMode(mode); if (mode === "rfid-new" || mode === "rfid") setExpanded(null); }} aria-selected={traceMode === mode} className={`shrink-0 rounded-t-xl px-5 py-3 text-sm font-bold ${traceMode === mode ? "border border-b-white border-slate-200 bg-white text-[#3f63e9]" : "bg-slate-100 text-slate-500"}`}>{mode === "rfid-new" ? "Truy suất RFID mới" : `Truy suất ${mode.toUpperCase()}`}</button>)}</nav>

      {traceMode === "rfid" || traceMode === "rfid-new" ? <div className="mx-auto grid max-w-[1900px] gap-5 px-5 py-7 lg:grid-cols-[minmax(280px,.95fr)_minmax(310px,.88fr)_minmax(650px,1.9fr)] lg:px-8">
        <section className="min-w-0"><h2 className="section-title">Hình ảnh sản phẩm</h2><div className="product-card"><div className="product-image-wrap relative">{normalized && !imageFailed ? <><button type="button" aria-label="Xem mặt trước" onClick={() => setImageSide("front")} className="image-nav left-3"><ChevronLeft /></button><img key={`${normalized}-${imageSide}`} src={`/api/traceability/image?rfid=${encodeURIComponent(normalized)}&side=${imageSide}`} onLoad={(event) => imageLoaded(event.currentTarget.src)} onError={() => setImageFailed(true)} alt={imageSide === "front" ? "Mặt trước sản phẩm" : "Mặt sau sản phẩm"} className="product-image" loading="lazy" decoding="async" fetchPriority="low" /><button type="button" aria-label="Xem mặt sau" onClick={() => setImageSide("back")} className="image-nav right-3"><ChevronRight /></button></> : <div className="grid place-items-center gap-1 text-center text-slate-500"><strong className="text-sm text-slate-700">{imageFailed ? "Không tải được ảnh sản phẩm" : "Chưa có ảnh sản phẩm"}</strong><small>{imageFailed ? "RFID này chưa có ảnh mặt tương ứng" : "Nhập hoặc quét RFID để tải ảnh"}</small></div>}</div>{normalized && !imageFailed && <div className="flex items-center justify-center gap-2 bg-slate-100 py-3"><button type="button" onClick={() => setImageSide("front")} className={imageSide === "front" ? "image-side active" : "image-side"}>Mặt trước</button><button type="button" onClick={() => setImageSide("back")} className={imageSide === "back" ? "image-side active" : "image-side"}>Mặt sau</button></div>}</div></section>

        <section className="min-w-0"><h2 className="section-title">Thông tin chung</h2><div className="h-[780px] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-sm scrollbar-thin">
          <div className="info-row items-start"><div><p className="font-bold text-[#4266e8]">Mã RFID</p><p className="sub-label">RFID Tag ID</p></div><div className="flex min-w-0 items-center gap-2"><span className="break-all text-right text-xs font-bold">{normalized}</span><button onClick={copyRfid} aria-label="Sao chép RFID" className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-[#4266e8]">{copied ? <Clipboard className="size-4 text-emerald-500" /> : <Copy className="size-4" />}</button></div></div>
          {info.map(([label, english, value]) => <div className="info-row" key={label}><div className="shrink-0"><p className="font-medium text-slate-500">{label}</p><p className="sub-label">{english}</p></div><span className={label === "Size" || label === "Xí nghiệp" || label === "Chuyền" ? "value-chip" : "max-w-[62%] text-right text-sm font-bold"}>{value}</span></div>)}
        </div></section>

        <section className="min-w-0"><Tabs defaultValue="tree" className="gap-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="section-title mb-0">Tiến trình phát triển sản phẩm và sản xuất</h2><TabsList className="h-11 rounded-xl bg-slate-100 p-1"><TabsTrigger value="diagram" className="rounded-lg px-4 data-[state=active]:text-[#4164e8]">Sơ đồ</TabsTrigger><TabsTrigger value="tree" className="rounded-lg px-4 data-[state=active]:text-[#4164e8]">Cây thư mục</TabsTrigger></TabsList></div>
          <TabsContent value="tree"><div className="h-[780px] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 shadow-sm scrollbar-thin md:p-7"><div className="overflow-hidden rounded-2xl border border-slate-200"><Table><TableHeader className="bg-[#172239] text-white"><TableRow className="border-none hover:bg-[#172239]"><TableHead className="h-16 w-[62%] pl-5 font-bold text-white">CÔNG ĐOẠN / STEP</TableHead><TableHead className="w-[23%] font-bold text-white">NGÀY HOÀN THÀNH / DATE</TableHead><TableHead className="w-[15%] font-bold text-white">LIÊN KẾT / LINK</TableHead></TableRow></TableHeader><TableBody>{steps.map((step) => <FragmentRow key={step.no} step={step} open={expanded === step.no} onToggle={() => setExpanded(expanded === step.no ? null : step.no)} />)}</TableBody></Table></div></div></TabsContent>
          <TabsContent value="diagram"><div className="h-[780px] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-sm scrollbar-thin"><div className="mx-auto max-w-2xl">{steps.map((step, index) => <div key={step.no} className="relative flex gap-5 pb-6 last:pb-0">{index < steps.length - 1 && <span className="absolute left-[21px] top-11 h-[calc(100%-28px)] w-px bg-slate-200" />}<span className="relative z-10 grid size-11 shrink-0 place-items-center rounded-full text-xs font-bold text-white shadow-sm" style={{ backgroundColor: step.color }}>{step.no}</span><button onClick={() => setExpanded(expanded === step.no ? null : step.no)} className="flex-1 rounded-xl border border-slate-200 p-4 text-left transition hover:border-[#829cf2] hover:shadow-sm"><div className="flex items-start justify-between gap-3"><div><p className="font-bold">{step.name}</p><p className="sub-label italic">{step.english}</p></div>{step.date && <span className="date-chip">{step.date}</span>}</div>{expanded === step.no && <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-500">{step.detail}</p>}</button></div>)}</div></div></TabsContent>
        </Tabs></section>
      </div> : <LookupPanel type={traceMode} />}
      <footer className="mx-auto flex max-w-[1900px] items-center justify-between px-8 pb-6 text-xs text-slate-400"><span>Nguồn dữ liệu: eGMF · RFID Cutting Mapping</span><span>Đồng bộ theo mã RFID</span></footer>
    </main>
  );
}

function LookupPanel({ type }: { type: "po" | "lot" }) {
  const [searched, setSearched] = useState(false);
  const items = type === "po"
    ? ["Nguyên liệu", "Phụ liệu", "Tem RFID", "Tem SHU", "Hồ sơ kỹ thuật", "Hồ sơ thông quan", "Hồ sơ chất lượng"]
    : ["Phiếu kiểm định", "Phiếu nhập hàng", "Sản phẩm", "PO", "Hồ sơ chất lượng"];
  return <section className="mx-auto max-w-[1500px] px-5 py-7 lg:px-8"><div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-xl font-bold">Truy suất theo {type.toUpperCase()}</h2><p className="mt-1 text-sm text-slate-500">Khách hàng và giá trị truy suất đều bắt buộc, hệ thống chỉ tìm chính xác.</p><form onSubmit={(event) => { event.preventDefault(); setSearched(true); }} className="mt-6 grid gap-4 md:grid-cols-[1fr_1.5fr_auto]"><label className="grid gap-2 text-sm font-bold">Khách hàng <input required placeholder="Nhập mã khách hàng" className="rounded-xl border border-slate-300 px-4 py-3 font-normal outline-none focus:border-[#5276ed]" /></label><label className="grid gap-2 text-sm font-bold">{type.toUpperCase()} <input required placeholder={`Nhập chính xác ${type.toUpperCase()}`} className="rounded-xl border border-slate-300 px-4 py-3 font-normal outline-none focus:border-[#5276ed]" /></label><Button type="submit" className="self-end rounded-xl bg-[#3f63e9] px-6 py-6">Tra cứu {type.toUpperCase()} <ArrowRight /></Button></form>{searched ? <div className="mt-6 overflow-hidden rounded-xl border border-slate-200"><div className="flex items-center justify-between bg-[#f8faff] px-5 py-4"><strong>{type === "po" ? "Mã hàng — Danh sách hạng mục" : "LOT — Danh sách hạng mục"}</strong><span className="text-xs text-slate-500">{items.length} hạng mục</span></div><Table><TableHeader className="bg-[#172239]"><TableRow><TableHead className="w-16 text-white">STT</TableHead><TableHead className="text-white">{type === "po" ? "Tên hạng mục" : "Hạng mục"}</TableHead><TableHead className="text-right text-white">SL</TableHead><TableHead className="text-right text-white">SL Yard</TableHead><TableHead className="text-white">Tải danh sách</TableHead></TableRow></TableHeader><TableBody>{items.map((item, index) => <TableRow key={item}><TableCell>{index + 1}</TableCell><TableCell className="font-semibold">{item}</TableCell><TableCell className="text-right">—</TableCell><TableCell className="text-right">—</TableCell><TableCell><button className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700">Tải danh sách</button></TableCell></TableRow>)}</TableBody></Table></div> : <div className="mt-6 grid min-h-52 place-items-center rounded-xl border border-dashed border-slate-300 text-slate-400">Chưa có dữ liệu truy suất {type.toUpperCase()}</div>}</div></section>;
}

function FragmentRow({ step, open, onToggle }: { step: TraceStep; open: boolean; onToggle: () => void }) {
  return <><TableRow className="group cursor-pointer border-slate-100 hover:bg-slate-50" onClick={onToggle} aria-expanded={open}><TableCell className="whitespace-normal py-4 pl-5"><div className="flex items-center gap-3">{open ? <ChevronDown className="size-4 shrink-0 text-slate-400" /> : <ChevronRight className="size-4 shrink-0 text-slate-400" />}<span className="grid size-8 shrink-0 place-items-center rounded-full text-xs font-bold text-white shadow-sm" style={{ backgroundColor: step.color }}>{step.no}</span><div><p className="text-base font-bold text-[#142038]">{step.name}</p><p className="sub-label italic">{step.english}</p></div></div></TableCell><TableCell>{step.date ? <span className="date-chip">{step.date}</span> : <span className="font-semibold text-[#4a70ef]">Nhấn để mở</span>}</TableCell><TableCell>{step.link ? <a href={step.link} title="Xem chứng từ" aria-label="Xem chứng từ" onClick={(e) => e.stopPropagation()} className="inline-grid size-10 place-items-center rounded-xl border border-blue-200 bg-blue-50 text-[#4266e8] hover:bg-[#4266e8] hover:text-white"><FileSearch className="size-6" /></a> : <span className="text-slate-400">-</span>}</TableCell></TableRow>{open && (step.departments ? step.departments.map((department) => <DepartmentRow key={department.name} department={department} />) : <TableRow className="bg-[#f7f9ff] hover:bg-[#f7f9ff]"><TableCell colSpan={3} className="whitespace-normal px-14 py-4 text-sm text-slate-600"><div className="flex items-start gap-2"><Clipboard className="mt-0.5 size-4 shrink-0 text-[#5074ef]" /><span>{step.detail}</span></div></TableCell></TableRow>)}</>;
}

function DepartmentRow({ department }: { department: DepartmentGroup }) {
  const [open, setOpen] = useState(false);
  return <><TableRow className="bg-[#f5f7fb] hover:bg-[#f0f4fa]"><TableCell colSpan={2} className="border-l-4 border-[#6f96ff] py-4 pl-14"><button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-3 text-left"><ChevronRight className={`size-4 shrink-0 text-slate-500 transition-transform ${open ? "rotate-90" : ""}`} /><span aria-hidden="true" className="text-lg">{department.icon}</span><strong className="text-sm text-[#172239]">{department.name}</strong></button></TableCell><TableCell className="text-right"><span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">{department.count} bản ghi</span></TableCell></TableRow>{open && <TableRow className="bg-[#fbfdff] hover:bg-[#f7faff]"><TableCell colSpan={3} className="border-l-4 border-[#6f96ff] py-4 pl-20 text-sm text-slate-600"><div className="flex items-start gap-2"><Clipboard className="mt-0.5 size-4 shrink-0 text-[#5074ef]" /><span>{department.summary}</span></div></TableCell></TableRow>}</>;
}
