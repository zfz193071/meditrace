/**
 * 诊断表单组件
 * 用于输入症状和用户地址
 */

import { useState } from "react";

interface DiagnosisFormProps {
  onSubmit: (symptoms: string, userId: string) => Promise<void>;
  initialUserId?: string;
}

export default function DiagnosisForm({ onSubmit, initialUserId = "" }: DiagnosisFormProps) {
  const [symptoms, setSymptoms] = useState("");
  const [userId, setUserId] = useState(initialUserId);
  const [addressError, setAddressError] = useState("");
  const [loading, setLoading] = useState(false);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!symptoms.trim()) {
      alert("请输入症状描述");
      return;
    }

    if (!validateAddress(userId)) {
      return;
    }

    setLoading(true);
    try {
      await onSubmit(symptoms, userId);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-xl p-8">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">开始诊断</h2>

      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          您的症状描述 *
        </label>
        <textarea
          value={symptoms}
          onChange={(e) => setSymptoms(e.target.value)}
          placeholder="请详细描述您的症状，例如：头痛、发热、咳嗽持续了 3 天..."
          className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none transition-all"
          rows={4}
          maxLength={1000}
        />
        <p className="mt-1 text-xs text-gray-500 text-right">{symptoms.length}/1000</p>
      </div>

      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          钱包地址（可选）
        </label>
        <input
          type="text"
          value={userId}
          onChange={handleAddressChange}
          placeholder="0x..."
          className={`w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all ${
            addressError ? "border-red-500" : "border-gray-300"
          }`}
        />
        {addressError && (
          <p className="mt-2 text-sm text-red-600 flex items-center gap-1">
            <span>⚠️</span>
            {addressError}
          </p>
        )}
        <p className="mt-1 text-xs text-gray-500">
          用于将诊断记录关联到您的身份，格式：0x 后跟 40 个十六进制字符
        </p>
      </div>

      <button
        type="submit"
        disabled={loading || !symptoms.trim() || !!addressError}
        className={`w-full py-4 rounded-xl font-semibold text-lg transition-all ${
          loading || !symptoms.trim() || !!addressError
            ? "bg-gray-300 cursor-not-allowed"
            : "btn-primary hover:shadow-lg hover:-translate-y-0.5"
        }`}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            诊断中...
          </span>
        ) : (
          "开始诊断"
        )}
      </button>
    </form>
  );
}
