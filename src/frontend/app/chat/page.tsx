"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Conversation,
  Message,
  createConversation,
  getConversations,
  sendMessage,
  sendMessageStream,
  deleteConversation,
  downloadBlob,
  updateConversation,
} from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import StatusBadge from "../../components/StatusBadge";
import MarkdownRenderer from "../../components/MarkdownRenderer";

export default function ConversationsPage() {
  // 添加自定义滚动动画样式
  if (typeof window !== 'undefined') {
    const styleId = 'conversation-scroll-animation';
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        @keyframes title-scroll-right-to-left {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(calc(-100% - 20px));
          }
        }
        .hover-scroll-title:hover h3 {
          animation: title-scroll-right-to-left 3s linear infinite;
        }
      `;
      document.head.appendChild(style);
    }
  }
  const router = useRouter();
  const searchParams = useSearchParams();
  const [userId, setUserId] = useState("0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [isAutoCreating, setIsAutoCreating] = useState(false); // 防止重复创建
  const [isAutoCreatedConversation, setIsAutoCreatedConversation] = useState(false); // 标记当前对话是否是自动创建的
  const [activeMenuConversationId, setActiveMenuConversationId] = useState<string | null>(null); // 当前打开的菜单
  const [renamingConversationId, setRenamingConversationId] = useState<string | null>(null); // 正在重命名的对话
  const [newTitle, setNewTitle] = useState(""); // 新标题
  const [scrollingTitles, setScrollingTitles] = useState<Set<string>>(new Set()); // 需要滚动的对话 ID 集合
  const [pageTitle, setPageTitle] = useState("新的对话"); // 页面动态标题
  const [urlConversationId, setUrlConversationId] = useState<string | null>(null); // URL 中的对话 ID
  const menuRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const previousMessageCountRef = useRef<number>(0);
  const isInitialMountRef = useRef<boolean>(true);
  const titleRefs = useRef<Record<string, HTMLDivElement | null>>({}); // 标题元素 refs

  // Ticket 01: 页面加载时自动创建新对话或加载 URL 指定的对话
  useEffect(() => {
    loadConversations();
    
    // 检查 URL 中是否有对话 ID
    const id = searchParams.get('id');
    if (id) {
      setUrlConversationId(id);
      // URL 有 ID 时，不自动创建新对话，而是等待加载完对话列表后查找并激活
    } else {
      // URL 无 ID 时，自动创建新对话
      autoCreateConversation();
    }
  }, [userId, searchParams]);

  // 提取公共的创建并激活对话逻辑
  const createAndActivateConversation = async (title: string = "新的诊断对话"): Promise<Conversation | null> => {
    try {
      const conversation = await createConversation({
        patientId: userId,
        title,
      });
      setConversations((prev) => [conversation, ...prev]);
      setActiveConversation(conversation);
      setPageTitle(title); // Ticket 01: 设置页面标题
      setIsAutoCreatedConversation(true); // 标记为自动创建的对话
      previousMessageCountRef.current = 0;
      return conversation;
    } catch (error) {
      console.error("创建对话失败:", error);
      alert("创建对话失败，请稍后重试");
      return null;
    }
  };

  // 自动创建对话函数
  const autoCreateConversation = async () => {
    // 只在首次挂载且没有激活对话时自动创建
    if (isAutoCreating || activeConversation || isInitialMountRef.current === false) {
      return;
    }
    
    setIsAutoCreating(true);
    try {
      const conversation = await createAndActivateConversation("新的诊断对话");
      if (!conversation) {
        // 创建失败，不显示错误提示，让用户手动创建
      }
    } catch (error) {
      console.error("自动创建对话失败:", error);
    } finally {
      setIsAutoCreating(false);
      isInitialMountRef.current = false;
    }
  };

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setActiveMenuConversationId(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ESC 键关闭菜单
  useEffect(() => {
    const handleEscKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActiveMenuConversationId(null);
        setRenamingConversationId(null);
      }
    };

    document.addEventListener('keydown', handleEscKey);
    return () => document.removeEventListener('keydown', handleEscKey);
  }, []);

  // 重命名对话函数
  const handleRenameConversation = async (conversationId: string, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
    }
    
    const conv = conversations.find(c => c.id === conversationId);
    if (!conv) return;
    
    setRenamingConversationId(conversationId);
    setNewTitle(conv.title);
    setActiveMenuConversationId(null);
  };

  // 确认重命名
  const confirmRename = async () => {
    if (!renamingConversationId || !newTitle.trim()) return;
    
    try {
      // 调用后端更新对话标题 API
      await fetch(`http://localhost:8000/api/conversations/${renamingConversationId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ title: newTitle.trim() }),
      });
      
      // 更新本地状态
      setConversations(conversations.map(c => 
        c.id === renamingConversationId ? { ...c, title: newTitle.trim() } : c
      ));
      
      if (activeConversation?.id === renamingConversationId) {
        setActiveConversation({ ...activeConversation, title: newTitle.trim() });
      }
    } catch (error) {
      console.error("重命名对话失败:", error);
      const errorMessage = error instanceof Error ? error.message : "重命名失败，请稍后重试";
      alert(errorMessage);
    } finally {
      setRenamingConversationId(null);
      setNewTitle("");
    }
  };

  // 回车确认重命名
  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      confirmRename();
    } else if (e.key === 'Escape') {
      setRenamingConversationId(null);
      setNewTitle("");
    }
  };

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
      setIsAutoCreatedConversation(false); // 从列表选择的对话不是自动创建的
      // Ticket 01: 更新页面标题
      setPageTitle(activeConversation.title);
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
    messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
  };

  // 检查标题是否需要滚动动画
  const checkTitleOverflow = () => {
    const titlesToScroll = new Set<string>();
    
    conversations.forEach((conv) => {
      const titleElement = titleRefs.current[conv.id];
      if (titleElement) {
        // 检查文本是否溢出容器
        if (titleElement.scrollWidth > titleElement.clientWidth) {
          titlesToScroll.add(conv.id);
        }
      }
    });
    
    setScrollingTitles(titlesToScroll);
  };

  // 监听对话列表变化，重新检查溢出
  useEffect(() => {
    if (conversations.length > 0) {
      setTimeout(() => checkTitleOverflow(), 0);
    }
  }, [conversations]);

  const loadConversations = async () => {
    setLoading(true);
    try {
      const conversationsList = await getConversations(userId);
      setConversations(conversationsList);
      
      // Ticket 01: 如果 URL 中有对话 ID，尝试加载该对话
      if (urlConversationId) {
        const targetConversation = conversationsList.find(c => c.id === urlConversationId);
        if (targetConversation) {
          setActiveConversation(targetConversation);
          setPageTitle(targetConversation.title);
          setIsAutoCreatedConversation(false);
          console.log(`成功加载 URL 指定的对话：${targetConversation.title}`);
        } else {
          console.warn(`对话 ID ${urlConversationId} 不存在，将创建新对话`);
          // 对话不存在，创建新对话
          await autoCreateConversation();
        }
      }
      
      // 延迟检查溢出，等待 DOM 更新
      setTimeout(() => checkTitleOverflow(), 0);
    } catch (error) {
      console.error("加载对话列表失败:", error);
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewConversation = async () => {
    await createAndActivateConversation("新的诊断对话");
  };

  // Ticket 02: 生成对话标题（基于用户第一条消息）
  const generateTitleFromMessage = (message: string): string => {
    // 取前 50 个字符
    const maxLength = 50;
    let title = message.trim();
    
    if (title.length > maxLength) {
      title = title.substring(0, maxLength);
      // 去除末尾的标点符号
      title = title.replace(/[，。！？,.!?;；:：\s]+$/, '');
      title = title + '...';
    } else {
      // 去除末尾的标点符号
      title = title.replace(/[，。！？,.!?;；:：\s]+$/, '');
    }
    
    return title || "新的诊断对话";
  };

  // Ticket 02: 更新对话标题
  const updateConversationTitle = async (conversationId: string, currentTitle: string) => {
    // 只有当标题是默认标题时才更新
    const defaultTitles = ["新的诊断对话", "新的对话", "MediTrace 对话", "有效提取用户的问题"];
    if (!defaultTitles.includes(currentTitle)) {
      console.log("对话已有自定义标题，跳过自动更新");
      return;
    }
    
    try {
      const newTitle = generateTitleFromMessage(currentTitle);
      await updateConversation(conversationId, newTitle);
      
      // 更新本地状态
      setConversations(prev => prev.map(c => 
        c.id === conversationId ? { ...c, title: newTitle } : c
      ));
      
      if (activeConversation?.id === conversationId) {
        setActiveConversation(prev => prev ? { ...prev, title: newTitle } : null);
        setPageTitle(newTitle);
      }
      
      console.log(`对话标题已更新：${newTitle}`);
    } catch (error) {
      console.error("更新对话标题失败:", error);
      // 标题更新失败不影响消息发送
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
      const hasPreviousMessages = activeConversation.messages && activeConversation.messages.length > 0;
      
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

      // Ticket 02: 如果是第一条消息，更新对话标题
      if (!hasPreviousMessages) {
        await updateConversationTitle(activeConversation.id, activeConversation.title);
      }
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
                  onClick={() => {
                    setActiveConversation(conv);
                    setActiveMenuConversationId(null); // 关闭菜单
                  }}
                  className={`group cursor-pointer transition-colors relative ${
                    activeConversation?.id === conv.id ? "bg-green-50" : "hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-center justify-between px-4 py-3 overflow-hidden">
                    {/* 左侧：对话标题 - 支持滚动 */}
                    <div 
                      className="flex-1 overflow-hidden mr-2"
                      ref={(el) => {
                        titleRefs.current[conv.id] = el;
                      }}
                    >
                      {/* 重命名输入框 */}
                      {renamingConversationId === conv.id ? (
                        <input
                          type="text"
                          value={newTitle}
                          onChange={(e) => setNewTitle(e.target.value)}
                          onKeyDown={handleRenameKeyDown}
                          onBlur={confirmRename}
                          autoFocus
                          className="font-semibold text-gray-800 w-full px-2 py-1 border border-green-500 rounded focus:outline-none"
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <h3 
                          className={`font-semibold text-gray-800 whitespace-nowrap ${
                            scrollingTitles.has(conv.id) ? 'hover-scroll-title' : ''
                          }`}
                        >
                          {conv.title}
                        </h3>
                      )}
                    </div>
                    {/* 右侧：三点菜单按钮 */}
                    <div className="flex items-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenuConversationId(
                            activeMenuConversationId === conv.id ? null : conv.id
                          );
                        }}
                        className="text-gray-400 hover:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        ···
                      </button>
                    </div>
                  </div>
                  
                  {/* 三点菜单弹框 - Ticket 05 */}
                  {activeMenuConversationId === conv.id && (
                    <div
                      ref={menuRef}
                      className="absolute right-2 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 overflow-hidden"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={(e) => handleRenameConversation(conv.id, e)}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 transition-colors"
                      >
                        重命名
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteConversation(conv.id, e);
                        }}
                        className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 transition-colors border-t"
                      >
                        删除
                      </button>
                    </div>
                  )}
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
          
          {/* 页面标题 - Ticket 01: 动态标题展示 */}
          <div className="flex-1">
            <h1 className="text-xl font-bold">
              {pageTitle}
            </h1>
          </div>
        </header>

        {/* 聊天内容区域 */}
        {activeConversation ? (
          <>
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
