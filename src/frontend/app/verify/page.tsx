"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { formatDate, copyToClipboard } from "../../lib/utils";

interface ChainRecord {
  dataHash: string;
  modelVersion: string;
  timestamp: number;
  ipfsCid: string;
  patient: string;
}

interface VerificationResult {
  isValid: boolean;
  chainRecord: ChainRecord | null;
  ipfsCid: string;
}

export default function VerifyPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const diagnosisId = searchParams.get("diagnosisId") || "";
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [inputId, setInputId] = useState(diagnosisId);

  useEffect(() => {
    if (diagnosisId) {
      verifyDiagnosis(diagnosisId);
    }
  }, [diagnosisId]);

  const verifyDiagnosis = async (id: string) => {
    if (!id.trim()) return;
    
    setLoading(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/verify/${id}`
      );
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error("验证失败:", error);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen p-8 bg-gray-50">
      <div className="max-w-4xl mx-auto">
        {/* 头部 */}
        <header className="mb-8">
          <button
            onClick={() => router.push("/")}
            className="mb-4 text-green-600 hover:text-green-700"
          >
            ← 返回首页
          </button>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">链上记录验证</h1>
          <p className="text-gray-600">验证诊断记录的真实性和完整性</p>
        </header>

        {/* 输入框 */}
        <section className="bg-white rounded-lg shadow p-6 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            诊断 ID
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={inputId}
              onChange={(e) => setInputId(e.target.value)}
              placeholder="输入诊断 ID"
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
            />
            <button
              onClick={() => verifyDiagnosis(inputId)}
              disabled={loading || !inputId.trim()}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? "验证中..." : "验证"}
            </button>
          </div>
        </section>

        {/* 验证结果 */}
        {result && (
          <section className="bg-white rounded-lg shadow p-6">
            {result.isValid ? (
              <>
                <div className="flex items-center gap-2 mb-6">
                  <div className="text-4xl">✅</div>
                  <div>
                    <h2 className="text-xl font-semibold text-green-600">验证通过</h2>
                    <p className="text-sm text-gray-600">该诊断记录真实存在于区块链</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="border rounded-lg p-4">
                    <h3 className="font-medium mb-3">链上记录详情</h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">数据哈希:</span>
                        <code 
                          className="bg-gray-100 px-2 py-1 rounded cursor-pointer hover:bg-gray-200"
                          onClick={() => copyToClipboard(result.chainRecord?.dataHash || "")}
                        >
                          {result.chainRecord?.dataHash?.substring(0, 32)}...
                        </code>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">模型版本:</span>
                        <span className="font-mono">{result.chainRecord?.modelVersion}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">时间戳:</span>
                        <span>{formatDate(result.chainRecord?.timestamp || 0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">患者地址:</span>
                        <code className="bg-gray-100 px-2 py-1 rounded">
                          {result.chainRecord?.patient}
                        </code>
                      </div>
                      {result.chainRecord?.ipfsCid && (
                        <div className="flex justify-between">
                          <span className="text-gray-600">IPFS CID:</span>
                          <code 
                            className="bg-gray-100 px-2 py-1 rounded cursor-pointer hover:bg-gray-200"
                            onClick={() => copyToClipboard(result.chainRecord?.ipfsCid || "")}
                          >
                            {result.chainRecord.ipfsCid.substring(0, 20)}...
                          </code>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 区块链浏览器链接 */}
                  <div className="border-t pt-4">
                    <p className="text-sm text-gray-600 mb-2">在区块链浏览器中查看:</p>
                    <a
                      href={`https://sepolia.etherscan.io/tx/${result.chainRecord?.dataHash}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-green-600 hover:text-green-700 underline"
                    >
                      🔗 打开 Etherscan
                    </a>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <div className="text-4xl">❌</div>
                <div>
                  <h2 className="text-xl font-semibold text-red-600">验证失败</h2>
                  <p className="text-gray-600">未找到该诊断记录，可能不存在或已被篡改</p>
                </div>
              </div>
            )}
          </section>
        )}

        {/* 说明 */}
        <section className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="font-medium text-blue-800 mb-2">如何验证?</h3>
          <ol className="list-decimal list-inside text-sm text-blue-700 space-y-1">
            <li>从诊断结果或历史记录中获取诊断 ID</li>
            <li>在上方输入框中输入诊断 ID</li>
            <li>系统会查询区块链并验证数据哈希</li>
            <li>如果验证通过，显示完整的链上记录</li>
          </ol>
        </section>
      </div>
    </main>
  );
}
