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
- ✅ 其他浏览器操作

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
- 数据库：本地 SQLite，生产 Neon PostgreSQL

---

## 重要修复记录

### Vercel 后端部署修复（2026-09-22）

数据库启动、PostgreSQL 兼容迁移及上线验证见 [BUGFIX-VERCEL-BACKEND-DEPLOYMENT.md](./BUGFIX-VERCEL-BACKEND-DEPLOYMENT.md)。

**注意事项**:
- 后端代码修改后需要重启服务
- 前端代码修改后 HMR 会自动应用
- 验证时需用户手动在浏览器测试

---

## 服务管理

### 一键部署

在本项目中，用户说“部署”时，直接执行仓库根目录的 `./deploy-vercel.sh`，同时发布前端和后端到现有 Vercel Hobby 项目，无需再次确认常规发布。脚本成功退出且线上验证通过后才能报告部署成功。

只检查不发布：`./deploy-vercel.sh --check`；只验证线上：`./deploy-vercel.sh --verify`。
数据库迁移是显式选项 `--migrate`，仅执行已审查的追加字段迁移；正常部署沿用 Vercel 环境变量，不覆盖密钥。
详细流程、失败回退及日志位置见 [BACKEND-DEPLOYMENT.md](./BACKEND-DEPLOYMENT.md)。本地服务启动/停止仍按下方规则手动操作。

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
- **本地开发步骤**: [README.md](./README.md#本地开发)

---

## Vercel 部署配置（生产环境）

前后端采用同一 Vercel 项目的 Services 架构，生产数据库必须配置 `DATABASE_URL`。
当前未配置 `DEEPSEEK_API_KEY`，使用演示回复；真实 AI 推理在 FastAPI 后端执行，需要该变量并会产生 API 费用。

环境变量、数据库迁移、脚本选项及失败恢复以 [BACKEND-DEPLOYMENT.md](./BACKEND-DEPLOYMENT.md) 为准。

---

## 开发规范

1. **测试**: 禁止自动在浏览器发起对话测试（全局规则），需手动验证
2. **文档**: 所有 bug 修复需记录在 `BUGFIX-*.md` 文件中
3. **服务**: 服务启动和停止需手动操作
