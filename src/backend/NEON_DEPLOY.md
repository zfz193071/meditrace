# MediTrace 后端部署到 Neon + Render

本指南将帮助你快速将 MediTrace 后端部署到云端。

## 📋 部署架构

```
前端 (已部署) → Render 后端 (FastAPI) → Neon PostgreSQL
https://meditrace.vercel.app        ↓              ↓
                              环境变量配置    免费数据库
```

---

## 🚀 第一步：配置 Neon PostgreSQL

### 1.1 访问 Neon Console
打开 https://console.neon.tech/app/projects/misty-thunder-45447876

### 1.2 获取连接字符串
1. 点击 **"Connection Details"** 按钮
2. 选择 **"Connection URI"** 格式
3. 复制连接字符串（格式如下）：
```
postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require
```

**重要**: 连接字符串包含敏感信息，请妥善保管！

### 1.3 初始化数据库 schema
在本地终端执行：

```bash
# 进入后端目录
cd src/backend

# 激活虚拟环境
source venv/bin/activate

# 设置环境变量（临时）
export DATABASE_URL="你的 Neon 连接字符串"

# 运行迁移脚本
python -c "from database import run_migration; run_migration('001_initial_schema.sql')"
```

**或者** 使用 psql 直接执行：
```bash
psql "你的 Neon 连接字符串" -f migrations/001_initial_schema.sql
```

---

## 🌐 第二步：部署到 Render（推荐）

### 2.1 准备代码
```bash
# 推送代码到远程仓库
git push origin main
```

### 2.2 创建 Render 账户
访问 https://render.com 并使用 GitHub 登录

### 2.3 创建 Web Service

1. 在 Render 控制台点击 **"New +"** → **"Web Service"**
2. 连接你的 GitHub 仓库：`zfz193071/meditrace`
3. 配置服务参数：

| 配置项 | 值 |
|--------|-----|
| **Name** | `meditrace-backend` |
| **Region** | 选择离你最近的（如 Singapore） |
| **Branch** | `main` |
| **Root Directory** | `src/backend` |
| **Runtime** | `Python` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

### 2.4 配置环境变量

在 Render 控制台的 **"Environment"** 标签页添加：

```bash
# 数据库（从 Neon 复制的连接字符串）
DATABASE_URL=postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require

# DeepSeek API 密钥
DEEPSEEK_API_KEY=sk-xxx

# CORS 配置（允许前端域名）
CORS_ORIGINS=https://meditrace.vercel.app,http://localhost:3000

# 端口（Render 自动注入，但建议显式设置）
PORT=8000
```

### 2.5 高级配置（可选）

点击 **"Advanced"** 标签页：

- **Auto-Deploy**: 开启（代码推送后自动部署）
- **Health Check Path**: `/health`（后端已提供健康检查端点）

### 2.6 部署
点击 **"Create Web Service"**，Render 将开始构建和部署。

首次部署约需 5-10 分钟。

---

## 🔧 第三步：验证部署

### 3.1 检查服务状态
在 Render 控制台查看 **"Events"** 标签页的构建日志。

### 3.2 测试健康检查
```bash
curl https://meditrace-backend.onrender.com/health
```

预期返回：
```json
{"status":"ok","database":"connected"}
```

### 3.3 测试 API 端点
```bash
# 获取病历列表
curl https://meditrace-backend.onrender.com/api/records

# 获取对话列表
curl https://meditrace-backend.onrender.com/api/conversations
```

---

## 🔗 第四步：更新前端配置

前端已部署到 Vercel，需要更新 API 地址：

### 4.1 Vercel 环境变量

访问 https://vercel.com/dashboard 找到 meditrace 项目

在 **Settings → Environment Variables** 添加：

```bash
NEXT_PUBLIC_API_URL=https://meditrace-backend.onrender.com
```

### 4.2 重新部署前端
```bash
# 在本地修改前端配置（如果需要）
# src/frontend/.env.local
NEXT_PUBLIC_API_URL=https://meditrace-backend.onrender.com

# 推送代码触发自动部署
git add src/frontend
git commit -m "feat: 更新生产环境 API 地址"
git push origin main
```

---

## 📝 环境变量参考

### 本地开发（src/backend/.env）
```bash
# 数据库（开发使用 SQLite，注释掉）
# DATABASE_URL=sqlite:///./meditrace.db

# 或切换到 Neon（测试用）
# DATABASE_URL=postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require

# DeepSeek API
DEEPSEEK_API_KEY=sk-xxx

# CORS（开发环境）
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Render 生产环境
```bash
DATABASE_URL=postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require
DEEPSEEK_API_KEY=sk-xxx
CORS_ORIGINS=https://meditrace.vercel.app,http://localhost:3000
PORT=8000
```

---

## 🔄 后续部署流程

### 代码更新后
```bash
# 1. 提交代码
git add .
git commit -m "feat/fix: 描述变更"

# 2. 推送到远程
git push origin main

# 3. Render 会自动重新部署（如果开启了 Auto-Deploy）
```

### 数据库变更
```bash
# 添加新的迁移脚本到 src/backend/migrations/
# 然后在 Render 的 Shell 中运行：
# 1. 点击 Render 控制台的 "Shell" 标签
# 2. 执行：
python -c "from database import run_migration; run_migration('002_new_migration.sql')"
```

---

## 🛠️ 故障排查

### 问题 1: 数据库连接失败
**症状**: 健康检查返回 `{"database":"disconnected"}`

**解决**:
1. 检查 `DATABASE_URL` 是否正确
2. 确认 Neon 项目未休眠（免费套餐会休眠）
3. 查看 Render 日志：`Events` 标签页

### 问题 2: CORS 错误
**症状**: 前端调用 API 时报 CORS 错误

**解决**:
1. 检查 `CORS_ORIGINS` 是否包含前端域名
2. 确认前端使用的 API 地址与 `CORS_ORIGINS` 一致

### 问题 3: 构建失败
**症状**: Render 构建失败

**解决**:
1. 查看构建日志定位错误
2. 检查 `requirements.txt` 是否包含所有依赖
3. 确认 `Root Directory` 设置为 `src/backend`

---

## 📊 监控和维护

### Render 监控
- **Metrics**: 查看 CPU、内存使用情况
- **Logs**: 实时日志流
- **Alerts**: 配置告警通知

### Neon 监控
- **Dashboard**: 查看数据库使用情况
- **Usage**: 监控查询量和存储

---

## ⚠️ 重要注意事项

1. **Neon 免费套餐**:
   - 数据库会休眠（无请求 5 分钟后）
   - 首次请求会有冷启动延迟（约 1-2 秒）
   - 适合开发和小型生产环境

2. **Render 免费套餐**:
   - 服务会休眠（15 分钟无请求）
   - 每月 750 小时免费额度
   - 适合开发和演示

3. **生产环境建议**:
   - 考虑升级到付费套餐避免休眠
   - 添加监控和告警
   - 定期备份数据库（Neon 支持时间点恢复）

---

## 🎉 部署完成

完成以上步骤后，你的 MediTrace 后端已成功部署到云端！

**服务地址**:
- 后端 API: `https://meditrace-backend.onrender.com`
- 前端页面: `https://meditrace.vercel.app`
- 数据库: Neon PostgreSQL（免费）

---

## 📚 相关文档

- [Neon 官方文档](https://neon.tech/docs)
- [Render 官方文档](https://render.com/docs)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [项目部署指南](./POSTGRES_SETUP.md)
