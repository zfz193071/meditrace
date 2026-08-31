"use client";

import { useState } from "react";

export default function Home() {
  const [symptoms, setSymptoms] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
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
  
  const handleAddressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setUserId(newValue);
    validateAddress(newValue);
  };

  const handleDiagnose = async () => {
    if (!symptoms.trim()) return;

    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/diagnose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symptoms,
          userId,
        }),
      });
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error("诊断失败:", error);
      alert("诊断失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen home-bg">
      {/* 英雄区域 */}
      <section className="gradient-bg text-white header-banner mb-8">
        <div className="max-w-6xl mx-auto text-center">
          <div className="mb-6">
            <span className="inline-block px-5 py-2.5 bg-white/20 backdrop-blur-sm rounded-full text-sm font-medium">
              ✨ 医疗 AI 诊断溯源系统
            </span>
          </div>
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-4 leading-tight">
            MediTrace
          </h1>
          <p className="text-lg md:text-xl lg:text-2xl opacity-90 max-w-3xl mx-auto mb-4">
            结合大模型与 Web3 技术
          </p>
          <p className="text-base md:text-lg opacity-85 max-w-2xl mx-auto mb-8 leading-relaxed">
            为每一次 AI 诊断提供区块链级别的溯源保障，满足医疗合规审计需求
          </p>
        </div>
      </section>

      {/* 按钮区域 */}
      <section className="py-6 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-wrap justify-center gap-4">
            <a 
              href="#diagnose" 
              className="btn-primary px-8 py-3 text-lg inline-block"
            >
              开始诊断
            </a>
            <a 
              href="#features" 
              className="btn-secondary px-8 py-3 text-lg inline-block"
            >
              了解更多
            </a>
          </div>
        </div>
      </section>

      {/* 主要功能区域 */}
      <section id="diagnose" className="py-8 page-container">
        <div className="max-w-4xl mx-auto">
          {/* 诊断表单卡片 */}
          <div className="card-modern mb-8 fade-in">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-green-500 to-cyan-500 rounded-2xl mb-4">
                <span className="text-3xl">🏥</span>
              </div>
              <h2 className="text-3xl font-bold text-gray-800 mb-2">症状描述</h2>
              <p className="text-gray-600">请详细描述您的症状，AI 将为您提供专业诊断建议</p>
            </div>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  症状描述
                </label>
                <textarea
                  className="input-modern resize-none"
                  rows={5}
                  placeholder="请描述您的症状，例如：头痛、发烧持续 3 天、咳嗽伴有胸闷..."
                  value={symptoms}
                  onChange={(e) => setSymptoms(e.target.value)}
                />
              </div>
              
              {/* 用户地址设置 */}
              <div className="bg-gray-50 rounded-xl p-5 border border-gray-200">
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  用户地址 <span className="text-gray-400 font-normal">(用于区块链记录)</span>
                </label>
                <input
                  type="text"
                  className={`input-modern font-mono text-sm ${
                    addressError ? "border-red-400" : ""
                  }`}
                  placeholder="0x..."
                  value={userId}
                  onChange={handleAddressChange}
                />
                {addressError && (
                  <p className="text-sm text-red-600 mt-2 flex items-center">
                    <span className="mr-1">⚠️</span>
                    {addressError}
                  </p>
                )}
                <p className="text-xs text-gray-500 mt-2 flex items-center">
                  <span className="mr-1">💡</span>
                  生产环境建议集成 MetaMask 等钱包连接
                </p>
              </div>
              
              <button
                className="btn-primary w-full py-4 text-lg disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={handleDiagnose}
                disabled={loading || !symptoms.trim()}
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="spinner w-5 h-5 mr-2" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    诊断中，请稍候...
                  </span>
                ) : (
                  "获取诊断建议"
                )}
              </button>
            </div>
          </div>

          {/* 诊断结果 */}
          {result && (
            <div className="card-modern mb-12 fade-in">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-xl flex items-center justify-center">
                  <span className="text-2xl">📊</span>
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-800">诊断建议</h2>
                  <p className="text-sm text-gray-500">AI 分析结果</p>
                </div>
              </div>
              
              <div className="space-y-4 mb-6">
                {result.suggestions?.map((suggestion: any, index: number) => (
                  <div 
                    key={index} 
                    className="border-2 border-gray-100 rounded-xl p-5 hover:border-green-200 transition-colors"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <h3 className="text-lg font-semibold text-gray-800">{suggestion.disease}</h3>
                      <span className="badge badge-success">
                        置信度：{Math.round(suggestion.confidence * 100)}%
                      </span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-700 mb-2">建议检查：</p>
                      <ul className="space-y-1">
                        {suggestion.recommendations?.map((rec: string, i: number) => (
                          <li key={i} className="text-gray-600 text-sm flex items-start">
                            <span className="mr-2 text-green-500">✓</span>
                            {rec}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>

              {/* 免责声明 */}
              <div className="bg-amber-50 border-2 border-amber-200 rounded-xl p-5 mb-6">
                <p className="text-sm text-amber-800 flex items-start">
                  <span className="mr-2 text-xl">⚠️</span>
                  {result.disclaimer}
                </p>
              </div>

              {/* 溯源信息 */}
              {result.diagnosisId && (
                <div className="bg-gradient-to-r from-green-50 to-cyan-50 rounded-xl p-5 border-2 border-green-100">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-semibold text-gray-700">溯源信息</p>
                    {result.chainTxHash ? (
                      <span className="badge badge-success flex items-center gap-1">
                        <span>✓</span> 已上链
                      </span>
                    ) : (
                      <span className="badge badge-warning flex items-center gap-1">
                        <span>⏳</span> 待上链
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600">
                    诊断 ID: <code className="bg-white px-3 py-1 rounded-lg font-mono text-xs">{result.diagnosisId}</code>
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* 功能特性 */}
      <section id="features" className="py-8 page-container bg-transparent">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-800 mb-4">核心功能</h2>
            <p className="text-gray-600 max-w-2xl mx-auto px-4">
              结合前沿技术，为您提供专业、可信的医疗诊断服务
            </p>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8 md:gap-10">
            <div className="card-modern history-card-bg card-bottom-margin">
              <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-500 rounded-2xl flex items-center justify-center mb-6">
                <span className="text-3xl">🤖</span>
              </div>
              <h3 className="text-xl font-bold text-gray-800 mb-3">AI 智能诊断</h3>
              <p className="text-gray-600">
                基于 DeepSeek 大模型与医学知识库 RAG，提供专业、准确的诊断建议
              </p>
            </div>
            
            <div className="card-modern history-card-bg card-bottom-margin">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl flex items-center justify-center mb-6">
                <span className="text-3xl">⛓️</span>
              </div>
              <h3 className="text-xl font-bold text-gray-800 mb-3">区块链溯源</h3>
              <p className="text-gray-600">
                诊断记录上链存储，确保数据不可篡改，满足医疗合规审计需求
              </p>
            </div>
            
            <div className="card-modern history-card-bg card-bottom-margin">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center mb-6">
                <span className="text-3xl">🔒</span>
              </div>
              <h3 className="text-xl font-bold text-gray-800 mb-3">隐私保护</h3>
              <p className="text-gray-600">
                链上仅存储数据哈希，完整报告存于 IPFS，充分保护患者隐私
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 导航卡片 */}
      <section className="py-8 page-container">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-3 gap-6">
            <div className="card-modern text-center card-bottom-margin">
              <a
                href="/chat"
                className="group block"
              >
                <div className="w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-400 rounded-2xl flex items-center justify-center mb-4 mx-auto group-hover:scale-110 transition-transform">
                  <span className="text-4xl">💬</span>
                </div>
                <h3 className="text-xl font-bold text-gray-800 mb-2">多轮对话</h3>
                <p className="text-gray-600">
                  进行多轮深度诊断咨询
                </p>
              </a>
            </div>
            
            <div className="card-modern text-center card-bottom-margin">
              <a
                href="/history"
                className="group block"
              >
                <div className="w-20 h-20 bg-gradient-to-br from-orange-400 to-red-400 rounded-2xl flex items-center justify-center mb-4 mx-auto group-hover:scale-110 transition-transform">
                  <span className="text-4xl">📋</span>
                </div>
                <h3 className="text-xl font-bold text-gray-800 mb-2">历史记录</h3>
                <p className="text-gray-600">
                  查看您的诊断历史记录和溯源状态
                </p>
              </a>
            </div>
            
            <div className="card-modern text-center card-bottom-margin">
              <a
                href="/verify"
                className="group block"
              >
                <div className="w-20 h-20 bg-gradient-to-br from-indigo-400 to-purple-400 rounded-2xl flex items-center justify-center mb-4 mx-auto group-hover:scale-110 transition-transform">
                  <span className="text-4xl">🔍</span>
                </div>
                <h3 className="text-xl font-bold text-gray-800 mb-2">链上验证</h3>
                <p className="text-gray-600">
                  验证诊断记录的真实性与完整性
                </p>
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* 页脚 */}
      <footer className="bg-gray-800 text-white py-12 px-6">
        <div className="max-w-6xl mx-auto">
          <p className="text-gray-500 text-sm text-center" style={{ textAlign: "center" }}>
            © 2024 MediTrace. Built with Next.js, FastAPI & Blockchain
          </p>
        </div>
      </footer>
    </main>
  );
}
