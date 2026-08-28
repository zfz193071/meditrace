# MediTrace 开发环境配置

本文档记录项目的开发环境配置，包括虚拟环境、依赖安装和服务启动。

---

## 🐍 Python 后端环境

### 虚拟环境设置

**重要**: 后端必须使用 Python 虚拟环境 (venv)，因为系统 Python 环境受保护。

#### 1. 创建虚拟环境（仅首次执行）

```bash
cd src/backend
python3 -m venv venv
```

#### 2. 激活虚拟环境

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 验证虚拟环境

```bash
which python  # 应该指向 venv/bin/python
which pip     # 应该指向 venv/bin/pip
```

### 后端服务启动

**方式 1 - 使用虚拟环境（推荐）:**
```bash
cd src/backend
source venv/bin/activate
python main.py
```

**方式 2 - 使用虚拟环境的 Python 直接启动:**
```bash
cd src/backend
./venv/bin/python main.py
```

**方式 3 - 使用 uvicorn（如果已安装）:**
```bash
cd src/backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 停止后端服务

```bash
# 查找并杀死端口 8000 上的进程
lsof -ti:8000 | xargs kill 2>/dev/null
```

### 虚拟环境常见问题

#### 问题 1: "externally-managed-environment" 错误

**原因**: macOS 系统 Python 环境受保护，不能直接安装包。

**解决方案**: 必须使用虚拟环境：
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 问题 2: "ModuleNotFoundError: No module 'fastapi'"

**原因**: 没有激活虚拟环境，或者依赖未安装。

**解决方案**:
```bash
cd src/backend
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

#### 问题 3: 虚拟环境损坏

**解决方案**: 删除并重新创建：
```bash
cd src/backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 虚拟环境文件说明

```
backend/
├── venv/                 # 虚拟环境目录（已添加到 .gitignore）
│   ├── bin/             # 可执行文件（包含 python, pip 等）
│   ├── lib/             # Python 库文件
│   ├── include/         # 头文件
│   └── pyvenv.cfg       # 虚拟环境配置
├── requirements.txt     # Python 依赖列表
├── .env                 # 环境变量（包含 API Key）
└── main.py             # 主应用
```

### 依赖列表

查看 `requirements.txt`:
```
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0
python-dotenv>=1.0.0
pydantic>=2.0.0
web3>=6.0.0
ipfshttpclient>=0.8.0
```

---

## 🟢 Node.js 前端环境

### 环境要求

- Node.js >= 18
- pnpm（推荐使用 pnpm 而非 npm）

### 安装步骤

```bash
cd src/frontend
pnpm install
```

### 启动开发服务器

```bash
pnpm dev
```

访问 http://localhost:3000

### 停止前端服务

```bash
# 查找并杀死端口 3000 上的进程
lsof -ti:3000 | xargs kill 2>/dev/null
```

---

## 🚀 完整启动流程

### 首次启动

```bash
# 1. 启动后端
cd src/backend
python3 -m venv venv              # 仅首次执行
source venv/bin/activate
pip install -r requirements.txt
python main.py                    # 后台运行或新开终端

# 2. 启动前端（新终端）
cd src/frontend
pnpm install                      # 仅首次执行
pnpm dev
```

### 日常开发启动

```bash
# 终端 1 - 后端
cd src/backend
source venv/bin/activate
python main.py

# 终端 2 - 前端
cd src/frontend
pnpm dev
```

### 快速重启脚本

**macOS/Linux:**
```bash
#!/bin/bash
# scripts/restart-all.sh

# 停止服务
echo "停止服务..."
lsof -ti:8000 | xargs kill 2>/dev/null
lsof -ti:3000 | xargs kill 2>/dev/null

# 启动后端
echo "启动后端..."
cd src/backend
source venv/bin/activate
python main.py &

# 启动前端
echo "启动前端..."
cd src/frontend
pnpm dev &

echo "服务已启动"
```

---

## 📝 环境变量配置

### 后端 .env

```bash
cd src/backend
cp .env.example .env
```

编辑 `.env` 文件，填入：
```
DEEPSEEK_API_KEY=your_api_key_here
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 前端 .env.local

```bash
cd src/frontend
cp .env.example .env.local
```

---

## 🔍 环境验证

### 检查后端

```bash
# 检查端口 8000
lsof -i:8000

# 测试 API
curl http://localhost:8000/api/health
```

### 检查前端

```bash
# 检查端口 3000
lsof -i:3000

# 访问浏览器
open http://localhost:3000
```

---

## 📚 相关文档

- [README.md](./README.md) - 项目概述
- [DEPLOYMENT.md](./DEPLOYMENT.md) - 部署指南
- [AGENTS.md](./AGENTS.md) - 项目助手指南

---

**最后更新**: 2026-08-28
