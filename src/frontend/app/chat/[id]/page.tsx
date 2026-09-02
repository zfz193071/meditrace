"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Conversation,
  Message,
  getConversation,
  sendMessage,
  sendMessageStream,
} from "@/lib/api";
import LoadingSpinner from "@/components/LoadingSpinner";
import MarkdownRenderer from "@/components/MarkdownRenderer";

/**
 * 动态路由对话页面
 * 支持通过 URL 访问特定对话：/chat/{conversationId}
 */
export default function ConversationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = params.id as string;

  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载对话
  useEffect(() => {
    if (!conversationId) return;

    const loadConversation = async () => {
      try {
        setLoading(true);
        const conv = await getConversation(conversationId);
        setConversation(conv);
      } catch (error) {
        console.error("加载对话失败:", error);
        alert("对话不存在或加载失败");
        router.push("/chat");
      } finally {
        setLoading(false);
      }
    };

    loadConversation();
  }, [conversationId, router]);

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
  };

  // 消息变化时滚动
  useEffect(() => {
    if (conversation?.messages) {
      scrollToBottom();
    }
  }, [conversation?.messages?.length]);

  // 发送消息
  const handleSendMessage = async () => {
    if (!newMessage.trim() || !conversation) return;

    setSending(true);
    try {
      const userMessage: Message = {
        role: "user",
        content: newMessage,
        timestamp: Date.now(),
      };

      const updatedMessages = [...(conversation.messages || []), userMessage];

      setConversation({
        ...conversation,
        messages: updatedMessages,
      });
      setNewMessage("");

      const aiMessageIndex = updatedMessages.length;
      const aiMessage: Message = {
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };

      setConversation({
        ...conversation,
        messages: [...updatedMessages, aiMessage],
      });

      await sendMessageStream(
        {
          conversationId: conversation.id,
          message: newMessage,
        },
        (chunk) => {
          setTimeout(() => {
            setConversation((prev) => {
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
          }, 0);
        }
      );
    } catch (error) {
      console.error("发送消息失败:", error);
      alert("发送消息失败，请稍后重试");
    } finally {
      setSending(false);
    }
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <main className="h-screen flex items-center justify-center home-bg">
        <LoadingSpinner />
      </main>
    );
  }

  if (!conversation) {
    return (
      <main className="h-screen flex items-center justify-center home-bg">
        <div className="text-center">
          <p className="text-6xl mb-4">❌</p>
          <p className="text-xl font-semibold mb-2">对话不存在</p>
          <button
            onClick={() => router.push("/chat")}
            className="btn-primary px-6 py-3 rounded-xl"
          >
            返回对话列表
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="h-screen flex home-bg overflow-hidden">
      {/* 右侧主区域 - 聊天 */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* 聊天顶部导航栏 */}
        <header className="p-4 border-b bg-white flex items-center gap-2 flex-shrink-0">
          {/* 返回按钮 */}
          <button
            onClick={() => router.push("/chat")}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="返回对话列表"
          >
            ←
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
            <h1 className="text-xl font-bold">
              {conversation.title}
            </h1>
          </div>
        </header>

        {/* 聊天内容区域 */}
        <>
          {/* 消息列表 */}
          <div 
            className="flex-1 overflow-y-auto p-6"
          >
            {conversation.messages?.map((msg, idx) => {
              const isLastMessage = idx === (conversation.messages?.length || 0) - 1;
              const isAiStreaming = msg.role === "assistant" && isLastMessage && sending;
              
              return (
                <div
                  key={idx}
                  className={`mb-4 flex ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`rounded-2xl px-4 py-3 max-w-[85%] ${
                      msg.role === "user"
                        ? "bg-green-500 text-white"
                        : "bg-transparent text-gray-800 dark:text-gray-100"
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
      </main>
    </main>
  );
}
