# MediTrace 项目助手指南

---

## ⚠️ 重要禁令：禁止自动在浏览器发起对话测试

**此规则适用于项目所有页面的智能体会话测试。**

### 禁止行为

- ❌ 禁止自动在浏览器中向 AI 发送消息进行测试
- ❌ 禁止自动在对话页面输入内容并触发 AI 响应
- ❌ 禁止自动验证 AI 回复的流式显示、内容准确性等需要消耗 API token 的操作

**原因**: 这些操作会消耗 DeepSeek API token，产生不必要的费用。

### 允许的行为

- ✅ 可以自动导航页面（`browser_navigate`）
- ✅ 可以自动点击页面元素（`browser_click`）
- ✅ 可以自动读取页面内容（`browser_get_page`）
- ✅ 可以自动抓包分析网络请求（`browser_start_capture`）
- ✅ 其他不消耗 API token 的浏览器操作

### 正确做法

- ✅ 代码修改完成后，提供测试步骤让用户手动验证
- ✅ 如需验证对话功能，告知用户"请手动发送消息测试"
- ✅ 使用代码审查、日志分析、测试脚本等非浏览器方式验证逻辑

### 适用范围

此禁令适用于：
- 所有页面（`/conversations`, `/`, 等）
- 所有涉及 AI 对话的功能
- 所有 agent 运行场景

---

## 项目概述

MediTrace - 医疗 AI 诊断溯源系统
- 前端：Next.js + React + TypeScript
- 后端：Python FastAPI
- 数据库：SQLite

---

## 重要修复记录

### 流式响应显示 Bug（2026-08-28）

**问题**: 流式接口返回数据但页面一次性显示所有内容  
**状态**: ✅ 已修复

**参考文档**: [BUGFIX-STREAMING-RECORD.md](./BUGFIX-STREAMING-RECORD.md)

**修改的文件**:
- `src/backend/main.py` - 流式响应完成信号修复
- `src/frontend/app/conversations/page.tsx` - UI 更新机制修复

**注意事项**:
- 后端代码修改后需要重启服务
- 前端代码修改后 HMR 会自动应用
- 验证时需用户手动在浏览器测试

---

## 服务管理

### ⚠️ 重要：后端必须使用虚拟环境 (venv)

**每次启动后端前必须激活虚拟环境**，否则会因为系统 Python 环境受保护而启动失败。

```bash
# 后端启动（必须使用 venv）
cd src/backend
source venv/bin/activate    # 激活虚拟环境
python main.py

# 或者直接使用虚拟环境的 Python
cd src/backend
./venv/bin/python main.py
```

### 启动服务（手动）
```bash
# 后端
cd src/backend && source venv/bin/activate && python main.py

# 前端
cd src/frontend && pnpm dev
```

### 停止服务（手动）
```bash
# 停止后端（端口 8000）
lsof -ti:8000 | xargs kill 2>/dev/null

# 停止前端（端口 3000）
lsof -ti:3000 | xargs kill 2>/dev/null
```

### 虚拟环境信息
- **路径**: `src/backend/venv/`
- **创建命令**: `python3 -m venv venv`
- **激活命令**: `source venv/bin/activate`
- **详细文档**: [DEVELOPMENT_ENV.md](./DEVELOPMENT_ENV.md)

---

## 开发规范

1. **测试**: 禁止自动在浏览器发起对话测试（全局规则），需手动验证
2. **文档**: 所有 bug 修复需记录在 `BUGFIX-*.md` 文件中
3. **服务**: 服务启动和停止需手动操作
