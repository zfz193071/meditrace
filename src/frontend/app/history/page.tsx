"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { formatDate, getStatusColor } from "../../lib/utils";

interface HistoryRecord {
  diagnosisId: string;
  timestamp: number;
  diseaseTypes: string[];
  chainStatus: "pending" | "confirmed" | "failed";
}

export default function HistoryPage() {
  const router = useRouter();
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState("0x262Ee58D3e7A782ceC68094a6DACb53D02Fa9d0B");
  
  // 允许用户修改地址
  const handleUserIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUserId(e.target.value);
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
      setRecords(data.records || []);
    } catch (error) {
      console.error("获取历史记录失败:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen p-8 bg-gray-50">
      <div className="max-w-6xl mx-auto">
        {/* 头部 */}
        <header className="mb-8">
          <button
            onClick={() => router.push("/")}
            className="mb-4 text-green-600 hover:text-green-700"
          >
            ← 返回首页
          </button>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">诊断历史记录</h1>
          <p className="text-gray-600">查看您的历史诊断记录和溯源状态</p>
        </header>

        {/* 用户信息 */}
        <section className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="flex justify-between items-center mb-3">
            <div>
              <p className="text-sm text-gray-500">当前用户</p>
              <p className="font-mono text-sm">{userId}</p>
            </div>
            <button
              onClick={fetchHistory}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              刷新
            </button>
          </div>
          <div>
            <label className="text-xs text-gray-500">切换用户地址:</label>
            <input
              type="text"
              className="w-full mt-1 p-2 border border-gray-300 rounded font-mono text-xs"
              placeholder="0x..."
              value={userId}
              onChange={handleUserIdChange}
            />
          </div>
        </section>

        {/* 历史记录列表 */}
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
            <p className="mt-4 text-gray-600">加载中...</p>
          </div>
        ) : records.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="text-6xl mb-4">📋</div>
            <h3 className="text-xl font-semibold mb-2">暂无历史记录</h3>
            <p className="text-gray-600 mb-6">您还没有进行过诊断</p>
            <button
              onClick={() => router.push("/")}
              className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              开始诊断
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {records.map((record, index) => (
              <div key={index} className="bg-white rounded-lg shadow p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-lg font-semibold mb-1">
                      诊断 ID: <code className="bg-gray-100 px-2 py-1 rounded">{record.diagnosisId}</code>
                    </h3>
                    <p className="text-sm text-gray-500">
                      {formatDate(record.timestamp)}
                    </p>
                  </div>
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(
                      record.chainStatus
                    )}`}
                  >
                    {record.chainStatus === "confirmed" && "✓ "}
                    {record.chainStatus === "pending" && "⏳ "}
                    {record.chainStatus === "failed" && "✗ "}
                    {record.chainStatus === "confirmed"
                      ? "已上链"
                      : record.chainStatus === "pending"
                      ? "待上链"
                      : "上链失败"}
                  </span>
                </div>

                <div className="border-t pt-4">
                  <p className="text-sm font-medium mb-2">可能疾病:</p>
                  <div className="flex flex-wrap gap-2">
                    {record.diseaseTypes.map((disease, i) => (
                      <span
                        key={i}
                        className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm"
                      >
                        {disease}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mt-4 flex gap-3">
                  <button
                    onClick={() =>
                      router.push(`/verify?diagnosisId=${record.diagnosisId}`)
                    }
                    className="px-4 py-2 border border-green-600 text-green-600 rounded hover:bg-green-50"
                  >
                    🔍 验证记录
                  </button>
                  <button className="px-4 py-2 border border-gray-300 text-gray-600 rounded hover:bg-gray-50">
                    📄 下载报告
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
