/**
 * 前端 API 客户端
 * 封装所有与后端 API 的交互
 */

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

/**
 * 诊断 API 请求参数
 */
export interface DiagnoseRequest {
  symptoms: string;
  userId: string;
}

/**
 * 诊断建议
 */
export interface DiagnosisSuggestion {
  disease: string;
  confidence: number;
  recommendations: string[];
}

/**
 * 诊断 API 响应
 */
export interface DiagnoseResponse {
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
 * 历史记录 API 响应
 */
export interface HistoryResponse {
  records: HistoryRecord[];
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
 * 验证 API 响应
 */
export interface VerifyResponse {
  isValid: boolean;
  chainRecord: ChainRecord | null;
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
 * 创建对话请求
 */
export interface CreateConversationRequest {
  userId: string;
  title: string;
}

/**
 * 发送消息请求
 */
export interface SendMessageRequest {
  conversationId: string;
  message: string;
}

/**
 * 通用 API 错误
 */
export interface ApiError {
  detail: string;
}

/**
 * 处理 API 响应
 * @param response Fetch 响应对象
 * @returns JSON 数据
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: "未知错误" }));
    throw new Error(error.detail || `API 请求失败：${response.status}`);
  }
  return response.json();
}

/**
 * 执行诊断
 * @param request 诊断请求
 * @returns 诊断结果
 */
export async function diagnose(request: DiagnoseRequest): Promise<DiagnoseResponse> {
  const response = await fetch(`${BASE_URL}/api/diagnose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse<DiagnoseResponse>(response);
}

/**
 * 获取用户历史记录
 * @param userId 用户 ID（钱包地址）
 * @returns 历史记录列表
 */
export async function getHistory(userId: string): Promise<HistoryResponse> {
  const response = await fetch(`${BASE_URL}/api/history/${userId}`);
  return handleResponse<HistoryResponse>(response);
}

/**
 * 验证诊断记录
 * @param diagnosisId 诊断 ID
 * @returns 验证结果
 */
export async function verify(diagnosisId: string): Promise<VerifyResponse> {
  const response = await fetch(`${BASE_URL}/api/verify/${diagnosisId}`);
  return handleResponse<VerifyResponse>(response);
}

/**
 * 下载报告
 * @param diagnosisId 诊断 ID
 * @returns Blob 对象（PDF 文件）
 */
export async function downloadReport(diagnosisId: string): Promise<Blob> {
  const response = await fetch(`${BASE_URL}/api/report/${diagnosisId}`);
  if (!response.ok) {
    throw new Error(`下载报告失败：${response.status}`);
  }
  return response.blob();
}

/**
 * 获取 IPFS 报告
 * @param cid IPFS CID
 * @returns Blob 对象（PDF 文件）
 */
export async function fetchIpfsReport(cid: string): Promise<Blob> {
  // 使用公共 IPFS 网关
  const ipfsUrl = `https://ipfs.io/ipfs/${cid}`;
  const response = await fetch(ipfsUrl);
  if (!response.ok) {
    throw new Error(`获取 IPFS 报告失败：${response.status}`);
  }
  return response.blob();
}

/**
 * 创建新对话
 * @param request 创建对话请求
 * @returns 创建的对话
 */
export async function createConversation(request: CreateConversationRequest): Promise<Conversation> {
  const response = await fetch(`${BASE_URL}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse<Conversation>(response);
}

/**
 * 获取用户的所有对话
 * @param userId 用户 ID
 * @returns 对话列表
 */
export async function getConversations(userId: string): Promise<Conversation[]> {
  const response = await fetch(`${BASE_URL}/api/conversations?userId=${userId}`);
  return handleResponse<Conversation[]>(response);
}

/**
 * 获取单个对话
 * @param conversationId 对话 ID
 * @returns 对话详情
 */
export async function getConversation(conversationId: string): Promise<Conversation> {
  const response = await fetch(`${BASE_URL}/api/conversations/${conversationId}`);
  return handleResponse<Conversation>(response);
}

/**
 * 发送消息响应
 */
export interface SendMessageResponse {
  messageId: string;
  content: string;
  context: string[];
  followUpQuestions: string[];
  diagnosisResult: any;
}

/**
 * 流式消息 chunk
 */
export interface StreamMessageChunk {
  content: string;
  complete: boolean;
  error?: string;
}

/**
 * 发送消息到对话（普通请求）
 * @param request 发送消息请求
 * @returns AI 回复消息
 */
export async function sendMessage(request: SendMessageRequest): Promise<SendMessageResponse> {
  const response = await fetch(`${BASE_URL}/api/conversations/${request.conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: request.message }),
  });
  return handleResponse<SendMessageResponse>(response);
}

/**
 * 发送消息到对话（流式请求）
 * @param request 发送消息请求
 * @param onChunk 每个 chunk 的回调
 * @returns 完整的 AI 回复内容
 */
export async function sendMessageStream(
  request: SendMessageRequest,
  onChunk: (chunk: StreamMessageChunk) => void
): Promise<string> {
  const response = await fetch(`${BASE_URL}/api/conversations/${request.conversationId}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: request.message }),
  });

  if (!response.ok) {
    throw new Error(`API 请求失败：${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("无法获取响应流");
  }

  const decoder = new TextDecoder();
  let fullContent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split("\n");

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data === "[DONE]") continue;

        try {
          const parsed: StreamMessageChunk = JSON.parse(data);
          fullContent += parsed.content;
          onChunk(parsed);

          if (parsed.error) {
            throw new Error(parsed.error);
          }

          if (parsed.complete) {
            return fullContent;
          }
        } catch (e) {
          console.error("解析流式数据失败:", e);
        }
      }
    }
  }

  return fullContent;
}

/**
 * 删除对话
 * @param conversationId 对话 ID
 */
export async function deleteConversation(conversationId: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/conversations/${conversationId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`删除对话失败：${response.status}`);
  }
}

/**
 * 下载 Blob 为文件
 * @param blob Blob 对象
 * @param filename 文件名
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
