import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cổng Truy Xuất Nguồn Gốc",
  description: "Tra cứu tiến trình phát triển và sản xuất theo mã RFID.",
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body className="antialiased">{children}</body></html>;
}
