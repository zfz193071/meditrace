"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";

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

function formatDate(timestamp: number): string {
  return new Date(timestamp).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
  alert("已复制到剪贴板");
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
    <main className="min-h-screen home-bg">
      {/* 头部横幅 */}
      <section className="gradient-bg text-white header-banner">
        <div className="max-w-4xl mx-auto">
          <div className="header-content mb-6">
            <button
              onClick={() => router.push("/")}
              className="back-btn"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex-1 justify-center">
              <h1 className="text-3xl md:text-4xl font-bold">链上记录验证</h1>
              <p className="text-white/80 mt-1">验证诊断记录的真实性和完整性</p>
            </div>
            <div className="w-6"></div>
          </div>
        </div>
      </section>

      {/* 主要内容 */}
      <section className="py-8 page-container">
        <div className="max-w-4xl mx-auto">
          {/* 输入框卡片 */}
          <div className="bg-white rounded-2xl card-shadow-xl p-8 mb-8" style={{ backgroundColor: 'white', padding: '2rem' }}>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              诊断 ID
            </label>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                value={inputId}
                onChange={(e) => setInputId(e.target.value)}
                placeholder="输入诊断 ID"
                className="input-modern flex-1 font-mono text-sm"
                onKeyDown={(e) => e.key === "Enter" && verifyDiagnosis(inputId)}
              />
              <button
                onClick={() => verifyDiagnosis(inputId)}
                disabled={loading || !inputId.trim()}
                className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                style={{ marginTop: '10px' }}
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full spinner"></div>
                    验证中...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    验证
                  </>
                )}
              </button>
            </div>
          </div>

          {/* 验证结果 */}
          {result && (
            <div className="bg-white rounded-2xl card-shadow-xl p-10 mb-8 fade-in">
              {result.isValid ? (
                <>
                  {/* 验证通过头部 */}
                  <div className="flex items-start gap-4 mb-8">
                    <div className="w-16 h-16 bg-gradient-to-br from-green-400 to-emerald-500 rounded-2xl flex items-center justify-center flex-shrink-0">
                      <span className="text-4xl">✅</span>
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold text-green-600 mb-1">验证通过</h2>
                      <p className="text-gray-600">该诊断记录真实存在于区块链</p>
                    </div>
                  </div>

                  {/* 链上记录详情 */}
                  <div className="bg-gradient-to-br from-blue-50 to-cyan-50 rounded-2xl p-6 mb-6">
                    <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                      <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      链上记录详情
                    </h3>
                    <div className="space-y-4">
                      <div className="bg-white rounded-xl p-5">
                        <div className="flex justify-between items-start mb-2">
                          <span className="text-sm text-gray-500">数据哈希:</span>
                          <code 
                            className="text-xs bg-gray-100 px-2 py-1 rounded cursor-pointer hover:bg-gray-200 font-mono max-w-[200px] truncate"
                            onClick={() => copyToClipboard(result.chainRecord?.dataHash || "")}
                            title={result.chainRecord?.dataHash}
                          >
                            {result.chainRecord?.dataHash?.substring(0, 32)}...
                          </code>
                        </div>
                      </div>
                      
                      <div className="bg-white rounded-xl p-5">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm text-gray-500">模型版本:</span>
                          <span className="font-mono text-sm bg-white px-3 py-1 rounded-lg">
                            {result.chainRecord?.modelVersion}
                          </span>
                        </div>
                      </div>
                      
                      <div className="bg-white rounded-xl p-5">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-sm text-gray-500">时间戳:</span>
                          <span className="text-sm bg-white px-3 py-1 rounded-lg">
                            {formatDate(result.chainRecord?.timestamp || 0)}
                          </span>
                        </div>
                      </div>
                      
                      <div className="bg-white rounded-xl p-5">
                        <div className="flex justify-between items-start mb-2">
                          <span className="text-sm text-gray-500">患者地址:</span>
                          <code className="font-mono text-xs bg-white px-3 py-1 rounded-lg">
                            {result.chainRecord?.patient}
                          </code>
                        </div>
                      </div>
                      
                      {result.chainRecord?.ipfsCid && (
                        <div className="bg-white rounded-xl p-5">
                          <div className="flex justify-between items-start mb-2">
                            <span className="text-sm text-gray-500">IPFS CID:</span>
                            <code 
                              className="text-xs bg-gray-100 px-2 py-1 rounded cursor-pointer hover:bg-gray-200 font-mono max-w-[200px] truncate"
                              onClick={() => copyToClipboard(result.chainRecord?.ipfsCid || "")}
                              title={result.chainRecord?.ipfsCid}
                            >
                              {result.chainRecord.ipfsCid.substring(0, 20)}...
                            </code>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 区块链浏览器链接 */}
                  <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-5">
                    <p className="text-sm text-blue-800 mb-3 font-medium">在区块链浏览器中查看:</p>
                    <a
                      href={`https://sepolia.etherscan.io/tx/${result.chainRecord?.dataHash}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium transition-colors"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      打开 Etherscan
                    </a>
                  </div>
                </>
              ) : (
                /* 验证失败 */
                <div className="flex items-start gap-4">
                  <div className="w-16 h-16 bg-gradient-to-br from-red-400 to-pink-500 rounded-2xl flex items-center justify-center flex-shrink-0">
                    <span className="text-4xl">❌</span>
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-red-600 mb-1">验证失败</h2>
                    <p className="text-gray-600">未找到该诊断记录，可能不存在或已被篡改</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 说明卡片 */}
          <div className="bg-gradient-to-br from-indigo-50 to-purple-50 border-2 border-indigo-200 rounded-2xl p-8">
            <h3 className="font-semibold text-indigo-900 mb-4" style={{ marginTop: '15px' }}>
              如何验证？
            </h3>
            <ol className="space-y-3" style={{ listStyleType: 'none', padding: 0, margin: 0 }}>
              <li className="flex items-center gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-indigo-500 text-white rounded-full flex items-center justify-center text-sm font-medium" style={{ marginRight: '10px' }}>1</span>
                <span className="text-indigo-800 text-sm">从诊断结果或历史记录中获取诊断 ID</span>
              </li>
              <li className="flex items-center gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-indigo-500 text-white rounded-full flex items-center justify-center text-sm font-medium" style={{ marginRight: '10px' }}>2</span>
                <span className="text-indigo-800 text-sm">在上方输入框中输入诊断 ID</span>
              </li>
              <li className="flex items-center gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-indigo-500 text-white rounded-full flex items-center justify-center text-sm font-medium" style={{ marginRight: '10px' }}>3</span>
                <span className="text-indigo-800 text-sm">系统会查询区块链并验证数据哈希</span>
              </li>
              <li className="flex items-center gap-3">
                <span className="flex-shrink-0 w-6 h-6 bg-indigo-500 text-white rounded-full flex items-center justify-center text-sm font-medium" style={{ marginRight: '10px' }}>4</span>
                <span className="text-indigo-800 text-sm">如果验证通过，显示完整的链上记录</span>
              </li>
            </ol>
          </div>
        </div>
      </section>

      {/* 页脚 */}
      <footer className="bg-gray-800 text-white py-8 px-6 mt-12">
        <div className="max-w-4xl mx-auto text-center" style={{ textAlign: 'center' }}>
          <p className="text-gray-500 text-sm">
            © 2024 MediTrace. Built with Next.js, FastAPI & Blockchain
          </p>
        </div>
      </footer>
    </main>
  );
}
