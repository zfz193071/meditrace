"""
区块链客户端
负责与智能合约交互，实现诊断记录上链
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError, TimeExhausted
from eth_typing import HexStr

# 导入工具函数
from utils.hex_utils import ensure_bytes32

load_dotenv(override=True)


class BlockchainClient:
    """区块链客户端"""
    
    def __init__(self):
        # 选择网络：本地开发 or Sepolia 测试网
        self.use_sepolia = os.getenv("USE_SEPOLIA", "false").lower() == "true"
        
        if self.use_sepolia:
            self.rpc_url = os.getenv("SEPOLIA_RPC_URL")
            self.private_key = os.getenv("SEPOLIA_PRIVATE_KEY")
            self.contract_address = os.getenv("CONTRACT_ADDRESS_SEPOLIA")
        else:
            self.rpc_url = os.getenv("BLOCKCHAIN_RPC_URL", "http://localhost:8545")
            self.private_key = os.getenv("BLOCKCHAIN_PRIVATE_KEY")
            self.contract_address = os.getenv("CONTRACT_ADDRESS")
        
        # 验证配置
        if not self.rpc_url:
            raise ValueError("区块链 RPC URL 未配置")
        
        # 初始化 Web3 连接
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        if self.use_sepolia and not self.w3.is_connected():
            raise ConnectionError("无法连接到 Sepolia 网络")
        
        # 加载合约
        self.contract = None
        if self.contract_address:
            self._load_contract()
    
    def _load_contract(self):
        """加载智能合约"""
        try:
            # 读取合约 ABI
            abi_path = "../contracts/artifacts/contracts/DiagnosisRecord.sol/DiagnosisRecord.json"
            import json
            
            with open(abi_path, 'r') as f:
                contract_data = json.load(f)
            
            abi = contract_data['abi']
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=abi
            )
            
        except Exception as e:
            raise RuntimeError(f"加载合约失败：{str(e)}")
    
    def get_account(self):
        """获取当前账户地址"""
        if self.private_key:
            # 使用新的 API: Account.from_key
            account = self.w3.eth.account.from_key(self.private_key)
            return account
        return None
    
    def get_gas_price(self):
        """获取当前 Gas 价格"""
        if self.use_sepolia:
            return int(self.w3.eth.gas_price * 1.2)  # 增加 20% 缓冲
        else:
            return 20000000000  # 本地链固定价格
    
    async def record_diagnosis(
        self,
        data_hash: str,
        model_version: str,
        ipfs_cid: str,
        patient_address: str
    ) -> Dict[str, Any]:
        """
        记录诊断到区块链
        
        Args:
            data_hash: 诊断数据 SHA-256 哈希
            model_version: 模型版本
            ipfs_cid: IPFS 报告 CID
            patient_address: 患者钱包地址
            
        Returns:
            交易信息和合约生成的 diagnosisId
        """
        if not self.contract:
            return {
                "success": False,
                "error": "合约未配置",
                "txHash": None,
                "diagnosisId": None
            }
        
        try:
            account = self.get_account()
            if not account:
                return {
                    "success": False,
                    "error": "未配置私钥",
                    "txHash": None,
                    "diagnosisId": None
                }
            
            account_addr = account.address
            
            # 将 data_hash 转换为 bytes32 (使用工具函数)
            data_hash_bytes = ensure_bytes32(data_hash)
            
            # 构建交易参数
            nonce = self.w3.eth.get_transaction_count(account_addr)
            
            # 使用 EIP-1559 交易格式 (Sepolia 标准)
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            max_priority_fee = self.w3.eth.max_priority_fee
            max_fee_per_gas = base_fee * 2 + max_priority_fee
            
            # 估算 Gas
            gas_estimate = self.contract.functions.recordDiagnosis(
                data_hash_bytes,
                model_version,
                ipfs_cid,
                patient_address
            ).estimate_gas({
                'from': account_addr,
            })
            
            # 构建交易 (EIP-1559)
            tx = self.contract.functions.recordDiagnosis(
                data_hash_bytes,
                model_version,
                ipfs_cid,
                patient_address
            ).build_transaction({
                'from': account_addr,
                'nonce': nonce,
                'gas': int(gas_estimate * 1.2),
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee,
            })
            
            # 签名并发送交易
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # 等待确认
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            # 从事件日志中提取 diagnosisId
            diagnosis_id = _extract_diagnosis_id_from_receipt(self.contract, self.w3, tx_receipt)
            
            return {
                "success": True,
                "txHash": self.w3.to_hex(tx_hash),
                "blockNumber": tx_receipt['blockNumber'],
                "gasUsed": tx_receipt['gasUsed'],
                "status": "confirmed",
                "diagnosisId": diagnosis_id
            }
            
        except ContractLogicError as e:
            return {
                "success": False,
                "error": f"合约执行失败：{str(e)}",
                "txHash": None
            }
        except TimeExhausted:
            return {
                "success": False,
                "error": "交易超时",
                "txHash": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"上链失败：{str(e)}",
                "txHash": None
            }
    
    def verify_diagnosis(self, diagnosis_id: str) -> Optional[Dict[str, Any]]:
        """
        验证诊断记录
        
        Args:
            diagnosis_id: 诊断 ID
            
        Returns:
            链上记录，如果不存在返回 None
        """
        if not self.contract:
            return None
        
        try:
            # 如果 diagnosis_id 是 hex 字符串，转换为 bytes
            if isinstance(diagnosis_id, str) and diagnosis_id.startswith("0x"):
                diagnosis_id = self.w3.to_bytes(hexstr=diagnosis_id)
            
            record = self.contract.functions.getRecord(diagnosis_id).call()
            
            return {
                "dataHash": record[0],
                "modelVersion": record[1],
                "timestamp": record[2],
                "ipfsCid": record[3],
                "patient": record[4]
            }
        except Exception as e:
            print(f"⚠️ 验证诊断记录失败：{e}")
            return None
    
    def get_patient_records(self, patient_address: str) -> list:
        """
        获取患者的所有诊断记录 ID
        
        Args:
            patient_address: 患者钱包地址
            
        Returns:
            诊断 ID 列表
        """
        if not self.contract:
            return []
        
        try:
            # 转换为 EIP-55 校验和格式地址
            checksum_address = self.w3.to_checksum_address(patient_address)
            return self.contract.functions.getPatientRecords(checksum_address).call()
        except Exception as e:
            print(f"⚠️ 查询患者记录失败：{e}")
            return []


def _extract_diagnosis_id_from_receipt(contract, w3, tx_receipt) -> Optional[str]:
    """
    从交易回执中提取 diagnosisId
    
    Args:
        contract: 智能合约对象
        w3: Web3 实例
        tx_receipt: 交易回执
        
    Returns:
        diagnosisId 的十六进制字符串，如果未找到返回 None
    """
    try:
        for log in tx_receipt.get('logs', []):
            try:
                # 尝试解码 DiagnosisRecorded 事件
                decoded_logs = contract.events.DiagnosisRecorded().process_log(log)
                if decoded_logs:
                    return w3.to_hex(decoded_logs['args']['diagnosisId'])
            except (ValueError, IndexError, KeyError):
                # 不是我们要的事件或解码失败，继续
                continue
    except Exception as e:
        print(f"⚠️ 解析事件日志失败：{e}")
    return None


# 单例模式
blockchain_client = None

def get_blockchain_client() -> BlockchainClient:
    """获取区块链客户端单例"""
    global blockchain_client
    if blockchain_client is None:
        try:
            blockchain_client = BlockchainClient()
        except Exception as e:
            print(f"⚠️ 区块链客户端初始化失败：{e}")
            return None
    return blockchain_client
