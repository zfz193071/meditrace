/**
 * 前端 TypeScript 类型定义
 * 统一的数据模型和接口类型
 */

/**
 * 诊断建议
 */
export interface DiagnosisSuggestion {
  disease: string;
  confidence: number; // 0-1
  recommendations: string[];
}

/**
 * 诊断结果
 */
export interface DiagnosisResult {
  diagnosisId: string;
  suggestions: DiagnosisSuggestion[];
  disclaimer: string;
  ipfsCid?: string;
  chainTxHash?: string;
}

/**
 * 历史记录记录
 */
export interface HistoryRecord {
  diagnosisId: string;
  timestamp: number;
  diseaseTypes: string[];
  chainStatus: "pending" | "confirmed" | "failed";
  ipfsCid?: string;
}

/**
 * 链上记录
 */
export interface ChainRecord {
  dataHash: string;
  modelVersion: string;
  timestamp: number;
  patient: string;
  ipfsCid: string;
}

/**
 * 验证结果
 */
export interface VerificationResult {
  isValid: boolean;
  chainRecord?: ChainRecord;
  ipfsCid: string;
}

/**
 * 对话消息
 */
export interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

/**
 * 对话
 */
export interface Conversation {
  id: string;
  userId: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

/**
 * 对话状态
 */
export type ConversationStatus = "active" | "archived" | "deleted";

/**
 * 页面加载状态
 */
export type LoadingState = "idle" | "loading" | "success" | "error";

/**
 * API 错误
 */
export interface ApiError {
  detail: string;
}

/**
 * 分页参数
 */
export interface PaginationParams {
  page: number;
  limit: number;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

/**
 * 分页响应
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

/**
 * 用户信息
 */
export interface User {
  address: string;
  createdAt?: number;
  lastActiveAt?: number;
}

/**
 * 系统配置
 */
export interface SystemConfig {
  backendUrl: string;
  ipfsGateway: string;
  blockchainExplorerUrl: string;
  maxSymptomsLength: number;
  defaultPaginationLimit: number;
}

/**
 * 表单验证错误
 */
export interface ValidationError {
  field: string;
  message: string;
}

/**
 * 通知消息
 */
export interface Notification {
  id: string;
  type: "success" | "error" | "warning" | "info";
  message: string;
  timestamp: number;
  read: boolean;
}
