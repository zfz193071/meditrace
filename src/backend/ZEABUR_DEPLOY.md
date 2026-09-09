# MediTrace 后端部署到 Zeabur + Neon

本指南将帮助你快速将 MediTrace 后端部署到 **Zeabur** 平台，使用 **Neon PostgreSQL** 数据库。

## 📋 部署架构

```
前端 (Vercel) → Zeabur 后端 (FastAPI) → Neon PostgreSQL
https://meditrace.baozaolaoba.top  ↓              ↓
                              自动扩展       免费数据库
```

**优势对比 Render**:
- ✅ **永不休眠** - 免费套餐也保持运行
- ✅ **自动扩展** - 根据流量自动调整资源
- ✅ **更快速度** - 全球边缘节点部署
- ✅ **简单配置** - 零配置文件即可部署

---

## 🚀 第一步：准备代码

### 1.1 确认部署文件已创建

以下文件已创建在 `src/backend/` 目录:

- ✅ `Procfile` - 指定启动命令
- ✅ `zbpack.json` - Zeabur 构建配置
- ✅ `requirements.txt` - Python 依赖

### 1.2 推送代码到 GitHub

```bash
cd /Users/zhuwenfang/a-working/meditrace

# 提交新创建的部署配置文件
git add src/backend/Procfile src/backend/zbpack.json

# 提交代码
git commit -m "feat: 准备 Zeabur 部署配置"

# 推送到远程仓库
git push origin main
```

---

## 🗄️ 第二步：配置 Neon PostgreSQL

你已经有 Neon 项目：https://console.neon.tech/app/projects/misty-thunder-45447876

### 2.1 获取数据库连接字符串

