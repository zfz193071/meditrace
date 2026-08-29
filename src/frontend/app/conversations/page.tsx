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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const previousMessageCountRef = useRef<number>(0);
  const isInitialMountRef = useRef<boolean>(true);

  useEffect(() => {
    loadConversations();
  }, [userId]);

  // 只在发送新消息时自动滚动，切换会话时不滚动
  useEffect(() => {
    // 首次渲染或切换会话时不滚动
    if (isInitialMountRef.current) {
      isInitialMountRef.current = false;
      previousMessageCountRef.current = activeConversation?.messages?.length || 0;
      return;
    }

    // 只有当消息数量增加时才滚动（新消息到达）
    const currentCount = activeConversation?.messages?.length || 0;
    if (currentCount > previousMessageCountRef.current) {
      scrollToBottom();
    }
    previousMessageCountRef.current = currentCount;
  }, [activeConversation?.messages?.length]);

  // 修复：切换会话时重置状态
  useEffect(() => {
    if (activeConversation) {
      // 切换会话时重置初始标记，但不触发滚动
      previousMessageCountRef.current = activeConversation.messages?.length || 0;
    }
  }, [activeConversation?.id]);

  // 响应式检测
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) {
        setSidebarCollapsed(true); // 移动端默认折叠
      }
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

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
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewConversation = async () => {
    try {
      const conversation = await createConversation({
        patientId: userId,
        title: "新的诊断对话",
      });
      setConversations([conversation, ...conversations]);
      setActiveConversation(conversation);
      previousMessageCountRef.current = 0;
    } catch (error) {
      console.error("创建对话失败:", error);
      alert("创建对话失败，请稍后重试");
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !activeConversation) return;

    setSending(true);
    try {
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

      const aiMessageIndex = updatedMessages.length;
      const aiMessage: Message = {
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };

      setActiveConversation({
        ...activeConversation,
        messages: [...updatedMessages, aiMessage],
      });

      await sendMessageStream(
        {
          conversationId: activeConversation.id,
          message: newMessage,
        },
        (chunk) => {
          setTimeout(() => {
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
            // 修复：流式更新时不主动滚动，让消息数量变化 useEffect 处理
          }, 0);
        }
      );
    } catch (error) {
      console.error("发送消息失败:", error);
      alert("发送消息失败，请稍后重试");
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

  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  return (
    <main className="h-screen flex home-bg overflow-hidden">
      {/* 移动端遮罩层 - 点击关闭侧栏 */}
      {isMobile && !sidebarCollapsed && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setSidebarCollapsed(true)}
        />
      )}

      {/* 左侧侧栏 - 会话列表 */}
      <aside 
        className={`bg-white border-r flex flex-col transition-all duration-300 ease-in-out ${
          sidebarCollapsed ? 'w-0' : 'w-80'
        } ${isMobile ? 'fixed inset-y-0 left-0 z-50 shadow-2xl' : ''}`}
      >
        {/* 侧栏头部 */}
        <div className="p-4 border-b flex-shrink-0">
          <button
            onClick={handleNewConversation}
            className="w-full btn-primary py-3 rounded-xl font-semibold"
          >
            + 新建对话
          </button>
        </div>

        {/* 会话列表 */}
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
      </aside>

      {/* 右侧主区域 - 聊天 */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* 聊天顶部导航栏 */}
        <header className="p-4 border-b bg-white flex items-center gap-2 flex-shrink-0">
          {/* 侧栏折叠/展开按钮 */}
          <button
            onClick={toggleSidebar}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title={sidebarCollapsed ? "展开侧栏" : "折叠侧栏"}
          >
            {sidebarCollapsed ? '▶' : '◀'}
          </button>
          
          {/* 返回主页按钮 */}
          <button
            onClick={() => router.push("/")}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="返回主页"
          >
            🏠
          </button>
          
          {/* 页面标题 */}
          <div className="flex-1">
            <h1 className="text-xl font-bold">MediTrace 对话</h1>
          </div>
        </header>

        {/* 聊天内容区域 */}
        {activeConversation ? (
          <>
            {/* 聊天头部 */}
            <div className="p-4 border-b bg-gray-50 flex-shrink-0">
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
                          <MarkdownRenderer
                            content={msg.content}
                            streaming={isAiStreaming}
                            className="prose prose-sm max-w-none"
                          />
                        ) : (
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
            <div className="p-4 border-t bg-white flex-shrink-0">
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
      </main>
    </main>
  );
}
