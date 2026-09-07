# MediTrace Vercel 部署配置 (2026)

## 📋 当前状态

### 域名配置
- **自定义域名**: `meditrace.baozaolaoba.top`
- **Vercel 项目**: https://vercel.com/lucyzhus-projects/meditrace
- **后端服务**: https://meditrace-backend.onrender.com

### Cloudflare DNS 配置 ✅ 已完成
| 类型 | 名称 | 目标 | 代理状态 |
|------|------|------|---------|
| CNAME | meditrace | 045d1d3492008e8d.vercel-dns-017.com. | DNS only (灰色云朵) |

---

## 🚀 部署步骤

### 第一步：在 Vercel 设置环境变量

**访问**: https://vercel.com/lucyzhus-projects/meditrace/settings/environment-variables

添加以下三个环境变量（Production 环境）：

| 变量名 | 值 |
|--------|-----|
| `NEXT_PUBLIC_BACKEND_URL` | `https://meditrace-backend.onrender.com` |
| `NEXT_PUBLIC_CONTRACT_ADDRESS` | `0x860418e7713A346c829Bc539C93c7A2d576897C5` |
| `NEXT_PUBLIC_RPC_URL` | `https://ethereum-sepolia-rpc.publicnode.com` |

**操作步骤**:
1. 点击 "Add New" → "Variable"
2. 输入变量名和值
3. 确保 Environment 选择 "Production"
4. 点击 "Save"
5. 重复添加三个变量

---

### 第二步：验证域名连接

**访问**: https://vercel.com/lucyzhus-projects/meditrace/settings/domains

检查状态：
- [ ] 域名 `meditrace.baozaolaoba.top` 已添加
- [ ] 显示 **"Valid Configuration"** ✅
- [ ] SSL 证书状态为 "Generating SSL Certificate" 或 "Ready"

如果显示 "Invalid Configuration"：
1. 等待 5-10 分钟（DNS 传播）
2. 点击 "Refresh" 刷新
3. 检查 Cloudflare DNS 记录是否正确

---

### 第三步：触发重新部署

**访问**: https://vercel.com/lucyzhus-projects/meditrace/deployments

**操作**:
1. 点击 "New Deployment" 按钮
2. 确认配置：
   - Framework Preset: Next.js
   - Root Directory: `./` (或 `./src/frontend` 如果前端在子目录)
   - Build Command: `cd src/frontend && pnpm build`
   - Output Directory: `src/frontend/.next`
3. 点击 "Deploy"

**等待部署完成**（通常 3-5 分钟）

---

### 第四步：验证后端服务

**访问**: https://meditrace-backend.onrender.com/docs

检查：
- [ ] Swagger API 文档可访问
- [ ] `/health` 端点返回健康状态
- [ ] CORS 配置包含 `https://meditrace.baozaolaoba.top`

如果后端无法访问：
1. 检查 Render 服务状态
2. 确认环境变量 `CORS_ORIGINS` 包含 Vercel 域名
3. 查看 Render 日志排查错误

---

### 第五步：验证前端访问

**访问**: https://meditrace.baozaolaoba.top

**检查清单**:
- [ ] 网站可以正常访问（无 404/500 错误）
- [ ] 页面正常加载（Next.js 应用）
- [ ] 打开浏览器控制台 → Network，检查 API 请求
- [ ] API 请求成功（状态码 200）
- [ ] 请求 URL 正确指向 `https://meditrace-backend.onrender.com/api/...`

**手动测试功能**（⚠️ 根据项目规则，禁止自动对话测试）:
- [ ] 页面导航正常
- [ ] 表单可以提交
- [ ] ⚠️ AI 对话功能 - 请手动发送一条消息测试

---

## 🔧 故障排查

### 问题 1: 部署状态显示 "Error"

**查看错误日志**:
1. 访问 Vercel Deployments 页面
2. 点击失败的部署
3. 查看 "Build Logs" 标签页

