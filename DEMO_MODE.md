# 演示模式配置说明

## 🎯 功能概述

为了**避免线上部署时消耗 DeepSeek API token**，系统实现了智能环境检测机制：

| 环境 | 配置 | AI 回复来源 | 成本 |
|------|------|-----------|------|
| **本地开发** | `DEEPSEEK_API_KEY` 已设置 | 真实 DeepSeek API | 消耗 token |
| **线上部署** | `DEEPSEEK_API_KEY` 未设置 | 模拟回复 | **0 成本** |

---

## 🚀 工作原理

### 后端自动切换

```python
# src/backend/main.py

deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

if deepseek_api_key:
    # 本地开发模式：使用真实 DeepSeek API
    deepseek_client = get_deepseek_client()
    diagnosis_result = await deepseek_client.diagnose_with_context(...)
else:
    # 线上部署模式：使用模拟回复（不消耗 token）
    diagnosis_result = get_mock_diagnosis_result(...)
```

### 前端提示

线上部署时，页面顶部会显示**演示模式提示横幅**：

> ⚠️ 演示模式：AI 回复为模拟内容。真实诊断请咨询专业医生。

---

## 📝 模拟回复逻辑

模拟 AI 会根据用户消息中的关键词生成**更有针对性**的回复：

| 用户消息关键词 | 模拟回复内容 |
|---------------|-------------|
| 发热、发烧、temperature | 上呼吸道感染、病毒性感冒 |
| 头痛、头疼、headache | 紧张性头痛 |
| 肚子、腹痛、恶心、呕吐 | 急性胃肠炎 |
| 其他 | 需要进一步评估（默认） |

这样可以保持对话的**真实感**，同时**0 成本**。

---

## 🔧 部署配置

### Render 部署（线上）

**不需要**在 Render 环境变量中设置 `DEEPSEEK_API_KEY`：

```bash
# Render 环境变量（示例）
CONTRACT_ADDRESS_SEPOLIA=0x860418e7713A346c829Bc539C93c7A2d576897C5
CORS_ORIGINS=https://your-app.vercel.app
PORT=8000
# ❌ 不要设置 DEEPSEEK_API_KEY
```

### 本地开发

在 `src/backend/.env` 文件中设置：

```bash
# src/backend/.env
DEEPSEEK_API_KEY=your_actual_api_key_here
CONTRACT_ADDRESS_SEPOLIA=0x860418e7713A346c829Bc539C93c7A2d576897C5
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
PORT=8000
```

---

## ✅ 验证方法

### 本地开发验证

```bash
cd src/backend
source venv/bin/activate
python main.py

# 发送测试消息
curl -X POST http://localhost:8000/api/conversations/test/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "我最近有点发热"}'
```

**预期输出**：真实 DeepSeek AI 回复

### 线上部署验证

1. 确保 Render 上**没有**设置 `DEEPSEEK_API_KEY`
2. 访问部署的网站
3. 发送消息

**预期输出**：
- 页面顶部显示"演示模式"提示横幅
- AI 回复为模拟内容
- 后端日志显示：`ℹ️ 演示模式：使用模拟 AI 回复（DEEPSEEK_API_KEY 未设置）`

---

## 🔄 切换模式

### 从演示模式 → 真实 AI

在 Render 环境变量中添加 `DEEPSEEK_API_KEY`，然后重启服务。

### 从真实 AI → 演示模式

在 Render 环境变量中**删除** `DEEPSEEK_API_KEY`，然后重启服务。

---

## 📊 成本对比

| 模式 | 每月调用次数 | 成本 |
|------|------------|------|
| **演示模式** | 无限 | **$0** |
| 真实 AI（DeepSeek） | 1000 次 | ~$10-20 |
| 真实 AI（DeepSeek） | 10000 次 | ~$100-200 |

---

## ⚠️ 注意事项

1. **演示模式不是真正的医疗诊断**
   - 模拟回复仅供展示功能
   - 必须明确告知用户这是演示
   - 不能用于实际医疗建议

2. **本地开发时记得设置 API Key**
   - 否则也会使用模拟回复
   - 检查 `.env` 文件是否存在

3. **线上部署前确认配置**
   - 检查 Render 环境变量
   - 确认没有意外设置 `DEEPSEEK_API_KEY`

---

## 📅 修改记录

- **2026-09-01**: 初始实现演示模式功能
  - 后端：`src/backend/main.py` - 添加 `get_mock_diagnosis_result()` 函数
  - 前端：`src/frontend/app/chat/[id]/page.tsx` - 添加演示模式提示横幅
  - 文档：`DEMO_MODE.md` - 配置说明文档
