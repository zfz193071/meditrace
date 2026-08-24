"use client";

import { useState } from "react";

export default function Home() {
  const [symptoms, setSymptoms] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleDiagnose = async () => {
    if (!symptoms.trim()) return;

    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/diagnose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symptoms,
          userId: "0xTestUser123456789",
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
    <main className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        {/* 头部 */}
        <header className="text-center mb-12">
          <h1 className="text-4xl font-bold text-green-700 mb-4">MediTrace</h1>
          <p className="text-gray-600">
            医疗 AI 诊断溯源系统 - 结合大模型与 Web3 技术
          </p>
        </header>

        {/* 诊断表单 */}
        <section className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <h2 className="text-2xl font-semibold mb-4">症状描述</h2>
          <textarea
            className="w-full p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
            rows={4}
            placeholder="请描述您的症状，例如：头痛、发烧持续 3 天、咳嗽..."
            value={symptoms}
            onChange={(e) => setSymptoms(e.target.value)}
          />
          <button
            className="mt-4 w-full bg-green-600 text-white py-3 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
            onClick={handleDiagnose}
            disabled={loading || !symptoms.trim()}
          >
            {loading ? "诊断中..." : "获取诊断建议"}
          </button>
        </section>

        {/* 诊断结果 */}
        {result && (
          <section className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-2xl font-semibold mb-4">诊断建议</h2>
            
            <div className="space-y-4">
              {result.suggestions?.map((suggestion: any, index: number) => (
                <div key={index} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="text-lg font-medium">{suggestion.disease}</h3>
                    <span className="text-sm text-gray-500">
                      置信度：{Math.round(suggestion.confidence * 100)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-sm font-medium">建议检查：</span>
                    <ul className="list-disc list-inside text-gray-600">
                      {suggestion.recommendations?.map((rec: string, i: number) => (
                        <li key={i}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>

            {/* 免责声明 */}
            <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-sm text-yellow-800">{result.disclaimer}</p>
            </div>

            {/* 溯源信息 */}
            {result.diagnosisId && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600">
                  诊断 ID: <code className="bg-gray-200 px-2 py-1 rounded">{result.diagnosisId}</code>
                </p>
                <p className="text-sm text-gray-600 mt-2">
                  溯源状态：
                  {result.chainTxHash ? (
                    <span className="text-green-600">✓ 已上链</span>
                  ) : (
                    <span className="text-yellow-600">⏳ 待上链</span>
                  )}
                </p>
              </div>
            )}
          </section>
        )}

        {/* 功能说明 */}
        <section className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-4xl mb-4">🤖</div>
            <h3 className="font-semibold mb-2">AI 诊断</h3>
            <p className="text-sm text-gray-600">
              基于大模型的智能诊断建议
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-4xl mb-4">⛓️</div>
            <h3 className="font-semibold mb-2">区块链溯源</h3>
            <p className="text-sm text-gray-600">
              诊断记录上链，确保不可篡改
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-4xl mb-4">🔍</div>
            <h3 className="font-semibold mb-2">可验证</h3>
            <p className="text-sm text-gray-600">
              任何人都可验证诊断记录真实性
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
