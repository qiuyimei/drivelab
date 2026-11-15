import type { Metadata } from "next";
import "./drive.css";

export const metadata: Metadata = {
  title: "DriveLab · 智能驾驶工况仿真与辅助分析",
  description: "工况仿真、车辆动力学约束评估、实车日志对标与知识库辅助分析",
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