**常见错误**:

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `pnpm install` 失败 | 依赖冲突 | 检查 `src/frontend/package.json`，删除 `node_modules` 后重试 |
| `pnpm build` 失败 | 代码语法错误 | 本地运行 `pnpm build` 测试，修复错误 |
| 环境变量缺失 | 未设置环境变量 | 在 Vercel Settings → Environment Variables 中添加 |

---

### 问题 2: DNS 未生效

**检查步骤**:
1. **等待 DNS 传播**: 通常 5 分钟 - 几小时
2. **刷新 Vercel Domains 页面**: 点击 "Refresh" 按钮
3. **检查 Cloudflare DNS**:
   - 访问 https://dash.cloudflare.com/.../dns/records
   - 确认 CNAME 记录存在：`meditrace` → `045d1d3492008e8d.vercel-dns-017.com.`

**测试 DNS**:
```bash
# 在终端运行
dig meditrace.baozaolaoba.top
# 或
nslookup meditrace.baozaolaoba.top
```

---

### 问题 3: API 请求失败（CORS 错误）

**检查后端 CORS 配置**:

1. 访问 Render Dashboard
2. 找到 `meditrace-backend` 服务
3. 检查环境变量 `CORS_ORIGINS`

**应该包含**:
```
CORS_ORIGINS=https://meditrace.baozaolaoba.top,https://meditrace.vercel.app
```

**修改方法**:
1. 在 Render Dashboard 修改环境变量
2. 保存后服务会自动重启
3. 等待 1-2 分钟生效

---

### 问题 4: 页面显示空白或 404

**检查**:
1. **前端构建是否成功**: 查看 Vercel 部署日志
2. **路由配置**: 检查 `src/frontend/app` 目录结构
3. **环境变量**: 确认 `NEXT_PUBLIC_BACKEND_URL` 正确设置

**本地测试**:
```bash
cd src/frontend
pnpm install
pnpm build
pnpm start
# 访问 http://localhost:3000 测试
```

---

## 📊 配置总结

### vercel.json 配置
```json
{
  "buildCommand": "cd src/frontend && pnpm build",
  "outputDirectory": "src/frontend/.next",
  "framework": "nextjs",
  "regions": ["hkg1"],
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://meditrace-backend.onrender.com/api/:path*"
    }
  ]
}
```

### Cloudflare DNS 配置
```
Type: CNAME
Name: meditrace
Target: 045d1d3492008e8d.vercel-dns-017.com.
Proxy: DNS only (灰色云朵)
```

### 环境变量
```
NEXT_PUBLIC_BACKEND_URL=https://meditrace-backend.onrender.com
NEXT_PUBLIC_CONTRACT_ADDRESS=0x860418e7713A346c829Bc539C93c7A2d576897C5
NEXT_PUBLIC_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
```

---

## ✅ 完成检查清单

部署完成后，确认以下所有项：

- [ ] Vercel 环境变量已设置（3 个）
- [ ] Vercel 域名显示 "Valid Configuration"
- [ ] Cloudflare DNS CNAME 记录正确
- [ ] Vercel 部署状态为 "Ready"
- [ ] 后端服务 https://meditrace-backend.onrender.com 可访问
- [ ] 网站 https://meditrace.baozaolaoba.top 可正常访问
- [ ] API 请求正常（浏览器控制台检查）
- [ ] AI 对话功能手动测试通过

---

## 📞 链接汇总

| 项目 | 链接 |
|------|------|
| Vercel 项目 | https://vercel.com/lucyzhus-projects/meditrace |
| Vercel 部署 | https://vercel.com/lucyzhus-projects/meditrace/deployments |
| Vercel 域名设置 | https://vercel.com/lucyzhus-projects/meditrace/settings/domains |
| Vercel 环境变量 | https://vercel.com/lucyzhus-projects/meditrace/settings/environment-variables |
| Render 后端 | https://meditrace-backend.onrender.com |
| Render Dashboard | https://dashboard.render.com |
| Cloudflare DNS | https://dash.cloudflare.com/.../baozaolaoba.top/dns/records |
| 网站访问 | https://meditrace.baozaolaoba.top |

---

**部署完成！🎉**

如有问题，请查看：
1. Vercel 部署日志
2. Render 后端日志
3. 浏览器控制台错误信息
