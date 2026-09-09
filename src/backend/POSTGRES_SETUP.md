# MediTrace PostgreSQL 配置指南

## 📋 概述

本项目已支持 SQLite（开发）和 PostgreSQL（生产）两种数据库。

## 🚀 免费 PostgreSQL 服务推荐（无需绑卡）

### 1. **Neon**（推荐 ⭐）
- ✅ 完全免费，无需信用卡
- ✅ Serverless PostgreSQL
- ✅ 自动扩展
- 📍 https://neon.tech

**创建步骤**:
1. 访问 https://neon.tech
2. 使用 GitHub 登录
3. 创建新项目（Project）
4. 复制连接字符串（Connection String）
5. 格式：`postgresql://user:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require`

### 2. **Supabase**
- ✅ 免费套餐充足
- ✅ 包含 PostgreSQL + 额外功能
- 📍 https://supabase.com

### 3. **Render PostgreSQL**
- ✅ 免费数据库服务
- ⚠️ 需要绑定信用卡（但数据库本身免费）
- 📍 https://render.com

---

## 🔧 配置步骤

### 步骤 1: 获取 PostgreSQL 连接字符串

从您选择的平台获取连接字符串，例如：
```
postgresql://user:password@host:port/database?sslmode=require
```

### 步骤 2: 设置环境变量

#### 本地开发（.env 文件）
```bash
# src/backend/.env
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
```

#### Render 部署
```bash
# 在 Render 控制台的 Environment 标签页添加
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
```

#### Vercel 部署
```bash
# 在 Vercel 控制台的 Settings -> Environment Variables 添加
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
```

### 步骤 3: 安装依赖

```bash
cd src/backend
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` 已包含 `psycopg2-binary>=2.9.0`

### 步骤 4: 初始化数据库

```bash
# 运行迁移脚本
python -c "from database import run_migration; run_migration('001_initial_schema.sql')"
```

或者直接使用 Python 执行 SQL：
```bash
psql "postgresql://user:password@host:port/database?sslmode=require" -f migrations/001_initial_schema.sql
```

---

## 🔄 从 SQLite 迁移到 PostgreSQL

### 方案 A: 使用 pgloader（推荐）

```bash
# 安装 pgloader
brew install pgloader  # macOS
sudo apt-get install pgloader  # Linux

# 执行迁移
pgloader \
  sqlite:///meditrace.db \
  postgresql://user:password@host:port/database?sslmode=require
```

### 方案 B: 手动导出导入

```bash
# 1. 从 SQLite 导出
sqlite3 meditrace.db ".dump" > backup.sql

# 2. 修改 SQL 语法（适配 PostgreSQL）
# 将 " 替换为 '
# 修改数据类型（JSON -> JSONB）

# 3. 导入到 PostgreSQL
psql "postgresql://user:password@host:port/database?sslmode=require" < backup.sql
```

---

## 📝 环境变量参考

```bash
# 数据库
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require

# DeepSeek API（可选）
DEEPSEEK_API_KEY=sk-xxx

# CORS 配置
CORS_ORIGINS=http://localhost:3000,https://your-frontend-domain.com

# IPFS（可选）
PINATA_JWT_TOKEN=xxx
```

---

## ✅ 验证连接

```bash
cd src/backend
source venv/bin/activate
python -c "from database import get_db_connection; conn = get_db_connection(); print('Database connected:', conn)"
```

---

## 🌐 部署到不同平台

### Koyeb（无需绑卡）
```yaml
# .koyeb.yaml
services:
  - name: meditrace-backend
    type: web
    builder:
      type: docker
      dockerfile: Dockerfile
    env:
      - key: DATABASE_URL
        value: ${DATABASE_URL}
      - key: DEEPSEEK_API_KEY
        value: ${DEEPSEEK_API_KEY}
    ports:
      - port: 8000
        assign: true
```

### Vercel（Serverless）
需要适配 Serverless 模式，参考 `vercel.json` 配置。

### Hugging Face Spaces
使用 Docker runtime，配置 `Dockerfile`。

---

## ⚠️ 注意事项

1. **SSL 连接**: 大多数云 PostgreSQL 服务需要 SSL 连接
2. **连接池**: 生产环境建议使用连接池（如 SQLAlchemy 连接池）
3. **环境变量**: 不要将数据库连接字符串提交到 Git
4. **端口**: Koyeb 使用 `$PORT` 环境变量，不要硬编码端口

---

## 📚 相关文档

- [Neon 文档](https://neon.tech/docs)
- [Supabase 文档](https://supabase.com/docs)
- [psycopg2 文档](https://www.psycopg.org/docs/)
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
