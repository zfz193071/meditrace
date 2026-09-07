# MediTrace 部署清单

## 📋 部署前准备

### 1. 域名和服务器
- [ ] 拥有域名 `baozaolaoba.top`（已在 Cloudflare）
- [ ] 准备服务器（VPS）
- [ ] 获取服务器 IP 地址

### 2. Cloudflare 配置
- [ ] 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
- [ ] 选择域名 `baozaolaoba.top`
- [ ] 进入 DNS 设置

---

## 🚀 部署步骤

### 第一步：Cloudflare DNS 配置

在 Cloudflare DNS 中添加记录：

| 类型 | 名称 | 内容 | TTL | 代理状态 |
|------|------|------|-----|---------|
| A | meditrace | 你的服务器 IP | Auto | 🟡 已代理 |

**操作**:
1. 点击 "添加记录"
2. 类型选择 "A"
3. 名称输入 "meditrace"
4. 内容输入服务器 IP
5. 代理状态选择 "已代理"（橙色云）
6. 点击 "保存"

---

### 第二步：服务器环境准备

```bash
# 1. 更新系统
sudo apt update && sudo apt upgrade -y

# 2. 安装 Node.js (如果未安装)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 3. 安装 Python 3.10+ (通常已预装)
python3 --version

# 4. 安装 Nginx
sudo apt install -y nginx

# 5. 安装 Certbot (SSL 证书)
sudo apt install -y certbot python3-certbot-nginx

# 6. 安装 PM2 (进程管理)
sudo npm install -g pm2

# 7. 安装 Git
sudo apt install -y git
```

---

### 第三步：部署项目代码

```bash
# 1. 克隆项目（或使用 SCP/SFTP 上传）
cd /var/www
sudo git clone <your-repo-url> meditrace
sudo chown -R $USER:$USER meditrace
cd meditrace

# 2. 安装前端依赖
cd src/frontend
pnpm install

# 3. 创建前端环境变量
cat > .env.production << EOF
NEXT_PUBLIC_BACKEND_URL=https://meditrace.baozaolaoba.top/api
NEXT_PUBLIC_CONTRACT_ADDRESS=0x860418e7713A346c829Bc539C93c7A2d576897C5
NEXT_PUBLIC_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com
EOF

# 4. 构建前端
pnpm build

# 5. 安装后端依赖（使用虚拟环境）
cd ../backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. 验证后端依赖
./venv/bin/python -c "import httpx; print('✓ httpx 已安装')"

# 7. 确认 .env 文件已配置
# 检查是否有 DEEPSEEK_API_KEY 等必要配置
```

---

### 第四步：配置 Nginx

创建配置文件 `/etc/nginx/sites-available/meditrace`:

```bash
sudo nano /etc/nginx/sites-available/meditrace
```

粘贴以下内容：

```nginx
server {
    listen 80;
    server_name meditrace.baozaolaoba.top;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name meditrace.baozaolaoba.top;
    
    ssl_certificate /etc/letsencrypt/live/meditrace.baozaolaoba.top/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/meditrace.baozaolaoba.top/privkey.pem;
    
    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # 后端 API
    location /api {
        rewrite ^/api(.*)$ $1 break;
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/meditrace /etc/nginx/sites-enabled/

# 移除默认配置（可选）
sudo rm /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

---

### 第五步：获取 SSL 证书

```bash
sudo certbot --nginx -d meditrace.baozaolaoba.top
```

按照提示：
1. 输入邮箱（用于证书更新通知）
2. 同意服务条款
3. 选择是否分享邮箱到 EFF（可选）
4. 选择是否自动重定向 HTTP→HTTPS（推荐选 Yes）

---

### 第六步：启动服务（PM2）

```bash
# 回到项目根目录
cd /var/www/meditrace

# 创建 PM2 配置文件
cat > ecosystem.config.js << EOF
module.exports = {
  apps: [
    {
      name: 'meditrace-frontend',
      cwd: './src/frontend',
      script: 'pnpm',
      args: 'start',
      env: {
        NODE_ENV: 'production',
        PORT: 3000
      }
    },
    {
      name: 'meditrace-backend',
      cwd: './src/backend',
      script: './venv/bin/python',
      args: 'main.py',
      env: {
        PYTHONUNBUFFERED: '1'
      }
    }
  ]
};
EOF

# 启动服务
pm2 start ecosystem.config.js

# 保存 PM2 配置（开机自启）
pm2 save

# 设置 PM2 开机自启
pm2 startup
# 按提示执行输出的命令
```

---

### 第七步：验证部署

#### 1. 检查服务状态
```bash
pm2 status
pm2 logs meditrace-frontend
pm2 logs meditrace-backend
```

#### 2. 访问网站
- 打开浏览器访问：https://meditrace.baozaolaoba.top
- 检查页面是否正常加载

#### 3. 测试 API
```bash
# 测试后端健康检查
curl https://meditrace.baozaolaoba.top/api/health
```

#### 4. 测试 AI 对话功能
- ⚠️ **需要手动测试**（根据项目规则，禁止自动对话测试）
- 在浏览器中访问 https://meditrace.baozaolaoba.top
- 输入症状，点击发送
- 检查 AI 是否正常回复

---

## 🔧 常见问题

### 前端无法加载
```bash
# 检查前端是否运行
pm2 logs meditrace-frontend

# 重启前端
pm2 restart meditrace-frontend
```

### 后端 API 无响应
```bash
# 检查后端是否运行
pm2 logs meditrace-backend

# 重启后端
pm2 restart meditrace-backend

# 检查虚拟环境是否正确激活
cd src/backend
source venv/bin/activate
python main.py  # 手动测试启动
```

### SSL 证书问题
```bash
# 重新获取证书
sudo certbot --nginx -d meditrace.baozaolaoba.top

# 测试证书续期
sudo certbot renew --dry-run
```

### Nginx 配置错误
```bash
# 测试配置
sudo nginx -t

# 查看错误日志
sudo tail -f /var/log/nginx/error.log
```

---

## 📊 日常维护

### 查看日志
```bash
pm2 logs
```

### 重启服务
```bash
pm2 restart all
```

### 查看资源使用
```bash
pm2 monit
```

### 更新代码
```bash
git pull
cd src/frontend && pnpm build
pm2 restart all
```

---

## ✅ 部署完成检查

- [ ] Cloudflare DNS 记录已添加
- [ ] Nginx 配置正确
- [ ] SSL 证书已获取
- [ ] 前端服务运行正常
- [ ] 后端服务运行正常
- [ ] 网站可以正常访问
- [ ] AI 对话功能测试通过（手动）

---

**部署完成后，记得将 `.env` 文件中的敏感信息（API Key、私钥等）添加到 Cloudflare 或服务器的安全存储中！**
