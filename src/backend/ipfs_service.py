"""
IPFS 报告存储服务
生成 PDF 诊断报告并上传到 IPFS
"""

import os
import io
import json
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class PDFGenerator:
    """PDF 报告生成器"""
    
    @staticmethod
    def generate_diagnosis_report(
        symptoms: str,
        suggestions: list,
        disclaimer: str,
        diagnosis_id: str,
        timestamp: Optional[datetime] = None
    ) -> bytes:
        """
        生成 PDF 诊断报告
        
        Args:
            symptoms: 症状描述
            suggestions: 诊断建议列表
            disclaimer: 免责声明
            diagnosis_id: 诊断 ID
            timestamp: 时间戳
            
        Returns:
            PDF 文件字节
        """
        timestamp = timestamp or datetime.now()
        
        # 使用纯文本方式生成 (避免依赖 pdfkit 的 wkhtmltopdf)
        # 未来可以替换为 reportlab 或 fpdf2 生成真正的 PDF
        
        content = f"""
═══════════════════════════════════════════════════════
         MediTrace - 医疗 AI 诊断报告
═══════════════════════════════════════════════════════

报告 ID: {diagnosis_id}
生成时间：{timestamp.strftime('%Y-%m-%d %H:%M:%S')}

───────────────────────────────────────────────────────
一、症状描述
───────────────────────────────────────────────────────
{symptoms}

───────────────────────────────────────────────────────
二、诊断建议
───────────────────────────────────────────────────────
"""
        
        for i, suggestion in enumerate(suggestions, 1):
            content += f"""
{i}. {suggestion.get('disease', '未知')}
   置信度：{suggestion.get('confidence', 0) * 100:.0f}%
   建议检查:
"""
            for rec in suggestion.get('recommendations', []):
                content += f"     • {rec}\n"
        
        content += f"""
───────────────────────────────────────────────────────
三、重要提示
───────────────────────────────────────────────────────
{disclaimer}

═══════════════════════════════════════════════════════
        本报告由 MediTrace AI 系统生成
        仅供参考，请咨询专业医生
═══════════════════════════════════════════════════════
"""
        
        return content.encode('utf-8')


class IPFSClient:
    """IPFS 客户端 (使用 Pinata 服务)"""
    
    def __init__(self):
        self.api_key = os.getenv("PINATA_API_KEY")
        self.secret_api_key = os.getenv("PINATA_SECRET_API_KEY")
        
        # 如果没有配置 Pinata，使用本地 IPFS 节点
        self.use_pinata = bool(self.api_key and self.secret_api_key)
        
        if self.use_pinata:
            self.base_url = "https://api.pinata.cloud"
        else:
            # 本地 IPFS 节点
            import ipfshttpclient
            try:
                self.client = ipfshttpclient.connect("/ip4/127.0.0.1/tcp/5001")
            except:
                self.client = None
    
    async def upload_report(self, report_bytes: bytes, filename: str = "diagnosis_report.txt") -> Optional[str]:
        """
        上传报告到 IPFS
        
        Args:
            report_bytes: 报告文件字节
            filename: 文件名
            
        Returns:
            IPFS CID，失败返回 None
        """
        try:
            if self.use_pinata:
                return await self._upload_to_pinata(report_bytes, filename)
            elif self.client:
                return await self._upload_to_local_ipfs(report_bytes, filename)
            else:
                print("⚠️ IPFS 未配置，跳过上传")
                return None
                
        except Exception as e:
            print(f"⚠️ IPFS 上传失败：{e}")
            return None
    
    async def _upload_to_pinata(self, report_bytes: bytes, filename: str) -> Optional[str]:
        """上传到 Pinata"""
        import httpx
        
        try:
            # 使用 JWT token 直接上传（从环境变量读取）
            # JWT token 可以通过 Pinata 控制台生成，有效期很长
            jwt_token = os.getenv("PINATA_JWT_TOKEN")
            if not jwt_token:
                print("⚠️ PINATA_JWT_TOKEN 未配置，尝试使用 API Key 方式")
                # 回退到使用 API Key 和 Secret 的方式
                return await self._upload_to_pinata_legacy(report_bytes, filename)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 上传文件
                files = {"file": (filename, report_bytes, "text/plain")}
                headers = {"Authorization": f"Bearer {jwt_token}"}
                
                upload_response = await client.post(
                    "https://api.pinata.cloud/pinning/pinFileToIPFS",
                    files=files,
                    headers=headers
                )
                upload_response.raise_for_status()
                
                return upload_response.json()["IpfsHash"]
                
        except Exception as e:
            print(f"Pinata 上传失败：{e}")
            return None
    
    async def _upload_to_pinata_legacy(self, report_bytes: bytes, filename: str) -> Optional[str]:
        """使用 API Key 和 Secret 上传（旧方式，需要手动生成 JWT）"""
        # 建议用户改用 JWT token 方式
        print("⚠️ 建议使用 PINATA_JWT_TOKEN 环境变量，而不是 PINATA_API_KEY/PINATA_SECRET_API_KEY")
        return None
    
    async def _upload_to_local_ipfs(self, report_bytes: bytes, filename: str) -> Optional[str]:
        """上传到本地 IPFS 节点"""
        try:
            import hashlib
            
            # 计算内容哈希
            content_hash = hashlib.sha256(report_bytes).hexdigest()[:16]
            filename_with_hash = f"{filename}_{content_hash}.txt"
            
            # 使用 ipfshttpclient 上传
            response = self.client.add_bytes(report_bytes)
            
            return response.get('Hash')
            
        except Exception as e:
            print(f"本地 IPFS 上传失败：{e}")
            return None


# 单例模式
ipfs_client = None

def get_ipfs_client() -> Optional[IPFSClient]:
    """获取 IPFS 客户端单例"""
    global ipfs_client
    if ipfs_client is None:
        try:
            ipfs_client = IPFSClient()
        except Exception as e:
            print(f"⚠️ IPFS 客户端初始化失败：{e}")
            return None
    return ipfs_client


def generate_report(
    symptoms: str,
    suggestions: list,
    disclaimer: str,
    diagnosis_id: str
) -> bytes:
    """生成诊断报告 (便捷函数)"""
    return PDFGenerator.generate_diagnosis_report(
        symptoms=symptoms,
        suggestions=suggestions,
        disclaimer=disclaimer,
        diagnosis_id=diagnosis_id
    )
