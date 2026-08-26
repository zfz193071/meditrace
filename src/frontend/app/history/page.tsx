"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface HistoryRecord {
  diagnosisId: string;
  timestamp: number;
  diseaseTypes: string[];
  chainStatus: "pending" | "confirmed" | "failed";
}

function formatDate(timestamp: number): string {
  // 后端返回的是秒级时间戳，需要转换为毫秒级
  const msTimestamp = timestamp * 1000;
  return new Date(msTimestamp).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getStatusBadge(chainStatus: string) {
  switch (chainStatus) {
    case "confirmed":
      return (
        <span className="badge badge-success flex items-center gap-1">
          <span className="text-xs">✓</span> 已上链
        </span>
      );
    case "pending":
      return (
        <span className="badge badge-warning flex items-center gap-1">
          <span className="text-xs">⏳</span> 待上链
        </span>
      );
    case "failed":
      return (
        <span className="badge badge-error flex items-center gap-1">
          <span className="text-xs">✗</span> 上链失败
        </span>
      );
    default:
      return null;
  }
}

export default function HistoryPage() {
  const router = useRouter();
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState("0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B");
  const [addressError, setAddressError] = useState("");
  
  const validateAddress = (address: string): boolean => {
    if (!address) {
      setAddressError("");
      return true;
    }
    if (!address.startsWith("0x")) {
      setAddressError("地址必须以 0x 开头");
      return false;
    }
    if (address.length !== 42) {
      setAddressError("地址长度不正确 (应为 42 字符)");
      return false;
    }
    const hexPart = address.slice(2);
    if (!/^[0-9a-fA-F]{40}$/.test(hexPart)) {
      setAddressError("地址包含无效的十六进制字符");
      return false;
    }
    setAddressError("");
    return true;
  };
  
  const handleUserIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setUserId(newValue);
    validateAddress(newValue);
  };

  useEffect(() => {
    fetchHistory();
  }, [userId]);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/history/${userId}`
      );
      const data = await response.json();
      const records = data.records || [];
      // 按时间戳降序排序，最新的记录显示在最前面
      records.sort((a, b) => b.timestamp - a.timestamp);
      setRecords(records);
    } catch (error) {
      console.error("获取历史记录失败:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen home-bg">
      {/* 头部横幅 */}
      <section className="gradient-bg text-white header-banner">
        <div className="max-w-6xl mx-auto">
          <div className="header-content mb-6">
            <button
              onClick={() => router.push("/")}
              className="back-btn"
            >
              <svg className="w-6 h-6 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex items-center gap-4 flex-1 justify-center">
              <div>
                <h1 className="text-3xl md:text-4xl font-bold">诊断历史记录</h1>
                <p className="text-white/80 mt-1">查看您的历史诊断记录和溯源状态</p>
              </div>
            </div>
            <div className="w-6"></div>
          </div>
        </div>
      </section>

      {/* 主要内容 */}
      <section className="py-8 page-container">
        <div className="max-w-6xl mx-auto">
          {/* 用户信息卡片 */}
          <div className="history-card-bg rounded-2xl card-shadow-xl p-6 mb-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <p className="text-sm text-gray-500 mb-0">当前用户</p>
                <code className="font-mono text-sm bg-gray-100 px-3 py-1 rounded-lg">
                  {userId.slice(0, 10)}...{userId.slice(-8)}
                </code>
              </div>
              
              <div className="flex items-center gap-3">
                <button
                  onClick={fetchHistory}
                  className="btn-primary flex items-center gap-2"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  刷新
                </button>
              </div>
            </div>
            
            <div className="mt-5 pt-5 border-t border-gray-100">
              <label className="block text-xs font-medium text-gray-500 mb-2">
                切换用户地址:
              </label>
              <input
                type="text"
                className={`input-modern font-mono text-xs ${
                  addressError ? "border-red-400" : ""
                }`}
                placeholder="0x..."
                value={userId}
                onChange={handleUserIdChange}
              />
              {addressError && (
                <p className="text-xs text-red-600 mt-2 flex items-center">
                  <span className="mr-1">⚠️</span>
                  {addressError}
                </p>
              )}
            </div>
          </div>

          {/* 历史记录列表 */}
          {loading ? (
            <div className="history-card-bg rounded-2xl card-shadow-xl p-16 text-center">
              <div className="inline-block">
                <div className="w-16 h-16 border-4 border-green-200 border-t-green-600 rounded-full spinner mx-auto mb-4"></div>
                <p className="text-gray-600">加载中...</p>
              </div>
            </div>
          ) : records.length === 0 ? (
            <div className="history-card-bg rounded-2xl card-shadow-xl p-16 text-center">
              <div className="w-24 h-24 bg-gradient-to-br from-orange-100 to-red-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <span className="text-6xl">📋</span>
              </div>
              <h3 className="text-2xl font-bold text-gray-800 mb-2">暂无历史记录</h3>
              <p className="text-gray-600 mb-8">您还没有进行过诊断</p>
              <button
                onClick={() => router.push("/")}
                className="btn-primary px-8 py-3"
              >
                开始诊断
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-gray-600">
                  共 <span className="font-semibold text-gray-800">{records.length}</span> 条记录
                </p>
              </div>
              
              {records.map((record, index) => (
                <div 
                  key={index} 
                  className="history-card-bg rounded-2xl card-shadow-xl p-6 hover-lift fade-in"
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4 mb-5">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold text-gray-800">
                          诊断 ID
                        </h3>
                        {getStatusBadge(record.chainStatus)}
                      </div>
                      <code className="font-mono text-sm bg-gray-100 px-3 py-1.5 rounded-lg text-gray-700">
                        {record.diagnosisId}
                      </code>
                      <p className="text-sm text-gray-500 mt-2 flex items-center gap-1">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {formatDate(record.timestamp)}
                      </p>
                    </div>
                  </div>

                  <div className="border-t border-gray-100 pt-5">
                    <p className="text-sm font-medium text-gray-700 mb-3">可能疾病:</p>
                    <div className="flex flex-wrap gap-2">
                      {record.diseaseTypes.map((disease, i) => (
                        <span
                          key={i}
                          className="badge badge-info"
                        >
                          {disease}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-3">
                    <button
                      onClick={() =>
                        router.push(`/verify?diagnosisId=${record.diagnosisId}`)
                      }
                      className="btn-secondary flex items-center gap-2"
                    >
                      <span>🔍</span> 验证记录
                    </button>
                    <button
                       onClick={async () => {
                         try {
                           const response = await fetch(
                             `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/report/${record.diagnosisId}`
                           );
                           if (!response.ok) {
                             throw new Error("下载失败");
                           }
                           const blob = await response.blob();
                           const url = window.URL.createObjectURL(blob);
                           const a = document.createElement("a");
                           a.href = url;
                           a.download = `diagnosis-report-${record.diagnosisId}.pdf`;
                           document.body.appendChild(a);
                           a.click();
                           window.URL.revokeObjectURL(url);
                           document.body.removeChild(a);
                         } catch (error) {
                           console.error("下载报告失败:", error);
                           alert("下载报告失败，请稍后重试");
                         }
                       }}
                       className="btn-secondary flex items-center gap-2"
                     >
                      <span>📄</span> 下载报告
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* 页脚 */}
      <footer className="bg-gray-800 text-white py-8 px-6 mt-12">
        <div className="max-w-6xl mx-auto text-center" style={{ textAlign: 'center' }}>
          <p className="text-gray-500 text-sm">
            © 2024 MediTrace. Built with Next.js, FastAPI & Blockchain
          </p>
        </div>
      </footer>
    </main>
  );
}
