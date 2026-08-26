# Spec 0004: CORS 配置与区块链客户端 API 兼容性修复

**状态**: 已完成  
**日期**: 2024-08-26  
**关联提交**: `b79082a`  
**优先级**: 高 (阻塞功能演示)

---

## 背景

在 MediTrace MVP 开发过程中，发现两个关键问题阻塞了系统的正常运行:

1. **CORS 跨域错误**: 前端 (localhost:3000) 无法调用后端 API (localhost:8000)
2. **区块链客户端 API 不兼容**: web3.py 库的 API 变更导致交易发送失败

这些问题导致诊断记录无法上链，链上验证功能无法使用，严重影响项目演示。

---

## 需求

### 需求 1: 修复 CORS 跨域问题

**用户故事**: 作为前端用户，我希望诊断结果能够成功返回，包括链上交易信息。

**验收标准**:
- [ ] 前端 `http://localhost:3000` 可以成功调用后端 `http://localhost:8000` 的所有 API
- [ ] OPTIONS 预检请求返回正确的 CORS 响应头
- [ ] 生产环境可以配置不同的允许来源列表
- [ ] 暴露必要的响应头供前端访问

**技术约束**:
- CORS 中间件必须在 FastAPI 应用创建后立即添加
- 开发环境允许 localhost:3000 和 localhost:8000
- 支持凭证 (cookies/auth headers)

### 需求 2: 修复区块链客户端 API 兼容性

**用户故事**: 作为系统，我希望诊断记录能够成功写入区块链，确保数据可溯源。

**验收标准**:
- [ ] `recordDiagnosis` 函数成功发送交易到 Sepolia 测试网
- [ ] 交易哈希正确返回并存储
- [ ] 诊断 ID 格式正确 (hex 字符串，以 0x 开头)
- [ ] 链上数据哈希正确转换为可显示格式
- [ ] 账户密钥管理安全 (使用 Account.from_key API)

**技术约束**:
- 使用 web3.py 最新 API (`Account.from_key` 替代 `from_account`)
- 交易构建使用 `build_transaction` + `sign_transaction` 模式
- data_hash 参数必须是 bytes32 类型
- 诊断 ID 从 bytes 转换为 hex 字符串显示

### 需求 3: 前端用户地址管理

**用户故事**: 作为测试用户，我希望能够手动设置钱包地址，方便调试。

**验收标准**:
- [ ] 首页显示用户地址输入框
- [ ] 历史记录页面显示当前用户地址
- [ ] 用户可以修改地址并立即生效
- [ ] 地址格式验证 (以 0x 开头)
- [ ] 生产环境提示集成 MetaMask 等钱包

**技术约束**:
- 开发环境允许手动输入地址
- 生产环境应通过钱包连接获取地址
- 地址状态在页面间共享

---

## 实现细节

### 变更文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/backend/main.py` | 修改 | CORS 配置、患者地址处理、响应格式 |
| `src/backend/blockchain_client.py` | 修改 | web3.py API 适配、交易构建逻辑 |
| `src/backend/models.py` | 修改 | 添加 chainTxHash 字段 |
| `src/frontend/app/page.tsx` | 修改 | 添加用户地址输入 UI |
| `src/frontend/app/history/page.tsx` | 修改 | 添加地址切换功能 |

### 关键代码变更

#### CORS 配置 (main.py)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)
```

#### 区块链交易构建 (blockchain_client.py)
```python
# 1. 将 data_hash 从 hex 字符串转换为 bytes32
if data_hash.startswith('0x'):
    data_hash_bytes = bytes.fromhex(data_hash[2:])
else:
    data_hash_bytes = bytes.fromhex(data_hash)

# 2. 使用 build_transaction 构建交易
tx = self.contract.functions.recordDiagnosis(
    data_hash_bytes,
    model_version,
    ipfs_cid,
    patient_address
).build_transaction({
    'from': account_addr,
    'nonce': nonce,
    'gas': int(gas_estimate * 1.2),
    'gasPrice': gas_price,
})

# 3. 签名并发送交易
signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
```

#### 诊断 ID 格式转换 (main.py)
```python
# 将 bytes 转换为 hex 字符串
diag_id_hex = '0x' + diag_id_bytes.hex()

# dataHash 同样处理
if isinstance(data_hash, bytes):
    data_hash = "0x" + data_hash.hex()
```

---

## 测试验证

### 手动测试步骤

1. **CORS 验证**
   ```bash
   curl -H "Origin: http://localhost:3000" \
        -H "Access-Control-Request-Method: GET" \
        -X OPTIONS -v http://localhost:8000/health
   ```
   预期：返回 `Access-Control-Allow-Origin: http://localhost:3000`

2. **诊断流程测试**
   - 打开 `http://localhost:3000`
   - 输入症状描述
   - 点击"获取诊断建议"
   - 验证返回结果包含 `chainTxHash`

3. **链上验证测试**
   - 复制返回的 `diagnosisId`
   - 访问 `http://localhost:3000/verify?diagnosisId=<id>`
   - 验证显示"验证通过"
   - 点击 Etherscan 链接，交易在 Sepolia 浏览器中可见

4. **历史记录测试**
   - 切换用户地址
   - 验证历史记录列表更新
   - 验证诊断 ID 格式正确 (0x 开头的 hex 字符串)

---

## 已知限制

1. **用户地址管理**: 当前为手动输入，生产环境需要集成钱包连接 (MetaMask/WalletConnect)
2. **CORS 配置**: 开发环境使用硬编码的 localhost 地址，生产环境需要从环境变量读取
3. **Hex 转换逻辑**: 多处重复的 hex 字符串<->bytes 转换，建议提取为工具函数

---

## 后续工作

- [ ] 创建 `utils/hex_utils.py` 封装十六进制转换逻辑
- [ ] 集成 MetaMask 钱包连接
- [ ] 将 CORS 配置移到环境变量
- [ ] 添加单元测试覆盖区块链客户端
- [ ] 添加 E2E 测试覆盖完整诊断流程

---

## 参考资料

- [FastAPI CORS 文档](https://fastapi.tiangolo.com/tutorial/cors/)
- [web3.py Account 文档](https://web3py.readthedocs.io/en/stable/accounts.html)
- [Sepolia 测试网指南](https://sepolia.dev/)
- [Etherscan Sepolia](https://sepolia.etherscan.io/)
