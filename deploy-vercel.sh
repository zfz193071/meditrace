#!/bin/bash
# Vercel 全栈部署脚本

echo "🚀 MediTrace Vercel 全栈部署"
echo "================================"

# 检查是否已登录 Vercel
if ! vercel whoami &>/dev/null; then
    echo "❌ 未登录 Vercel，请先登录..."
    vercel login
fi

# 设置环境变量（首次部署需要）
echo ""
echo "📝 设置环境变量..."
echo "请在 Vercel Dashboard 手动设置以下环境变量："
echo ""
echo "必需变量："
echo "  - DATABASE_URL (Neon PostgreSQL 连接字符串)"
echo "  - DEEPSEEK_API_KEY"
echo "  - PINATA_API_KEY"
echo "  - PINATA_SECRET_API_KEY"
echo "  - PINATA_JWT_TOKEN"
echo ""
echo "可选变量："
echo "  - USE_SEPOLIA=true"
echo "  - SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com"
echo "  - CONTRACT_ADDRESS_SEPOLIA=0x860418e7713A346c829Bc539C93c7A2d576897C5"
echo "  - CORS_ORIGINS=https://meditrace.baozaolaoba.top"
echo ""

# 询问是否继续
read -p "是否继续部署？(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 部署已取消"
    exit 1
fi

# 部署到 Vercel
echo ""
echo "📦 部署到 Vercel..."
vercel --prod

echo ""
echo "✅ 部署完成！"
echo ""
echo "📋 后续步骤："
echo "1. 在 Vercel Dashboard 设置环境变量"
echo "2. 访问 https://<your-vercel-domain>.vercel.app/api/health 测试后端"
echo "3. 配置自定义域名（可选）"
echo ""
echo "📖 详细文档：VERCEL-FULLSTACK-DEPLOYMENT.md"
