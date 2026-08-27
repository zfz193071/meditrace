/**
 * 诊断结果卡片组件
 * 显示单次诊断的建议和溯源信息
 */

import { DiagnosisSuggestion } from "../lib/api";

interface DiagnosisResultCardProps {
  suggestion: DiagnosisSuggestion;
  index: number;
}

export default function DiagnosisResultCard({ suggestion, index }: DiagnosisResultCardProps) {
  return (
    <div
      className="bg-white rounded-2xl shadow-lg p-6 mb-4 hover:shadow-xl transition-shadow"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-800">{suggestion.disease}</h3>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
          置信度：{(suggestion.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <div className="mb-4">
        <h4 className="text-sm font-semibold text-gray-600 mb-2">建议检查项目:</h4>
        <div className="flex flex-wrap gap-2">
          {suggestion.recommendations.map((rec, idx) => (
            <span
              key={idx}
              className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-700"
            >
              {rec}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
