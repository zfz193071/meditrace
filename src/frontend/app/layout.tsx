import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediTrace - 医疗 AI 诊断溯源系统",
  description: "结合大模型与 Web3 技术的医疗诊断辅助系统",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
