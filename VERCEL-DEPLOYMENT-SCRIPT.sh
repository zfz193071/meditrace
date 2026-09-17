#!/bin/bash
# MediTrace Vercel 部署脚本
# 注意：需要先安装 Vercel CLI

set -e

echo "=========================================="
echo "MediTrace Vercel 全栈部署脚本"
echo "=========================================="
echo ""
echo "⚠️  本脚本只负责设置环境变量并触发部署。"
echo "   使用 Vercel Services 架构前，必须在控制台手动完成两步："
echo "     1) Settings → General → Root Directory 清空（= 仓库根目录）"
echo "     2) Settings → Build and Development Settings → Framework Preset = Services"
echo "   详见 VERCEL-SERVICES-DEPLOYMENT.md"
echo ""

# 检查 Vercel CLI 是否安装
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI 未安装!"
    echo ""
    echo "请先安装 Vercel CLI:"
    echo "  npm i -g vercel"
    echo "  # 或者"
    echo "  brew install vercel-cli"
    echo ""
    echo "如果 npm 权限有问题，先修复:"
    echo "  sudo chown -R $(whoami) ~/.npm"
    echo ""
    exit 1
fi

echo "✅ Vercel CLI 已安装"
echo ""

# 进入项目目录
cd /Users/zhuwenfang/a-working/meditrace

# 登录 Vercel
echo "=========================================="
echo "步骤 1: 登录 Vercel"
echo "=========================================="
vercel login

echo ""
echo "=========================================="
echo "步骤 2: 从 .env 文件读取环境变量"
echo "=========================================="
echo ""

# 读取 .env 文件
ENV_FILE="src/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 找不到环境变量文件：$ENV_FILE"
    exit 1
fi

echo "✅ 找到环境变量文件：$ENV_FILE"
echo ""

# 从 .env 文件读取变量（跳过注释和空行）
get_env_value() {
    local key=$1
    grep "^${key}=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'"
}

# 读取各个环境变量
USE_SEPOLIA=$(get_env_value "USE_SEPOLIA")
SEPOLIA_RPC_URL=$(get_env_value "SEPOLIA_RPC_URL")
CONTRACT_ADDRESS_SEPOLIA=$(get_env_value "CONTRACT_ADDRESS_SEPOLIA")
PINATA_API_KEY=$(get_env_value "PINATA_API_KEY")
PINATA_SECRET_API_KEY=$(get_env_value "PINATA_SECRET_API_KEY")
PINATA_JWT_TOKEN=$(get_env_value "PINATA_JWT_TOKEN")
CORS_ORIGINS=$(get_env_value "CORS_ORIGINS")

# 前端构建期变量：后端源地址。
# NEXT_PUBLIC_* 会在构建时被内联进前端产物，改动后必须重新部署才生效。
# 必须是「源地址」，不能带 /api 后缀（前端代码已统一拼成 ${源地址}/api/xxx）。
NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-https://meditrace.baozaolaoba.top}"

# 显示读取到的变量（部分隐藏）
echo "已读取以下环境变量:"
echo "  - USE_SEPOLIA: $USE_SEPOLIA"
echo "  - SEPOLIA_RPC_URL: ${SEPOLIA_RPC_URL:0:30}..."
echo "  - CONTRACT_ADDRESS_SEPOLIA: $CONTRACT_ADDRESS_SEPOLIA"
echo "  - PINATA_API_KEY: ${PINATA_API_KEY:0:10}..."
echo "  - PINATA_SECRET_API_KEY: ${PINATA_SECRET_API_KEY:0:10}..."
echo "  - PINATA_JWT_TOKEN: ${PINATA_JWT_TOKEN:0:20}..."
echo "  - CORS_ORIGINS: $CORS_ORIGINS"
echo "  - NEXT_PUBLIC_BACKEND_URL: $NEXT_PUBLIC_BACKEND_URL"
echo ""

# 检查 DATABASE_URL
DATABASE_URL=$(get_env_value "DATABASE_URL")
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  WARNING: DATABASE_URL 未在 .env 文件中找到!"
    echo ""
    echo "生产环境需要 Neon PostgreSQL 数据库。"
    echo "请从以下来源获取 DATABASE_URL:"
    echo "  1. 登录 Neon (https://neon.tech)"
    echo "  2. 选择你的数据库项目"
    echo "  3. 复制 Connection string (包含 password)"
    echo ""
    read -p "请输入 DATABASE_URL (Neon PostgreSQL 连接字符串): " DATABASE_URL
    echo ""
else
    echo "✅ DATABASE_URL 已找到: ${DATABASE_URL:0:30}..."
    echo ""
fi

# 添加环境变量到 Vercel
echo "=========================================="
echo "步骤 3: 设置 Vercel 环境变量"
echo "=========================================="
echo ""

# 使用 --force 标志覆盖已存在的变量
echo "添加 DATABASE_URL (如果已存在则覆盖)..."
vercel env add DATABASE_URL production --force <<< "$DATABASE_URL"

echo "添加 USE_SEPOLIA..."
vercel env add USE_SEPOLIA production --force <<< "$USE_SEPOLIA"

echo "添加 SEPOLIA_RPC_URL..."
vercel env add SEPOLIA_RPC_URL production --force <<< "$SEPOLIA_RPC_URL"

echo "添加 CONTRACT_ADDRESS_SEPOLIA..."
vercel env add CONTRACT_ADDRESS_SEPOLIA production --force <<< "$CONTRACT_ADDRESS_SEPOLIA"

echo "添加 PINATA_API_KEY..."
vercel env add PINATA_API_KEY production --force <<< "$PINATA_API_KEY"

echo "添加 PINATA_SECRET_API_KEY..."
vercel env add PINATA_SECRET_API_KEY production --force <<< "$PINATA_SECRET_API_KEY"

echo "添加 PINATA_JWT_TOKEN..."
vercel env add PINATA_JWT_TOKEN production --force <<< "$PINATA_JWT_TOKEN"

echo "添加 CORS_ORIGINS..."
vercel env add CORS_ORIGINS production --force <<< "$CORS_ORIGINS"

echo "添加 NEXT_PUBLIC_BACKEND_URL (前端构建期内联，指向同域名后端)..."
vercel env add NEXT_PUBLIC_BACKEND_URL production --force <<< "$NEXT_PUBLIC_BACKEND_URL"

echo ""
echo "✅ 所有环境变量已设置完成!"

echo ""
echo "=========================================="
echo "步骤 3: 部署到 Vercel"
echo "=========================================="
echo ""
read -p "是否现在部署？(y/n): " deploy_confirm

if [ "$deploy_confirm" = "y" ]; then
    echo "开始部署..."
    vercel --prod
    echo ""
    echo "✅ 部署完成!"
    echo ""
    echo "获取部署 URL:"
    vercel ls
else
    echo "部署已取消"
fi

echo ""
echo "=========================================="
echo "步骤 4: 验证部署"
echo "=========================================="
echo ""
echo "请手动执行以下命令验证部署:"
echo ""
echo "  # 检查后端健康"
echo "  curl https://your-vercel-domain.vercel.app/api/health"
echo ""
echo "  # 访问前端"
echo "  open https://your-vercel-domain.vercel.app"
echo ""
