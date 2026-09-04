"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  Conversation,
  Message,
  createConversation,
  getConversations,
  getConversation,
  sendMessage,
  sendMessageStream,
  deleteConversation,
  downloadBlob,
  updateConversation,
  replaceConversationUrl,
} from "@/lib/api";
import LoadingSpinner from "@/components/LoadingSpinner";
import StatusBadge from "@/components/StatusBadge";
import MarkdownRenderer from "@/components/MarkdownRenderer";

export default function ConversationsPage() {
  // 添加自定义滚动动画样式 - Ticket 04
  if (typeof window !== "undefined") {
    const styleId = "conversation-scroll-animation";
    if (!document.getElementById(styleId)) {
      const style = document.createElement("style");
      style.id = styleId;
      style.textContent = `
        @keyframes title-scroll-right-to-left {
          0% {
            transform: translateX(100%);
          }
          85% {
            transform: translateX(calc(-100% - 20px));
          }
          100% {
            transform: translateX(calc(-100% - 20px));
          }
        }
        .hover-scroll-title h3 {
          animation: title-scroll-right-to-left 5s linear infinite;
          animation-play-state: paused;
        }
        .hover-scroll-title:hover h3 {
          animation-play-state: running;
        }
      `;
      document.head.appendChild(style);
    }
  }
  const router = useRouter();
  const params = useParams();
  const [userId, setUserId] = useState(
    "0x262Ee58D3e7A782ceC68094A6DACb53D02Fa9d0B"
  );
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeConversation, setActiveConversation] =
    useState<Conversation | null>(null);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [isAutoCreating, setIsAutoCreating] = useState(false); // 防止重复创建
  const [isTempConversation, setIsTempConversation] = useState(false); // 标记当前对话是否为临时会话
  const [activeMenuConversationId, setActiveMenuConversationId] = useState<
    string | null
  >(null); // 当前打开的菜单
  const [renamingConversationId, setRenamingConversationId] = useState<
    string | null
  >(null); // 正在重命名的对话
  const [newTitle, setNewTitle] = useState(""); // 新标题
  const [scrollingTitles, setScrollingTitles] = useState<Set<string>>(
    new Set()
  ); // 需要滚动的对话 ID 集合
  const [pageTitle, setPageTitle] = useState(""); // 页面动态标题，初始为空
  const [urlConversationId, setUrlConversationId] = useState<string | null>(
    null
  ); // URL 中的对话 ID
  const [hasGeneratedTitle, setHasGeneratedTitle] = useState(false); // 标记是否已生成标题
  const titleGenerationRef = useRef<boolean>(false); // 防止重复生成标题的 ref
  const menuRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const previousMessageCountRef = useRef<number>(0);
  const isInitialMountRef = useRef<boolean>(true);
  const titleRefs = useRef<Record<string, HTMLDivElement | null>>({}); // 标题元素 refs
  const shouldAutoScrollRef = useRef<boolean>(true); // Ticket 06: 追踪是否应该自动滚动

  // Ticket 01: 页面加载时自动创建新对话或加载 URL 指定的对话
  // 使用 ref 来追踪是否由用户点击触发的会话切换，避免 useEffect 重复执行
  const isUserSwitchingRef = useRef<boolean>(false);
  // 追踪最后加载的对话 ID，防止重复加载
  const lastLoadedConversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    console.log(
      `[useEffect 1] 触发 - params.id: ${params.id}, urlConversationId: ${urlConversationId}, isUserSwitchingRef: ${isUserSwitchingRef.current}`
    );

    // 检查 URL 中是否有对话 ID（动态路由 /chat/{id}）
    const id = params.id as string;

    // 如果是用户点击切换会话，跳过自动加载逻辑
    if (isUserSwitchingRef.current) {
      console.log(`[跳过加载] 用户正在切换会话，跳过自动加载`);
      isUserSwitchingRef.current = false;
      return;
    }

    // 如果已经加载过该对话 ID，跳过重复加载
    if (id && id === lastLoadedConversationIdRef.current) {
      console.log(`[跳过加载] 对话 ${id} 已加载过，跳过`);
      return;
    }

    // 当 URL 中的对话 ID 变化时，需要重新加载并激活该对话
    if (id && id !== urlConversationId) {
      console.log(
        `[URL 变化] URL 中的对话 ID 从 ${urlConversationId} 变为 ${id}`
      );
      setUrlConversationId(id);
      // URL 有 ID 时，加载对话列表后查找并激活
      loadConversations(id);
      // 更新最后加载的对话 ID
      lastLoadedConversationIdRef.current = id;
    } else if (!id) {
      // URL 无 ID 时，加载对话列表并自动创建新对话
      console.log(
        `[无 URL ID] 调用 loadConversations() 和 autoCreateConversation()`
      );
      loadConversations();
      autoCreateConversation();
    } else {
      console.log(
        `[无变化] id=${id}, urlConversationId=${urlConversationId}, 无变化`
      );
    }
  }, [userId, params.id, urlConversationId]);

  // 提取公共的创建并激活对话逻辑（临时会话）
  const createAndActivateTempConversation = async (
    title: string = "新的诊断对话"
  ): Promise<void> => {
    console.log(
      `[createAndActivateTempConversation] 创建临时对话 - title: ${title}`
    );
    // 创建一个临时的 conversation 对象（不持久化到数据库）
    const tempConversation: Conversation = {
      id: `temp-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
      patientId: userId,
      title,
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
    };

    setActiveConversation(tempConversation);
    setPageTitle(title);
    setIsTempConversation(true); // 标记为临时会话
    previousMessageCountRef.current = 0;
    console.log(
      `[createAndActivateTempConversation] 临时对话创建完成 - id: ${tempConversation.id}`
    );
  };

  // 提取公共的创建并激活正式对话逻辑
  const createAndActivateConversation = async (
    title: string = "新的诊断对话"
  ): Promise<Conversation | null> => {
    try {
      const conversation = await createConversation({
        patientId: userId,
        title,
      });
      setConversations((prev) => [conversation, ...prev]);
      setActiveConversation(conversation);
      setPageTitle(title);
      setIsTempConversation(false); // 标记为正式会话
      previousMessageCountRef.current = 0;
      return conversation;
    } catch (error) {
      console.error("创建对话失败:", error);
      alert("创建对话失败，请稍后重试");
      return null;
    }
  };

  // 自动创建临时对话函数
  const autoCreateConversation = async () => {
    console.log(
      `[autoCreateConversation] 开始执行 - isAutoCreating: ${isAutoCreating}, activeConversation: ${
        activeConversation?.id || "null"
      }, isInitialMountRef: ${isInitialMountRef.current}`
    );
    // 只在首次挂载且没有激活对话时自动创建
    if (
      isAutoCreating ||
      activeConversation ||
      isInitialMountRef.current === false
    ) {
      console.log(`[autoCreateConversation] 跳过 - 条件不满足`);
      return;
    }

    setIsAutoCreating(true);
    try {
      await createAndActivateTempConversation("新的诊断对话");
    } catch (error) {
      console.error("自动创建临时对话失败:", error);
    } finally {
      setIsAutoCreating(false);
      isInitialMountRef.current = false;
      console.log(`[autoCreateConversation] 完成`);
    }
  };

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setActiveMenuConversationId(null);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ESC 键关闭菜单
  useEffect(() => {
    const handleEscKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setActiveMenuConversationId(null);
        setRenamingConversationId(null);
      }
    };

    document.addEventListener("keydown", handleEscKey);
    return () => document.removeEventListener("keydown", handleEscKey);
  }, []);

  // Ticket 02: 清理临时会话 - 组件卸载时删除未使用的临时会话
  useEffect(() => {
    return () => {
      // 组件卸载时，如果是临时会话且没有消息，删除它
      if (isTempConversation && activeConversation?.messages?.length === 0) {
        const tempId = activeConversation.id;
        if (tempId.startsWith("temp-")) {
          console.log(`清理临时会话：${tempId}`);
          // 不需要调用后端 API，临时会话没有持久化
        }
      }
    };
  }, []);

  // 重命名对话函数
  const handleRenameConversation = async (
    conversationId: string,
    e?: React.MouseEvent
  ) => {
    if (e) {
      e.stopPropagation();
    }

    const conv = conversations.find((c) => c.id === conversationId);
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
      await fetch(
        `http://localhost:8000/api/conversations/${renamingConversationId}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ title: newTitle.trim() }),
        }
      );

      // 更新本地状态
      setConversations(
        conversations.map((c) =>
          c.id === renamingConversationId ? { ...c, title: newTitle.trim() } : c
        )
      );

      if (activeConversation?.id === renamingConversationId) {
        setActiveConversation({
          ...activeConversation,
          title: newTitle.trim(),
        });
      }
    } catch (error) {
      console.error("重命名对话失败:", error);
      const errorMessage =
        error instanceof Error ? error.message : "重命名失败，请稍后重试";
      alert(errorMessage);
    } finally {
      setRenamingConversationId(null);
      setNewTitle("");
    }
  };

  // 回车确认重命名
  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      confirmRename();
    } else if (e.key === "Escape") {
      setRenamingConversationId(null);
      setNewTitle("");
    }
  };

  // 只在发送新消息时自动滚动，切换会话时不滚动 - Ticket 06
  useEffect(() => {
    // 首次渲染或切换会话时不滚动
    if (isInitialMountRef.current) {
      isInitialMountRef.current = false;
      previousMessageCountRef.current =
        activeConversation?.messages?.length || 0;
      shouldAutoScrollRef.current = true; // 默认允许自动滚动
      return;
    }

    // 只有当消息数量增加时才滚动（新消息到达）
    const currentCount = activeConversation?.messages?.length || 0;
    if (
      currentCount > previousMessageCountRef.current &&
      shouldAutoScrollRef.current
    ) {
      scrollToBottom();
    }
    previousMessageCountRef.current = currentCount;
  }, [activeConversation?.messages?.length]);

  // 修复：切换会话时重置状态，但保持滚动位置在底部 - Ticket 06
  useEffect(() => {
    if (activeConversation) {
      // 切换会话时重置初始标记，但不触发滚动
      previousMessageCountRef.current =
        activeConversation.messages?.length || 0;
      setIsTempConversation(false); // 从列表选择的对话不是临时会话
      // Ticket 01: 更新页面标题
      setPageTitle(activeConversation.title);
      // 重置标题生成标记，允许新会话生成标题
      titleGenerationRef.current = false;
      setHasGeneratedTitle(false);
      // 切换会话时滚动到底部
      setTimeout(() => scrollToBottom(), 0);
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
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const scrollToBottom = (isStreaming: boolean = false) => {
    messagesEndRef.current?.scrollIntoView({
      behavior: isStreaming ? "smooth" : "auto",
    });
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

  const loadConversations = async (targetId?: string) => {
    console.log(
      `[loadConversations] 开始 - targetId: ${
        targetId || "undefined"
      }, activeConversation: ${activeConversation?.id || "null"}`
    );
    setLoading(true);
    try {
      const conversationsList = await getConversations(userId);
      setConversations(conversationsList);
      console.log(
        `[loadConversations] 加载到 ${conversationsList.length} 个对话`
      );

      // Ticket 01: 如果指定了对话 ID，尝试加载该对话
      if (targetId) {
        const targetConversation = conversationsList.find(
          (c) => c.id === targetId
        );
        if (targetConversation) {
          console.log(
            `[loadConversations] 找到目标对话：${targetConversation.title}`
          );
          setActiveConversation(targetConversation);
          setPageTitle(targetConversation.title);
          setIsTempConversation(false);
          // 重置标题生成标记
          titleGenerationRef.current = false;
          setHasGeneratedTitle(false);
          // 切换会话时滚动到底部
          setTimeout(() => scrollToBottom(), 0);
          console.log(
            `[loadConversations] 成功加载 URL 指定的对话：${targetConversation.title}`
          );
        } else {
          // 对话不存在于列表中，检查是否已经激活了对应的对话（可能是点击切换导致的）
          // 如果已经激活了对应的对话，跳过创建临时会话
          console.log(
            `[loadConversations] 对话 ${targetId} 不在列表中，activeConversation.id: ${
              activeConversation?.id || "null"
            }`
          );
          if (activeConversation?.id === targetId) {
            console.log(
              `[loadConversations] 对话 ${targetId} 已激活，跳过创建`
            );
            return;
          }
          console.warn(
            `[loadConversations] 对话 ID ${targetId} 不存在，将创建新对话`
          );
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
    await createAndActivateTempConversation("新的诊断对话");
    // 清空 URL 中的对话 ID
    if (typeof window !== "undefined") {
      window.history.replaceState({}, "", "/chat");
    }
  };

  // Ticket 02: 转换临时会话为正式会话
  const convertTempConversationToPermanent =
    async (): Promise<Conversation | null> => {
      if (!activeConversation) {
        console.error("转换失败：activeConversation 不存在");
        return null;
      }

      // 检查是否已经是正式会话（ID 不以 temp- 开头）
      if (!activeConversation.id.startsWith("temp-")) {
        console.log(`会话已经是正式的，无需转换：${activeConversation.id}`);
        return activeConversation;
      }

      console.log(`[转换会话] 开始转换临时会话：${activeConversation.id}`);
      console.log(`[转换会话] 用户 ID: ${userId}`);
      console.log(`[转换会话] 标题：${activeConversation.title}`);

      try {
        // 创建正式会话
        console.log(`[转换会话] 调用 createConversation API...`);
        const conversation = await createConversation({
          patientId: userId,
          title: activeConversation.title,
        });

        console.log(`[转换会话] API 返回：`, conversation);

        if (!conversation || !conversation.id) {
          console.error("[转换会话] API 返回无效数据");
          return null;
        }

        // 更新本地状态
        setConversations((prev) => [conversation, ...prev]);
        setActiveConversation(conversation);
        setIsTempConversation(false);

        // 更新 URL 为新的对话 ID
        replaceConversationUrl(conversation.id);

        console.log(`[转换会话] 转换成功，新 ID: ${conversation.id}`);
        return conversation;
      } catch (error) {
        console.error("[转换会话] 转换临时会话失败:", error);
        if (error instanceof Error) {
          console.error("[转换会话] 错误详情:", error.message);
        }
        alert(
          `保存对话失败：${
            error instanceof Error ? error.message : "请稍后重试"
          }`
        );
        return null;
      }
    };

  // Ticket 03: 生成对话标题（基于用户第一条消息）
  const generateTitleFromMessage = (message: string): string => {
    let title = message.trim();

    // 去除末尾的标点符号
    title = title.replace(/[，。！？,.!?;；:：\s]+$/, "");

    // ≤10 字符：直接使用
    if (title.length <= 10) {
      return title || "新的诊断对话";
    }

    // >10 字符：截断并添加省略号
    title = title.substring(0, 30);
    title = title.replace(/[，。！？,.!?;；:：\s]+$/, "");
    return title + "...";
  };

  // Ticket 03: 调用 AI 生成更智能的标题
  const generateAITitle = async (message: string): Promise<string> => {
    try {
      // 调用后端 API 生成标题
      const response = await fetch("http://localhost:8000/api/generate-title", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) {
        throw new Error("标题生成失败");
      }

      const data = await response.json();
      let title = data.title?.trim();

      // 清理标题
      if (!title) {
        return generateTitleFromMessage(message);
      }

      // 限制长度
      if (title.length > 30) {
        title = title.substring(0, 30) + "...";
      }

      return title;
    } catch (error) {
      console.error("AI 标题生成失败，使用备用方案:", error);
      return generateTitleFromMessage(message);
    }
  };

  // Ticket 03: 更新对话标题（实时生成）
  const updateConversationTitle = async (
    conversationId: string,
    currentTitle: string,
    userMessageContent: string
  ) => {
    // 检查是否已经生成过标题
    if (titleGenerationRef.current) {
      console.log("标题已生成，跳过");
      return;
    }

    // 只有当标题是默认标题时才更新
    const defaultTitles = [
      "新的诊断对话",
      "新的对话",
      "MediTrace 对话",
      "有效提取用户的问题",
    ];
    if (!defaultTitles.includes(currentTitle)) {
      console.log("对话已有自定义标题，跳过自动更新");
      return;
    }

    // 标记开始生成标题
    titleGenerationRef.current = true;

    try {
      let newTitle: string;

      // ≤10 字符：直接使用
      if (userMessageContent.trim().length <= 10) {
        newTitle = generateTitleFromMessage(userMessageContent);
      } else {
        // >10 字符：调用 AI 生成
        newTitle = await generateAITitle(userMessageContent);
      }

      // 更新后端数据库
      await updateConversation(conversationId, newTitle);

      // 批量更新本地状态
      setConversations((prev) => {
        const updated = prev.map((c) =>
          c.id === conversationId ? { ...c, title: newTitle } : c
        );
        return updated;
      });

      setActiveConversation((prev) => {
        if (!prev) return null;
        return { ...prev, title: newTitle };
      });

      setPageTitle(newTitle);

      // 同步更新浏览器标签页
      document.title = newTitle + " - MediTrace";

      setHasGeneratedTitle(true);
      console.log(`对话标题已更新：${newTitle}`);
    } catch (error) {
      console.error("更新对话标题失败:", error);
      // 标题更新失败不影响消息发送
      // 重置标记，允许下次重试
      titleGenerationRef.current = false;
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim() || !activeConversation) return;

    setSending(true);
    try {
      // Ticket 02: 如果是临时会话，先转换为正式会话
      // 使用 activeConversation.id 作为判断依据，而不是依赖 isTempConversation 状态
      // 因为临时会话的 ID 以 "temp-" 开头
      let conversationId = activeConversation.id;
      const isTemp = conversationId.startsWith("temp-");

      if (isTemp) {
        console.log(`检测到临时会话，开始转换为正式会话：${conversationId}`);
        const convertedConv = await convertTempConversationToPermanent();
        if (!convertedConv) {
          // 转换失败，不发送消息
          console.error("临时会话转换失败，无法发送消息");
          setSending(false);
          return;
        }
        conversationId = convertedConv.id;
        console.log(`会话已转换，新 ID: ${conversationId}`);
      }

      const userMessage: Message = {
        role: "user",
        content: newMessage,
        timestamp: Date.now(),
      };

      const updatedMessages = [
        ...(activeConversation.messages || []),
        userMessage,
      ];
      const hasPreviousMessages =
        activeConversation.messages && activeConversation.messages.length > 0;

      // 新消息到达时，重置自动滚动标志
      shouldAutoScrollRef.current = true;

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

      // 标记第一条用户消息内容，用于标题生成
      const firstUserMessageContent = !hasPreviousMessages ? newMessage : "";

      await sendMessageStream(
        {
          conversationId: conversationId,
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

            // 实时标题更新：在 AI 第一个 chunk 到达时触发标题生成
            // 条件：
            // 1. 是第一条用户消息（hasPreviousMessages 为 false）
            // 2. 标题尚未生成（titleGenerationRef.current 为 false）
            // 3. 这是第一个 chunk（chunk.content 长度在 1-10 之间，表示刚开始）
            if (
              !hasPreviousMessages &&
              !titleGenerationRef.current &&
              chunk.content.length > 0 &&
              chunk.content.length < 100
            ) {
              // 异步生成标题，不阻塞消息流
              updateConversationTitle(
                conversationId,
                activeConversation.title,
                firstUserMessageContent
              );
            }

            // 流式响应时自动滚动（如果用户没有手动滚动）
            if (shouldAutoScrollRef.current) {
              scrollToBottom(true); // true 表示流式响应，使用平滑滚动
            }
          }, 0);
        }
      );

      // 如果标题尚未生成（例如 API 调用失败），在流式完成后尝试生成
      if (!hasPreviousMessages && !titleGenerationRef.current) {
        await updateConversationTitle(
          conversationId,
          activeConversation.title,
          firstUserMessageContent
        );
      }
    } catch (error) {
      console.error("发送消息失败:", error);
      alert("发送消息失败，请稍后重试");
      loadConversations();
    } finally {
      setSending(false);
    }
  };

  const handleDeleteConversation = async (
    conversationId: string,
    e: React.MouseEvent
  ) => {
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
          sidebarCollapsed ? "w-0" : "w-80"
        } ${isMobile ? "fixed inset-y-0 left-0 z-50 shadow-2xl" : ""}`}
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
                    console.log(
                      `[点击会话] 开始 - conv.id: ${conv.id}, conv.title: ${conv.title}`
                    );
                    // 关闭菜单
                    setActiveMenuConversationId(null);
                    // 标记用户正在切换会话，防止 useEffect 重复执行
                    isUserSwitchingRef.current = true;
                    console.log(`[点击会话] 设置 isUserSwitchingRef = true`);
                    // 使用 router.push 更新 URL，触发 Next.js 路由更新
                    // 对话加载由 useEffect 和 loadConversations 统一处理
                    router.push(`/chat/${conv.id}`);
                    console.log(
                      `[点击会话] router.push 完成，等待 loadConversations 加载对话`
                    );
                  }}
                  className={`group cursor-pointer transition-colors relative ${
                    activeConversation?.id === conv.id
                      ? "bg-green-50"
                      : "hover:bg-gray-50"
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
                            scrollingTitles.has(conv.id)
                              ? "hover-scroll-title"
                              : ""
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
                            activeMenuConversationId === conv.id
                              ? null
                              : conv.id
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
            {sidebarCollapsed ? "▶" : "◀"}
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
              {activeConversation ? pageTitle : ""}
            </h1>
          </div>
        </header>

        {/* 聊天内容区域 */}
        {activeConversation ? (
          <>
            {/* 消息列表 */}
            <div
              className="flex-1 overflow-y-auto p-6"
              onWheel={() => {
                // 用户手动滚动时，设置 shouldAutoScrollRef = false
                shouldAutoScrollRef.current = false;
              }}
              onTouchStart={() => {
                // 移动端触摸滚动时，设置 shouldAutoScrollRef = false
                shouldAutoScrollRef.current = false;
              }}
            >
              {activeConversation.messages?.map((msg, idx) => {
                const isLastMessage =
                  idx === (activeConversation.messages?.length || 0) - 1;
                const isAiStreaming =
                  msg.role === "assistant" && isLastMessage && sending;

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
                      <div
                        className={`text-sm ${
                          msg.role === "user" ? "" : "markdown-container"
                        }`}
                      >
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
                          msg.role === "user"
                            ? "text-green-100"
                            : "text-gray-500 dark:text-gray-400"
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
                  onKeyDown={(e) =>
                    e.key === "Enter" && !sending && handleSendMessage()
                  }
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
              <p className="text-xl font-semibold mb-2"></p>
              <p className="text-sm">或创建新的诊断对话</p>
            </div>
          </div>
        )}
      </main>
    </main>
  );
}