1. 打开 [Neon Console](https://console.neon.tech/app/projects/misty-thunder-45447876)
2. 在 dashboard 页面找到 **"Connection Details"** 或 **"Connection URI"**
3. 点击 **"Copy"** 复制连接字符串

**连接字符串格式**:
```
postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require
```

**⚠️ 重要**: 连接字符串包含密码，请妥善保管！

### 2.2 初始化数据库 Schema

在本地终端执行（推荐使用 psql）:

```bash
# 进入后端目录
cd src/backend

# 使用 psql 连接 Neon 数据库
psql "你的 Neon 连接字符串"

# 在 psql 提示符下执行以下 SQL:
CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(36) PRIMARY KEY,
    patient_id VARCHAR(42) NOT NULL,
    title VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    context_refs JSONB,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_patient_id ON conversations(patient_id);
CREATE INDEX IF NOT EXISTS idx_updated_at ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation ON messages(conversation_id, timestamp);

# 退出 psql
\q
```

**或者使用 Python 脚本初始化**:

```bash
# 进入后端目录
cd src/backend

# 设置环境变量
export DATABASE_URL="你的 Neon 连接字符串"

# 使用 Python 初始化
python3 << EOF
import sqlite3
import psycopg2
from contextlib import contextmanager

DATABASE_URL = "你的 Neon 连接字符串"

@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

with get_db() as conn:
    # 创建 conversations 表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id VARCHAR(36) PRIMARY KEY,
            patient_id VARCHAR(42) NOT NULL,
            title VARCHAR(200) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
        )
    """)
    
    # 创建 messages 表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            context_refs JSONB,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    
    # 创建索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_patient_id ON conversations(patient_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON conversations(updated_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation ON messages(conversation_id, timestamp)")
    
    print("✅ Database tables created successfully")
EOF
```

---

## 🌐 第三步：部署到 Zeabur

### 3.1 创建 Zeabur 账户

1. 访问 https://zeabur.com
2. 点击 **"Sign In"** → **"Sign in with GitHub"**
3. 授权 Zeabur 访问你的 GitHub 账户

### 3.2 创建新项目

1. 在 Zeabur 控制台点击 **"New Project"**
2. 输入项目名称：`meditrace-backend`
3. 点击 **"Create"**

### 3.3 连接 GitHub 仓库

1. 在项目中点击 **"New Service"**
2. 选择 **"GitHub"** 作为源代码
3. 授权 Zeabur 访问 GitHub
4. 选择仓库：`zfz193071/meditrace` (或你的仓库名)
5. 点击 **"Connect"**

### 3.4 配置服务

Zeabur 会自动检测 Python 项目，你需要配置以下参数:

#### 基本配置

| 配置项 | 值 |
|--------|-----|
| **Service Name** | `meditrace-backend` |
| **Region** | 选择离你最近的 (如 Singapore/Tokyo) |
| **Branch** | `main` |
| **Root Directory** | `src/backend` |

#### 构建配置 (自动检测)

Zeabur 会自动识别:
- ✅ `requirements.txt` → 自动安装依赖
- ✅ `Procfile` → 使用 `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
- ✅ `zbpack.json` → 自定义构建/启动命令

**如果自动检测失败，手动配置**:

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3.5 配置环境变量

在 Zeabur 控制台的 **"Variables"** 标签页添加以下环境变量:

```bash
# 数据库连接 (从 Neon 复制的连接字符串)
DATABASE_URL=postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require

# DeepSeek API 密钥 (可选，留空则使用模拟回复)
DEEPSEEK_API_KEY=sk-xxx

# CORS 配置 (允许前端域名)
CORS_ORIGINS=https://meditrace.baozaolaoba.top,http://localhost:3000

# 端口 (Zeabur 会自动注入，但建议显式设置)
PORT=8000

# 区块链配置 (可选)
BLOCKCHAIN_RPC_URL=https://sepolia.infura.io/v3/xxx
CONTRACT_ADDRESS_SEPOLIA=0x...

# IPFS 配置 (可选)
PINATA_JWT_TOKEN=xxx
```

**⚠️ 重要**: 
- `DEEPSEEK_API_KEY` 可选，不设置时后端会使用模拟回复 (不消耗 token)
- `CORS_ORIGINS` 必须包含你的前端域名 `https://meditrace.baozaolaoba.top`

### 3.6 部署

1. 点击 **"Deploy"** 按钮
2. Zeabur 将开始构建和部署
3. 首次部署约需 3-5 分钟

---

## 🔧 第四步：验证部署

### 4.1 检查服务状态

在 Zeabur 控制台查看部署日志:
- ✅ **Build Successful** - 构建成功
- ✅ **Service Running** - 服务运行中

### 4.2 获取服务 URL

部署完成后，Zeabur 会提供一个自动生成的域名:
```
https://meditrace-backend.your-zeabur-app.com
```

你也可以在 **"Domains"** 标签页自定义域名。

### 4.3 测试健康检查

```bash
curl https://meditrace-backend.your-zeabur-app.com/health
```

**预期返回**:
```json
{"status":"healthy","version":"0.1.0"}
```

### 4.4 测试 API 端点

```bash
# 测试诊断 API (演示模式，不消耗 token)
curl -X POST https://meditrace-backend.your-zeabur-app.com/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{"symptoms": "发热头痛", "userId": "test-user-123"}'

# 测试对话 API
curl -X POST https://meditrace-backend.your-zeabur-app.com/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"patientId": "test-user-123", "title": "测试对话"}'
```

---

## 🔗 第五步：更新前端配置

前端已部署到 `https://meditrace.baozaolaoba.top/`,需要更新 API 地址。

### 5.1 修改前端代码

编辑前端配置文件 (根据实际项目结构):

```bash
# 查找前端 API 配置位置
cd src/frontend
grep -r "API_URL\|BASE_URL\|apiUrl" . --include="*.ts" --include="*.tsx" --include="*.env*"
```

通常在以下位置之一:
- `.env.local` 或 `.env.production`
- `src/config/api.ts`
- `src/lib/api.ts`

**修改示例**:

```env
# src/frontend/.env.production
NEXT_PUBLIC_API_URL=https://meditrace-backend.your-zeabur-app.com
```

### 5.2 重新部署前端

```bash
# 如果前端使用 Vercel，推送代码后会自动重新部署
cd /Users/zhuwenfang/a-working/meditrace

git add src/frontend
git commit -m "feat: 更新生产环境 API 地址到 Zeabur"
git push origin main
```

**或者在 Vercel 控制台手动触发部署**:
1. 访问 https://vercel.com/dashboard
2. 找到 `meditrace` 项目
3. 点击 **"Deployments"** → 触发新部署

---

## 📝 环境变量参考

### 本地开发 (`src/backend/.env`)

```bash
# 数据库 (开发使用 SQLite，注释掉)
# DATABASE_URL=sqlite:///./meditrace.db

# 或切换到 Neon (测试用)
# DATABASE_URL=postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require

# DeepSeek API
DEEPSEEK_API_KEY=sk-xxx

# CORS (开发环境)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# IPFS (可选)
PINATA_JWT_TOKEN=xxx
```

### Zeabur 生产环境

```bash
DATABASE_URL=postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require
DEEPSEEK_API_KEY=sk-xxx  # 可选，留空则使用模拟回复
CORS_ORIGINS=https://meditrace.baozaolaoba.top,http://localhost:3000
PORT=8000
BLOCKCHAIN_RPC_URL=https://sepolia.infura.io/v3/xxx  # 可选
CONTRACT_ADDRESS_SEPOLIA=0x...  # 可选
PINATA_JWT_TOKEN=xxx  # 可选
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

# 3. Zeabur 会自动重新部署 (如果开启了 Auto-Deploy)
```

### 数据库变更

如果修改了数据库 schema:

```bash
# 1. 在本地创建迁移脚本
cd src/backend/migrations
# 创建 002_new_table.sql

# 2. 在 Zeabur Shell 中运行迁移
# - 点击 Zeabur 控制台的 "Shell" 标签
# - 执行:
python3 << EOF
import psycopg2
from contextlib import contextmanager

DATABASE_URL = "你的 Neon 连接字符串"  # 从 Zeabur Variables 复制

@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

with get_db() as conn:
    # 执行迁移 SQL
    conn.execute("ALTER TABLE conversations ADD COLUMN new_column VARCHAR(100)")
    print("✅ Migration completed")
EOF
```

---

## 🛠️ 故障排查

### 问题 1: 构建失败

**症状**: Zeabur 构建日志显示错误

**解决**:
1. 查看构建日志定位错误
2. 检查 `requirements.txt` 是否包含所有依赖
3. 确认 `Root Directory` 设置为 `src/backend`
4. 检查 `Procfile` 格式是否正确 (注意缩进)

### 问题 2: 数据库连接失败

**症状**: 健康检查返回错误或日志显示数据库连接失败

**解决**:
1. 检查 `DATABASE_URL` 是否正确 (复制时不要遗漏字符)
2. 确认 Neon 项目未删除或暂停
3. 检查 `DATABASE_URL` 中的密码是否包含特殊字符 (可能需要 URL 编码)
4. 查看 Zeabur 日志：`Deployments` → 点击部署 → `Logs`

### 问题 3: CORS 错误

**症状**: 前端调用 API 时报 CORS 错误

**解决**:
1. 检查 `CORS_ORIGINS` 是否包含前端域名
2. 确认前端使用的 API 地址与 `CORS_ORIGINS` 一致
3. 检查前端代码中是否正确设置了 `credentials: 'include'`

### 问题 4: 服务启动失败

**症状**: Zeabur 显示服务 unhealthy

**解决**:
1. 查看启动日志：`Deployments` → `Logs`
2. 检查 `Procfile` 中的启动命令
3. 确认 `main.py` 可以独立运行
4. 检查环境变量是否正确设置

---

## 📊 监控和维护

### Zeabur 监控

- **Metrics**: 查看 CPU、内存、请求量
- **Logs**: 实时日志流 (调试必备)
- **Domains**: 管理自定义域名
- **Variables**: 管理环境变量

### Neon 监控

- **Dashboard**: 查看数据库使用情况
- **Usage**: 监控查询量和存储
- **Branches**: 支持数据库分支 (测试用)

---

## ⚠️ 重要注意事项

### 1. 环境变量安全

- ✅ **不要**将 `.env` 文件提交到 Git
- ✅ **使用** Zeabur 的 Variables 管理敏感信息
- ✅ 定期检查环境变量是否泄露

### 2. 数据库备份

Neon 自动提供时间点恢复 (PITR):
- 免费套餐：7 天保留期
- 可在 Neon Console 手动创建分支作为备份

### 3. 成本优化

- ✅ Zeabur 免费套餐足够小型项目使用
- ✅ 设置资源限制避免意外费用
- ✅ 监控使用量，设置告警

### 4. 生产环境建议

- ✅ 启用 Zeabur 的 HTTPS (默认启用)
- ✅ 配置自定义域名 (可选)
- ✅ 添加监控和告警
- ✅ 定期备份数据库
- ✅ 使用 DeepSeek API Key 启用真实 AI (可选)

---

## 🎉 部署完成

完成以上步骤后，你的 MediTrace 后端已成功部署到 Zeabur!

**服务地址**:
- 后端 API: `https://meditrace-backend.your-zeabur-app.com` (Zeabur 提供的域名)
- 前端页面: `https://meditrace.baozaolaoba.top/`
- 数据库：Neon PostgreSQL (免费)

---

## 📚 相关文档

- [Zeabur 官方文档](https://zeabur.com/docs)
- [Zeabur Python 部署指南](https://zeabur.com/docs/en-US/guides/python)
- [Neon 官方文档](https://neon.tech/docs)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [项目部署记录](./NEON_DEPLOY.md)

---

## 🆘 需要帮助？

如果遇到问题:

1. 查看 Zeabur 日志：`Deployments` → `Logs`
2. 检查环境变量是否正确
3. 在 Zeabur Discord 社区提问：https://discord.gg/zeabur
4. 返回本地测试：`cd src/backend && uvicorn main:app --reload`

祝部署顺利！🚀
