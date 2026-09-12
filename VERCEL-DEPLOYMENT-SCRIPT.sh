#!/bin/bash
# MediTrace Vercel 部署脚本
# 注意：需要先安装 Vercel CLI

set -e

echo "=========================================="
echo "MediTrace Vercel 全栈部署脚本"
echo "=========================================="

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
echo "步骤 2: 设置环境变量"
echo "=========================================="
echo ""
echo "请依次输入以下环境变量值:"
echo ""

# 读取 Neon 数据库连接字符串
read -p "请输入 DATABASE_URL (Neon PostgreSQL 连接字符串): " DATABASE_URL
vercel env add DATABASE_URL production <<< "$DATABASE_URL"

# 注意：生产环境不需要 DEEPSEEK_API_KEY，已记录在 AGENTS.md

# 区块链相关配置
read -p "请输入 USE_SEPOLIA (输入 true): " USE_SEPOLIA
vercel env add USE_SEPOLIA production <<< "$USE_SEPOLIA"

read -p "请输入 SEPOLIA_RPC_URL: " SEPOLIA_RPC_URL
vercel env add SEPOLIA_RPC_URL production <<< "$SEPOLIA_RPC_URL"

read -p "请输入 CONTRACT_ADDRESS_SEPOLIA: " CONTRACT_ADDRESS_SEPOLIA
vercel env add CONTRACT_ADDRESS_SEPOLIA production <<< "$CONTRACT_ADDRESS_SEPOLIA"

# Pinata IPFS 配置
read -p "请输入 PINATA_API_KEY: " PINATA_API_KEY
vercel env add PINATA_API_KEY production <<< "$PINATA_API_KEY"

read -p "请输入 PINATA_SECRET_API_KEY: " PINATA_SECRET_API_KEY
vercel env add PINATA_SECRET_API_KEY production <<< "$PINATA_SECRET_API_KEY"

read -p "请输入 PINATA_JWT_TOKEN: " PINATA_JWT_TOKEN
vercel env add PINATA_JWT_TOKEN production <<< "$PINATA_JWT_TOKEN"

# CORS 配置
read -p "请输入 CORS_ORIGINS (例如：https://meditrace.baozaolaoba.top): " CORS_ORIGINS
vercel env add CORS_ORIGINS production <<< "$CORS_ORIGINS"

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
