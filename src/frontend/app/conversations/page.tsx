"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Conversation,
  Message,
  createConversation,
  getConversations,
  sendMessage,
  sendMessageStream,
  deleteConversation,
  downloadBlob,
} from "../../lib/api";
import Header from "../../components/Header";
import LoadingSpinner from "../../components/LoadingSpinner";
import StatusBadge from "../../components/StatusBadge";
import MarkdownRenderer from "../../components/MarkdownRenderer";

export default function ConversationsPage() {
  const router = useRouter();
  const [userId, setUserId] = useState("0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [showNewConversation, setShowNewConversation] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadConversations();
  }, [userId]);

  useEffect(() => {
    scrollToBottom();
  }, [activeConversation?.messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadConversations = async () => {
    setLoading(true);
    try {
      const conversationsList = await getConversations(userId);
      setConversations(conversationsList);
    } catch (error) {
      console.error("加载对话列表失败:", error);
      // API 可能还不存在，设置为空数组
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateConversation = async () => {
    if (!newTitle.trim()) {
      alert("请输入对话标题");
      return;
    }

    try {
      const conversation = await createConversation({
        patientId: userId,
        title: newTitle,
      });
      setConversations([conversation, ...conversations]);
      setActiveConversation(conversation);
      setShowNewConversation(false);
      setNewTitle("");
    } catch (error) {
      console.error("创建对话失败:", error);
      alert("创建对话失败，请稍后重试");
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !activeConversation) return;

    setSending(true);
    try {
      // 先添加用户消息到本地状态（乐观更新）
      const userMessage: Message = {
        role: "user",
        content: newMessage,
        timestamp: Date.now(),
      };

      const updatedMessages = [...(activeConversation.messages || []), userMessage];
      setActiveConversation({
        ...activeConversation,
        messages: updatedMessages,
      });
      setNewMessage("");

      // 创建 AI 消息占位符
      const aiMessageIndex = updatedMessages.length;
      const aiMessage: Message = {
        role: "assistant",
        content: "", // 初始为空，流式填充
        timestamp: Date.now(),
      };

      setActiveConversation({
        ...activeConversation,
        messages: [...updatedMessages, aiMessage],
      });

      // 流式发送消息
      await sendMessageStream(
        {
          conversationId: activeConversation.id,
          message: newMessage,
        },
        (chunk) => {
          // 使用 setTimeout 确保每个 chunk 都能触发 UI 更新
          // 避免 React 批量更新导致的显示延迟
          setTimeout(() => {
            // 更新 AI 消息内容
            setActiveConversation((prev) => {
              if (!prev) return prev;
              const messages = [...prev.messages];
              if (messages[aiMessageIndex]) {
                messages[aiMessageIndex] = {
                  ...messages[aiMessageIndex],
                  content: messages[aiMessageIndex].content + chunk.content,
                };
              }
              return {
                ...prev,
                messages,
              };
            });
            
            // 滚动到底部
            scrollToBottom();
          }, 0);
        }
      );
    } catch (error) {
      console.error("发送消息失败:", error);
      alert("发送消息失败，请稍后重试");
      // 失败时重新加载对话列表
      loadConversations();
    } finally {
      setSending(false);
    }
  };

  const handleDeleteConversation = async (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("确定要删除这个对话吗？")) return;

    try {
      await deleteConversation(conversationId);
      setConversations(conversations.filter((c) => c.id !== conversationId));
      if (activeConversation?.id === conversationId) {
        setActiveConversation(null);
      }
    } catch (error) {
      console.error("删除对话失败:", error);
      alert("删除对话失败，请稍后重试");
    }
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleDateString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
    });
  };

  return (
    <main className="min-h-screen home-bg">
      <Header
        title="对话历史"
        subtitle="管理您的多轮诊断对话"
        onBack={() => router.push("/")}
      />

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex gap-6 h-[calc(100vh-280px)]">
          {/* 对话列表 */}
          <div className="w-80 bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col">
            <div className="p-4 border-b">
              <button
                onClick={() => setShowNewConversation(!showNewConversation)}
                className="w-full btn-primary py-3 rounded-xl font-semibold"
              >
                + 新建对话
              </button>
            </div>

            {showNewConversation && (
              <div className="p-4 border-b bg-gray-50">
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="输入对话标题..."
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg mb-2"
                  onKeyDown={(e) => e.key === "Enter" && handleCreateConversation()}
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleCreateConversation}
                    className="flex-1 bg-green-500 text-white py-2 rounded-lg text-sm"
                  >
                    创建
                  </button>
                  <button
                    onClick={() => setShowNewConversation(false)}
                    className="flex-1 bg-gray-200 text-gray-700 py-2 rounded-lg text-sm"
                  >
                    取消
                  </button>
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <LoadingSpinner />
                </div>
              ) : conversations.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <p className="text-lg mb-2">📭</p>
                  <p>暂无对话记录</p>
                  <p className="text-sm mt-2">点击"新建对话"开始咨询</p>
                </div>
              ) : (
                <div className="divide-y">
                  {conversations.map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => setActiveConversation(conv)}
                      className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
                        activeConversation?.id === conv.id ? "bg-green-50" : ""
                      }`}
                    >
                      <div className="flex items-start justify-between mb-1">
                        <h3 className="font-semibold text-gray-800 truncate flex-1">
                          {conv.title}
                        </h3>
                        <button
                          onClick={(e) => handleDeleteConversation(conv.id, e)}
                          className="ml-2 text-gray-400 hover:text-red-500"
                        >
                          ✕
                        </button>
                      </div>
                      <p className="text-sm text-gray-500 truncate">
                        {conv.messages?.[conv.messages.length - 1]?.content || "暂无消息"}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        {formatDate(conv.updatedAt)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 聊天区域 */}
          <div className="flex-1 bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden">
            {activeConversation ? (
              <>
                {/* 聊天头部 */}
                <div className="p-4 border-b bg-gray-50">
                  <h2 className="text-xl font-bold">{activeConversation.title}</h2>
                  <p className="text-sm text-gray-500">
                    {activeConversation.messages?.length || 0} 条消息
                  </p>
                </div>

                {/* 消息列表 */}
                <div className="flex-1 overflow-y-auto p-6">
                  {activeConversation.messages?.map((msg, idx) => {
                    const isLastMessage = idx === (activeConversation.messages?.length || 0) - 1;
                    const isAiStreaming = msg.role === "assistant" && isLastMessage && sending;
                    
                    return (
                      <div
                        key={idx}
                        className={`mb-4 flex ${
                          msg.role === "user" ? "justify-end" : "justify-start"
                        }`}
                      >
                        <div
                          className={`max-w-[70%] rounded-2xl px-4 py-3 ${
                            msg.role === "user"
                              ? "bg-green-500 text-white"
                              : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"
                          }`}
                        >
                          {/* 消息内容 */}
                          <div className={`text-sm ${msg.role === "user" ? "" : "markdown-container"}`}>
                            {msg.role === "assistant" ? (
                              // AI 消息使用 Markdown 渲染器
                              <MarkdownRenderer
                                content={msg.content}
                                streaming={isAiStreaming}
                                className="prose prose-sm max-w-none"
                              />
                            ) : (
                              // 用户消息普通显示
                              <p className="whitespace-pre-wrap">{msg.content}</p>
                            )}
                          </div>
                          
                          {/* 时间戳 */}
                          <p
                            className={`text-xs mt-2 ${
                              msg.role === "user" ? "text-green-100" : "text-gray-500 dark:text-gray-400"
                            }`}
                          >
                            {formatTime(msg.timestamp)}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </div>

                {/* 输入区域 */}
                <div className="p-4 border-t">
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && !sending && handleSendMessage()}
                      placeholder="输入您的问题..."
                      className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-transparent"
                      disabled={sending}
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={sending || !newMessage.trim()}
                      className={`px-6 py-3 rounded-xl font-semibold transition-all ${
                        sending || !newMessage.trim()
                          ? "bg-gray-300 cursor-not-allowed"
                          : "btn-primary"
                      }`}
                    >
                      {sending ? "发送中..." : "发送"}
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <p className="text-6xl mb-4">💬</p>
                  <p className="text-xl font-semibold mb-2">选择一个对话</p>
                  <p className="text-sm">或创建新的诊断对话</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
