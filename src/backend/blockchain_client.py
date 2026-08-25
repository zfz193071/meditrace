"""
区块链客户端
负责与智能合约交互，实现诊断记录上链
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError, TimeExhausted

load_dotenv()


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
            abi_path = "../contracts/artifacts/DiagnosisRecord.json"
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
            account = self.w3.eth.from_account(self.private_key)
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
            交易信息
        """
        if not self.contract:
            return {
                "success": False,
                "error": "合约未配置",
                "txHash": None
            }
        
        try:
            account = self.get_account()
            if not account:
                return {
                    "success": False,
                    "error": "未配置私钥",
                    "txHash": None
                }
            
            # 构建交易
            nonce = self.w3.eth.get_transaction_count(account)
            gas_price = self.get_gas_price()
            
            # 估算 Gas
            gas_estimate = self.contract.functions.recordDiagnosis(
                data_hash,
                model_version,
                ipfs_cid,
                patient_address
            ).estimate_gas({
                'from': account,
                'nonce': nonce
            })
            
            # 发送交易
            tx_hash = self.contract.functions.recordDiagnosis(
                data_hash,
                model_version,
                ipfs_cid,
                patient_address
            ).transact({
                'from': account,
                'nonce': nonce,
                'gas': int(gas_estimate * 1.2),  # 增加 20% 缓冲
                'gasPrice': gas_price
            })
            
            # 等待确认
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            return {
                "success": True,
                "txHash": self.w3.to_hex(tx_hash),
                "blockNumber": tx_receipt['blockNumber'],
                "gasUsed": tx_receipt['gasUsed'],
                "status": "confirmed"
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
            record = self.contract.functions.getRecord(diagnosis_id).call()
            
            return {
                "dataHash": record[0],
                "modelVersion": record[1],
                "timestamp": record[2],
                "ipfsCid": record[3],
                "patient": record[4]
            }
        except:
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
            return self.contract.functions.getPatientRecords(patient_address).call()
        except:
            return []


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
