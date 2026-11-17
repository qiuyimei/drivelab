import type { Metadata } from "next";
import "./drive.css";
import "./tasks.css";

export const metadata: Metadata = {
  title: "DriveLab · 智能驾驶工况仿真与辅助分析",
  description: "围绕工况风险、日志差异、资料依据与候选方案的AI复盘工作台，连接可复算的计算和中文报告",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}

