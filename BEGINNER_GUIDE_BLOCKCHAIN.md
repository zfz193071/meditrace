# MediTrace 区块链新手入门指南

> 从零开始学习 MetaMask、Sepolia 测试网和区块链上链原理

---

## 📚 目录

1. [什么是区块链？](#1-什么是区块链)
2. [MetaMask 钱包入门](#2-metamask-钱包入门)
3. [Sepolia 测试网详解](#3-sepolia-测试网详解)
4. [获取测试币 (FAUCET)](#4-获取测试币-faucet)
5. [智能合约基础](#5-智能合约基础)
6. [Gas 费用详解](#6-gas-费用详解)
7. [MediTrace 上链流程](#7-meditrace-上链流程)
8. [常见问题排查](#8-常见问题排查)

---

## 1. 什么是区块链？

### 1.1 核心概念

**区块链**是一个去中心化的分布式账本，具有以下特点：

- **不可篡改**：一旦数据上链，几乎无法修改
- **去中心化**：没有单一控制点，由全网节点共同维护
- **透明可追溯**：所有交易公开可查
- **安全性**：使用密码学保证数据安全

### 1.2 区块的结构

```
┌─────────────────────────┐
│  区块头 (Block Header)   │
│  ├─ 前一个区块的哈希     │ ← 链式结构的关键
│  ├─ 时间戳              │
│  ├─ 随机数 (Nonce)       │ ← 挖矿的关键
│  └─ Merkle Root         │ ← 所有交易的摘要
├─────────────────────────┤
│  交易列表 (Transactions) │
│  ├─ 交易 1               │
│  ├─ 交易 2               │
│  └─ ...                 │
└─────────────────────────┘
```

### 1.3 挖矿是什么？

**挖矿**是区块链达成共识的过程：

1. 矿工收集待确认的交易
2. 打包成新区块
3. 通过计算找到满足条件的 Nonce（工作量证明）
4. 广播给全网验证
5. 验证通过后添加到链上

**为什么需要挖矿？**

- 防止恶意攻击
- 保证交易顺序
- 发行新币（区块奖励）

---

## 2. MetaMask 钱包入门

### 2.1 什么是 MetaMask？

MetaMask 是一个以太坊钱包浏览器扩展，让你：

- 存储和管理加密货币
- 与 DApp（去中心化应用）交互
- 签署交易和消息

### 2.2 安装 MetaMask

**步骤 1：访问官网**

```
https://metamask.io/
```

**步骤 2：下载扩展**

- Chrome/Edge: 访问 Chrome 应用商店
- Firefox: 访问 Firefox 附加组件
- 点击"添加至浏览器"

**步骤 3：创建钱包**

1. 点击"创建钱包"
2. 设置强密码（仅本地使用）
3. **重要**：备份助记词（12 个单词）
   - 写在纸上，不要截图
   - 不要告诉任何人
   - 丢失助记词 = 丢失资产

**步骤 4：验证助记词**
按顺序输入 12 个单词，确保备份正确

### 2.3 钱包界面说明

![区块结构图](block_0.png)
![MetaMask 钱包界面](block_1.png)

_图 2：MetaMask 钱包界面 - 显示网络选择、余额显示、发送/接收/购买按钮和账户地址_

```
┌─────────────────────────────┐
│  MetaMask 钱包               │
├─────────────────────────────┤
│  网络：Ethereum Mainnet ▼   │ ← 切换网络
│                             │
│  余额：0.00 ETH             │
│  $0.00                      │
│                             │
│  [发送] [接收] [购买]       │ ← 主要操作
│                             │
│  账户 1                      │
│  0x1234...5678              │ ← 地址
│  [复制]                     │
└─────────────────────────────┘
```

### 2.4 重要概念

**地址（Address）**

- 格式：`0x` 开头的 40 位十六进制
- 示例：`0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb`
- 公开分享，用于接收资金

**私钥（Private Key）**

- 控制钱包的密钥
- **绝对不要分享**
- 可导出为助记词

**助记词（Mnemonic）**

- 12 或 24 个单词
- 私钥的人类可读形式
- 可恢复整个钱包

---

## 3. Sepolia 测试网详解

### 3.1 什么是测试网？

**测试网**是以太坊的测试环境：

- 使用测试币（无真实价值）
- 模拟主网行为
- 用于开发和测试

**为什么需要测试网？**

- 避免在主网测试时损失真实资金
- 验证智能合约逻辑
- 学习区块链交互

### 3.2 以太坊网络类型

| 网络类型                   | RPC URL        | 币的价值    | 用途     |
| -------------------------- | -------------- | ----------- | -------- |
| 主网 (Mainnet)             | 官方节点       | 💰 真实价值 | 生产环境 |
| Sepolia                    | 测试节点       | 🎮 免费测试 | 开发测试 |
| 本地开发 (Ganache/Hardhat) | localhost:8545 | 🎮 无限生成 | 本地调试 |

### 3.3 在 MetaMask 中添加 Sepolia

**方法 1：使用 Chainlist（推荐）**

1. 访问 https://chainlist.org/
2. 连接 MetaMask
3. 搜索"Sepolia"
4. 点击"Add to MetaMask"

**方法 2：手动添加**

1. 打开 MetaMask
2. 点击网络下拉菜单
3. 点击"添加网络"
4. 填写信息：
   ```
   网络名称：Sepolia Testnet
   新 RPC URL：https://ethereum-sepolia-rpc.publicnode.com
   链 ID：11155111
   货币符号：ETH
   区块浏览器 URL：https://sepolia.etherscan.io
   ```

### 3.4 MediTrace 中的 Sepolia 配置

在 `src/backend/.env` 中：

```bash
# 启用 Sepolia 测试网
USE_SEPOLIA=true

# Sepolia RPC URL
SEPOLIA_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com

# 后端使用的账户私钥（仅用于上链）
SEPOLIA_PRIVATE_KEY=7e4cffc5275557070d807f772f65312bc9e561a92bad19c474871f663291f705

# 已部署的智能合约地址
CONTRACT_ADDRESS_SEPOLIA=0x860418e7713A346c829Bc539C93c7A2d576897C5
```

**⚠️ 安全警告**

- 上述私钥仅用于测试网
- 主网私钥必须严格保密
- 定期轮换测试私钥

---

## 4. 获取测试币 (FAUCET)

### 4.1 什么是 Faucet？

**Faucet（水龙头）**是免费分发测试币的服务，用于：

- 支付 Gas 费用
- 测试交易功能

### 4.2 Sepolia Faucet 列表

**官方 Faucet（推荐）**

```
https://sepoliafaucet.com/
```

- 需要 GitHub 账号
- 每日限额：0.5 ETH

**Alchemy Faucet**

```
https://sepoliafaucet.com/
```

- 需要 Alchemy 账号
- 每日限额：0.25 ETH

**Infura Faucet**

```
https://www.infura.io/faucet/sepolia
```

- 需要 Infura 账号
- 每日限额：0.5 ETH

### 4.3 领取测试币步骤

1. 打开 Faucet 网站
2. 连接 MetaMask 钱包
3. 输入你的钱包地址
4. 完成人机验证
5. 点击"请求测试币"
6. 等待几秒到几分钟
7. 在 MetaMask 中查看余额

### 4.4 查看交易

交易确认后，可以在区块浏览器查看：

```
https://sepolia.etherscan.io/address/<你的地址>
```

示例：

```
https://sepolia.etherscan.io/address/0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
```

---

## 5. 智能合约基础

### 5.1 什么是智能合约？

**智能合约**是运行在区块链上的程序：

- 自动执行预设规则
- 不可篡改
- 公开透明

### 5.2 MediTrace 的智能合约

合约地址：`0x860418e7713A346c829Bc539C93c7A2d576897C5`（Sepolia）

**合约功能：**

```solidity
// 记录诊断信息
function recordDiagnosis(
    bytes32 _dataHash,     // 数据哈希
    string memory _modelVersion,  // 模型版本
    string memory _ipfsCid,       // IPFS CID
    address _patient               // 患者地址
) returns (bytes32)

// 查询诊断记录
function getRecord(bytes32 _diagnosisId) returns (Record memory)

// 获取患者的所有记录
function getPatientRecords(address _patient) returns (bytes32[] memory)
```

### 5.3 合约数据结构

```solidity
struct Record {
    bytes32 dataHash;        // 诊断数据 SHA-256 哈希
    string modelVersion;     // 模型版本 (如 "v1.0.0")
    uint256 timestamp;       // 时间戳
    string ipfsCid;          // IPFS 报告 CID
    address patient;         // 患者钱包地址
}

// 主映射：diagnosisId => Record
mapping(bytes32 => Record) public records;

// 患者记录列表：patient => diagnosisId[]
mapping(address => bytes32[]) public patientRecords;
```

### 5.4 查看合约

在 Etherscan 上查看合约：

```
https://sepolia.etherscan.io/address/0x860418e7713A346c829Bc539C93c7A2d576897C5
```

可以查看：

- 合约代码（如果已验证）
- 交易记录
- 事件日志
- 读取合约数据

---

## 6. Gas 费用详解

### 6.1 什么是 Gas？

**Gas**是以太坊网络的手续费：

- 支付矿工/验证者
- 防止网络滥用
- 按计算复杂度收费

### 6.2 Gas 计算

```
总费用 = Gas 用量 × Gas 价格

Gas 用量：执行交易所需的计算步骤
Gas 价格：每单位 Gas 愿意支付的费用（Gwei）
```

**示例：**

```
Gas 用量：100,000
Gas 价格：30 Gwei (0.000000030 ETH)
总费用：100,000 × 30 = 3,000,000 Gwei = 0.003 ETH
```

### 6.3 EIP-1559 费用市场

Sepolia 使用 EIP-1559 费用模型：

![Gas 费用计算](block_2.png)

_图 3：Gas 费用计算示意图 - 展示基础费用 (Base Fee)、优先费用 (Priority Fee) 和总费用的关系_

```
总费用 = (基础费用 + 优先费用) × Gas 用量

基础费用 (Base Fee)：网络自动调整
优先费用 (Priority Fee)：给验证者的小费
```

**MediTrace 后端配置：**

```python
# 获取基础费用
latest_block = self.w3.eth.get_block('latest')
base_fee = latest_block['baseFeePerGas']

# 获取优先费用
max_priority_fee = self.w3.eth.max_priority_fee

# 计算最大费用
max_fee_per_gas = base_fee * 2 + max_priority_fee
```

### 6.4 节省 Gas 的技巧

1. **批量操作**：减少交易次数
2. **选择低峰期**：网络不拥堵时 Gas 便宜
3. **优化合约**：减少存储操作
4. **使用 Layer 2**：更低费用的侧链

---

## 7. MediTrace 上链流程

### 7.1 完整流程图

![上链流程图](block_3.png)

_图 4：MediTrace 完整上链流程图 - 从用户诊断到报告下载的全流程_

```
┌─────────────┐
│  用户诊断   │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│  生成诊断报告    │
│  (PDF + JSON)    │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  上传到 IPFS      │
│  Pinata 服务      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  获取 IPFS CID    │
│  QmXxx...        │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  计算数据哈希    │
│  SHA-256         │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  调用智能合约    │
│  recordDiagnosis │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  支付 Gas 费用    │
│  发送交易        │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  等待确认        │
│  ~15 秒/区块      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  交易上链成功    │
│  返回 diagnosisId│
└──────────────────┘
```

### 7.2 步骤详解

#### 步骤 1：生成诊断报告

后端生成 JSON 和 PDF 报告：

```python
report_data = {
    "symptoms": symptoms,
    "suggestions": suggestions,
    "timestamp": datetime.now(),
    "modelVersion": "v1.0.0"
}
```

#### 步骤 2：上传到 IPFS

使用 Pinata API 上传：

```python
import requests

response = requests.post(
    "https://api.pinata.cloud/pinning/pinFileToIPFS",
    headers={"Authorization": f"Bearer {PINATA_JWT_TOKEN}"},
    files={"file": pdf_bytes}
)

ipfs_cid = response.json()["IpfsHash"]
# 示例：QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG
```

#### 步骤 3：计算数据哈希

```python
import hashlib

data_string = json.dumps(report_data, sort_keys=True)
data_hash = hashlib.sha256(data_string.encode()).hexdigest()
# 示例：a3f5e8d9c2b1...
```

#### 步骤 4：调用智能合约

```python
# 构建交易
tx = contract.functions.recordDiagnosis(
    data_hash_bytes,      # bytes32 格式
    "v1.0.0",            # 模型版本
    ipfs_cid,            # IPFS CID
    patient_address      # 患者地址
).build_transaction({
    'from': account_addr,
    'nonce': nonce,
    'gas': estimated_gas,
    'maxFeePerGas': max_fee,
    'maxPriorityFeePerGas': priority_fee,
})

# 签名交易
signed_tx = w3.eth.account.sign_transaction(tx, private_key)

# 发送交易
tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
```

#### 步骤 5：等待确认

```python
# 等待交易 receipt
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

# 从事件中提取 diagnosisId
diagnosis_id = extract_diagnosis_id(tx_receipt)
```

#### 步骤 6：返回结果

```python
return {
    "success": True,
    "txHash": tx_hash,
    "diagnosisId": diagnosis_id,
    "blockNumber": tx_receipt['blockNumber']
}
```

### 7.3 前端展示

用户在历史记录页面看到：

```
┌─────────────────────────────────────┐
│  诊断 ID                             │
│  ✓ 已上链                           │
│  0xda49dba7...f1a74b0c             │
│                                     │
│  2024/08/26 22:57                   │
│                                     │
│  可能疾病：                         │
│  [肺炎] [肺结核]                    │
│                                     │
│  [🔍 验证记录] [📄 下载报告]        │
└─────────────────────────────────────┘
```

点击"下载报告"会：

1. 显示 loading 效果
2. 从 IPFS 下载 PDF
3. 自动保存到本地

---

## 8. 常见问题排查

### 8.1 常见问题

#### Q1: MetaMask 显示"连接超时"

**原因**：RPC 节点不可用

**解决**：

1. 切换到其他 RPC URL
2. 检查网络连接
3. 尝试官方节点

#### Q2: 交易失败"Insufficient funds"

**原因**：Gas 费用不足

**解决**：

1. 检查余额
2. 从 Faucet 获取更多测试币
3. 降低 Gas 价格（如果允许）

#### Q3: 交易长时间"Pending"

**原因**：Gas 价格过低

**解决**：

1. 等待网络拥堵缓解
2. 使用"加速交易"功能
3. 重新发送更高的 Gas 价格

#### Q4: 合约调用失败

**原因**：

- 合约参数错误
- Gas 不足
- 合约逻辑错误

**解决**：

1. 检查参数格式
2. 增加 Gas 限制
3. 查看事件日志中的错误信息

### 8.2 调试工具

**区块浏览器**

```
Sepolia: https://sepolia.etherscan.io
主网：https://etherscan.io
```

**查看交易详情**

```
https://sepolia.etherscan.io/tx/<交易哈希>
```

**查看合约事件**

```
https://sepolia.etherscan.io/address/<合约地址>#events
```

### 8.3 后端日志

查看上链过程日志：

```bash
cd src/backend
source venv/bin/activate
python main.py

# 成功时输出：
# ✓ 诊断已上链：0x1234...
# ✓ 链上诊断 ID: 0x5678...

# 失败时输出：
# ⚠️ 上链失败：错误信息
```

### 8.4 环境变量检查

确保 `.env` 配置正确：

```bash
# 检查是否启用 Sepolia
grep USE_SEPOLIA .env

# 检查 RPC URL
grep SEPOLIA_RPC_URL .env

# 检查私钥（⚠️ 注意保密）
grep SEPOLIA_PRIVATE_KEY .env

# 检查合约地址
grep CONTRACT_ADDRESS_SEPOLIA .env
```

---

## 📚 学习资源

### 官方文档

- [以太坊官网](https://ethereum.org/)
- [MetaMask 文档](https://docs.metamask.io/)
- [Solidity 文档](https://docs.soliditylang.org/)
- [Sepolia 测试网](https://sepolia.org/)

### 开发工具

- [Remix IDE](https://remix.ethereum.org/) - 在线合约开发
- [Hardhat](https://hardhat.org/) - 本地开发环境
- [Foundry](https://book.getfoundry.sh/) - Rust 开发框架

### 学习课程

- [CryptoZombies](https://cryptozombies.io/) - 游戏化学习 Solidity
- [Speed Run Ethereum](https://speedrunethereum.com/) - 实战项目

---

## ✅ 检查清单

在继续开发前，确保完成以下检查：

- [ ] 安装并配置 MetaMask
- [ ] 创建钱包并备份助记词
- [ ] 添加 Sepolia 测试网
- [ ] 从 Faucet 获取测试币（至少 1 ETH）
- [ ] 在 Sepolia 上查看自己的地址
- [ ] 理解 Gas 费用概念
- [ ] 阅读智能合约代码
- [ ] 成功执行一次上链操作
- [ ] 在 Etherscan 上验证交易

---

## 📞 获取帮助

遇到问题？

1. 查看 [常见问题排查](#8-常见问题排查)
2. 检查后端日志输出
3. 在 Etherscan 上查看交易状态
4. 参考项目文档：`docs/adr/0003-blockchain-design.md`

---

**最后更新**: 2024-08-27  
**文档版本**: 1.0
