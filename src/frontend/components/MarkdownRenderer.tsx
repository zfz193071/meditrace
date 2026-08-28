"use client";

import React, { useEffect, useRef, useState } from "react";

/**
 * Markdown 渲染组件
 * 支持语义化文本排版和打字机效果流式输出
 * 
 * 特性:
 * - 支持标题、段落、列表、代码块、引用等 Markdown 语法
 * - 打字机效果流式输出动画
 * - 深色/浅色主题适配
 * - 自动滚动到最新内容
 */

interface MarkdownRendererProps {
  /** Markdown 内容 */
  content: string;
  /** 是否启用打字机效果 */
  streaming?: boolean;
  /** 自定义样式类名 */
  className?: string;
}

/**
 * 简单的 Markdown 解析器（不依赖外部库，减少依赖）
 * 支持常见 Markdown 语法
 */
const parseMarkdown = (markdown: string): React.ReactNode[] => {
  const lines = markdown.split("\n");
  const elements: React.ReactNode[] = [];
  let currentList: string[] = [];
  let currentCodeBlock: string[] = [];
  let inCodeBlock = false;
  let listType: "ul" | "ol" = "ul";
  let inQuote = false;
  const quoteLines: string[] = [];

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <div key={`list-${elements.length}`} className="my-2 pl-4">
          {listType === "ul" ? (
            <ul className="list-disc space-y-1">
              {currentList.map((item, idx) => (
                <li key={idx} className="text-gray-700 dark:text-gray-300">
                  {parseInline(item)}
                </li>
              ))}
            </ul>
          ) : (
            <ol className="list-decimal space-y-1">
              {currentList.map((item, idx) => (
                <li key={idx} className="text-gray-700 dark:text-gray-300">
                  {parseInline(item)}
                </li>
              ))}
            </ol>
          )}
        </div>
      );
      currentList = [];
    }
  };

  const flushQuote = () => {
    if (quoteLines.length > 0) {
      elements.push(
        <blockquote
          key={`quote-${elements.length}`}
          className="border-l-4 border-green-400 pl-4 my-2 py-2 bg-gray-50 dark:bg-gray-800 rounded-r"
        >
          {quoteLines.map((line, idx) => (
            <p key={idx} className="text-gray-600 dark:text-gray-400 italic">
              {parseInline(line)}
            </p>
          ))}
        </blockquote>
      );
      quoteLines.length = 0;
      inQuote = false;
    }
  };

  const flushCodeBlock = () => {
    if (currentCodeBlock.length > 0) {
      elements.push(
        <pre
          key={`code-${elements.length}`}
          className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-2 text-sm font-mono"
        >
          <code>{currentCodeBlock.join("\n")}</code>
        </pre>
      );
      currentCodeBlock = [];
    }
  };

  const parseInline = (text: string): React.ReactNode => {
    // 处理内联样式
    let result: React.ReactNode[] = [];
    let remaining = text;

    // 处理加粗 **text**
    const boldRegex = /\*\*(.+?)\*\*/g;
    let match;
    let lastIndex = 0;

    while ((match = boldRegex.exec(remaining)) !== null) {
      if (match.index > lastIndex) {
        result.push(remaining.slice(lastIndex, match.index));
      }
      result.push(
        <strong key={`bold-${result.length}`} className="font-bold">
          {match[1]}
        </strong>
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < remaining.length) {
      result.push(remaining.slice(lastIndex));
    }

    // 处理斜切 *text*
    const italicRegex = /\*(.+?)\*/g;
    result = [];
    remaining = Array.isArray(result[0]) ? result.join("") : String(result);
    lastIndex = 0;

    while ((match = italicRegex.exec(remaining)) !== null) {
      if (match.index > lastIndex) {
        result.push(remaining.slice(lastIndex, match.index));
      }
      result.push(
        <em key={`italic-${result.length}`} className="italic">
          {match[1]}
        </em>
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < remaining.length) {
      result.push(remaining.slice(lastIndex));
    }

    // 处理行内代码 `code`
    const codeRegex = /`(.+?)`/g;
    result = [];
    remaining = Array.isArray(result[0]) ? result.join("") : String(result);
    lastIndex = 0;

    while ((match = codeRegex.exec(remaining)) !== null) {
      if (match.index > lastIndex) {
        result.push(remaining.slice(lastIndex, match.index));
      }
      result.push(
        <code
          key={`inline-code-${result.length}`}
          className="bg-gray-200 dark:bg-gray-700 px-1 rounded text-sm font-mono"
        >
          {match[1]}
        </code>
      );
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < remaining.length) {
      result.push(remaining.slice(lastIndex));
    }

    return result.length > 0 ? result : text;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 代码块
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        flushCodeBlock();
        inCodeBlock = false;
      } else {
        flushList();
        flushQuote();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      currentCodeBlock.push(line);
      continue;
    }

    // 标题
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushList();
      flushQuote();
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const HeadingTag = `h${level}` as keyof JSX.IntrinsicElements;
      const sizeClasses: Record<number, string> = {
        1: "text-3xl font-bold",
        2: "text-2xl font-bold",
        3: "text-xl font-bold",
        4: "text-lg font-bold",
        5: "text-base font-bold",
        6: "text-sm font-bold",
      };

      elements.push(
        <HeadingTag
          key={`heading-${i}`}
          className={`${sizeClasses[level]} my-3 text-gray-900 dark:text-gray-100`}
        >
          {parseInline(text)}
        </HeadingTag>
      );
      continue;
    }

    // 引用
    if (line.startsWith("> ")) {
      flushList();
      flushCodeBlock();
      inQuote = true;
      quoteLines.push(line.slice(2));
      continue;
    }

    if (inQuote && line.trim() === "") {
      flushQuote();
      continue;
    }

    if (inQuote) {
      quoteLines.push(line.slice(2));
      continue;
    }

    // 无序列表
    const ulMatch = line.match(/^[\*\-\+]\s+(.+)$/);
    if (ulMatch) {
      flushQuote();
      flushCodeBlock();
      listType = "ul";
      currentList.push(ulMatch[1]);
      continue;
    }

    // 有序列表
    const olMatch = line.match(/^\d+\.\s+(.+)$/);
    if (olMatch) {
      flushQuote();
      flushCodeBlock();
      listType = "ol";
      currentList.push(olMatch[1]);
      continue;
    }

    // 空行
    if (line.trim() === "") {
      flushList();
      flushQuote();
      elements.push(<div key={`empty-${i}`} className="h-2" />);
      continue;
    }

    // 普通段落
    flushList();
    flushQuote();
    elements.push(
      <p key={`p-${i}`} className="my-2 text-gray-700 dark:text-gray-300 leading-relaxed">
        {parseInline(line)}
      </p>
    );
  }

  // 刷新剩余内容
  flushList();
  flushQuote();
  flushCodeBlock();

  return elements;
};

export default function MarkdownRenderer({
  content,
  streaming = false,
  className = "",
}: MarkdownRendererProps) {
  const contentRef = useRef<HTMLDivElement>(null);

  // 当 streaming 为 false 时，直接显示完整内容
  // 当 streaming 为 true 时，content 就是当前已接收到的内容（由父组件逐步更新）
  const renderedContent = parseMarkdown(content);

  // 自动滚动到底部
  useEffect(() => {
    if (streaming && contentRef.current) {
      // 使用 requestAnimationFrame 确保在渲染后滚动
      requestAnimationFrame(() => {
        contentRef.current!.scrollTop = contentRef.current!.scrollHeight;
      });
    }
  }, [content, streaming]);

  return (
    <div
      ref={contentRef}
      className={`markdown-content ${className}`}
    >
      {renderedContent}
      {streaming && (
        <span className="inline-block w-0.5 h-5 bg-green-500 ml-1 animate-pulse align-middle streaming-cursor" />
      )}
    </div>
  );
}
