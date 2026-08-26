# MediTrace 编码规范

本文档定义了 MediTrace 项目的编码标准和最佳实践。

---

## 通用原则

### 1. 命名约定

#### Python 后端
- **变量/函数**: snake_case（如 `diagnosis_id`, `get_history`）
- **类名**: PascalCase（如 `DiagnosisRecord`, `IPFSClient`）
- **常量**: UPPER_SNAKE_CASE（如 `MAX_RETRIES = 3`）
- **私有成员**: 前缀下划线（如 `_upload_to_pinata`）

#### TypeScript/JavaScript 前端
- **变量/函数**: camelCase（如 `diagnosisId`, `fetchHistory`）
- **组件**: PascalCase（如 `HistoryPage`, `DownloadButton`）
- **常量**: UPPER_SNAKE_CASE 或 const 命名空间

#### Solidity 智能合约
- **变量/函数**: mixedCase（如 `dataHash`, `recordDiagnosis`）
- **合约/结构**: PascalCase（如 `DiagnosisRecord`, `Record`）
- **常量**: UPPER_SNAKE_CASE

### 2. API 响应格式

- **所有 API 响应使用 camelCase** 字段名（前端友好）
- **内部代码使用 snake_case**（Python 惯例）
- 使用 Pydantic 的 `Field(alias=...)` 进行转换

示例：
```python
# 内部字段名（snake_case）
class HistoryRecord(BaseModel):
    diagnosis_id: str = Field(..., alias="diagnosisId")
    ipfs_cid: Optional[str] = Field(None, alias="ipfsCid")
```

---

## Python 后端规范

### 3. 代码结构

#### 3.1 文件组织
```
src/backend/
├── main.py              # FastAPI 应用入口
├── models.py            # 数据模型
├── deepseek_client.py   # AI 客户端
├── blockchain_client.py # 区块链客户端
├── ipfs_service.py      # IPFS 服务
└── utils/
    └── hex_utils.py     # 工具函数
```

#### 3.2 函数设计
- **单一职责**: 每个函数只做一件事
- **长度限制**: 函数不超过 50 行
- **参数数量**: 不超过 5 个参数（超过则使用数据类）
- **类型注解**: 所有函数必须有类型注解

```python
# ✅ 好
async def upload_report(
    report_bytes: bytes,
    filename: str
) -> Optional[str]:
    """上传报告到 IPFS"""
    pass

# ❌ 避免
def upload(a, b, c, d, e):  # 无类型注解，参数过多
    pass
```

### 4. 错误处理

- **使用特定异常**: 避免裸 `except Exception`
- **记录错误**: 使用 `print(f"⚠️ 错误描述：{e}")`
- **用户友好**: API 返回有意义的错误消息

```python
try:
    result = await ipfs.upload(data)
except httpx.TimeoutException:
    print(f"⚠️ IPFS 上传超时：{ipfs_cid}")
    return None
except Exception as e:
    print(f"⚠️ IPFS 上传失败：{type(e).__name__}: {str(e)[:100]}")
    return None
```

### 5. 日志规范

- **使用表情符号前缀**:
  - `✅` 成功操作
  - `⚠️` 警告
  - `❌` 错误
  - `🔍` 调试信息
  - `✓` 一般信息

```python
print(f"✓ 报告已上传 IPFS: {ipfs_cid}")
print(f"⚠️ 上链失败：{chain_result.get('error')}")
```

---

## TypeScript 前端规范

### 6. React 组件

#### 6.1 组件结构
```typescript
interface Props {
  diagnosisId: string;
  onVerify: (id: string) => void;
}

export const VerifyButton: React.FC<Props> = ({ diagnosisId, onVerify }) => {
  // 组件逻辑
  return <button>...</button>;
};
```

#### 6.2 状态管理
- **优先使用局部状态**: 避免不必要的全局状态
- **使用 TypeScript 接口**: 定义清晰的类型
- **避免内联样式**: 使用 Tailwind CSS 类

### 7. 错误处理

```typescript
try {
  const response = await fetch(url);
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData?.detail || "请求失败");
  }
  const data = await response.json();
} catch (error) {
  console.error("操作失败:", error);
  alert(error instanceof Error ? error.message : "操作失败");
}
```

---

## Solidity 智能合约规范

### 8. 合约设计

#### 8.1 结构
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ContractName
 * @dev 功能描述
 */
contract ContractName {
    // 状态变量
    mapping(bytes32 => Record) public records;
    
    // 事件
    event RecordCreated(bytes32 indexed id, address indexed owner);
    
    // 外部函数
    function createRecord(...) external returns (...) {
        // 实现
    }
}
```

#### 8.2 安全实践
- **使用 `indexed` 事件参数**: 便于 off-chain 查询
- **检查 - 影响 - 交互模式**: 避免重入攻击
- **使用 `Ownable`**: 管理访问控制

---

## 代码审查检查清单

### 代码异味（Code Smells）

审查时应注意以下 Fowler 代码异味：

| 异味 | 描述 | 修复方法 |
|------|------|----------|
| **Mysterious Name** | 名称不清晰 | 重命名为有意义的名字 |
| **Duplicated Code** | 重复代码 | 提取公共函数 |
| **Feature Envy** | 过度依赖其他对象数据 | 移动方法到正确位置 |
| **Data Clumps** | 参数频繁一起出现 | 封装为数据类 |
| **Primitive Obsession** | 过度使用原始类型 | 创建专用类型 |
| **Repeated Switches** | 重复的条件判断 | 使用多态或映射 |
| **Shotgun Surgery** | 一处修改多处影响 | 集中相关代码 |
| **Divergent Change** | 一个文件多个原因修改 | 拆分模块 |
| **Speculative Generality** | 不必要的抽象 | 删除多余代码 |
| **Message Chains** | 长链式调用 | 封装中间对象 |
| **Middle Man** | 只委托的类/函数 | 直接调用目标 |
| **Refused Bequest** | 忽略继承的行为 | 使用组合替代 |

### 审查流程

1. **功能正确性**: 代码是否实现需求？
2. **命名清晰**: 变量/函数名是否易懂？
3. **代码简洁**: 是否避免重复？
4. **错误处理**: 是否处理异常情况？
5. **测试覆盖**: 是否有相应测试？
6. **文档完整**: 是否有必要注释？

---

## 工具配置

### 推荐的开发工具

| 工具 | 用途 | 配置 |
|------|------|------|
| **Python** | 后端开发 | Black + isort + mypy |
| **TypeScript** | 前端开发 | ESLint + Prettier |
| **Solidity** | 智能合约 | Solhint + Prettier Solidity |
| **Git** | 版本控制 | Commitlint + Husky |

### 预提交钩子

```bash
# 安装 Husky
cd src/frontend
npm install -D husky lint-staged
npx husky install

# 配置 pre-commit
npx husky add .husky/pre-commit "npx lint-staged"
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2024-08-26 | 初始版本 |

---

## 参考资源

- [PEP 8 - Python Style Guide](https://pep8.org/)
- [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)
- [Solidity Style Guide](https://docs.soliditylang.org/en/v0.8.0/style-guide.html)
- [Refactoring by Martin Fowler](https://refactoring.com/)
