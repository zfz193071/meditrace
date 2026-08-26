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
    """PDF 报告生成器 (使用 fpdf2)"""
    
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
        from fpdf import FPDF
        
        timestamp = timestamp or datetime.now()
        
        # 获取脚本所在目录，用于找到字体文件
        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(script_dir, 'fonts', 'SourceHanSansCN-Regular.ttf')
        
        # 创建 PDF 对象 (A4 纸张，毫米单位)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # 添加中文字体 (普通、粗体、斜体)
        pdf.add_font('Chinese', '', font_path, uni=True)
        pdf.add_font('Chinese', 'B', font_path, uni=True)
        pdf.add_font('Chinese', 'I', font_path, uni=True)
        pdf.set_font('Chinese', '', 11)
        
        # 页眉
        pdf.set_font('Chinese', '', 12)
        pdf.cell(0, 10, 'MediTrace - 医疗 AI 诊断报告', 0, 1, 'C')
        pdf.ln(5)
        
        # 报告标题
        pdf.set_font('Chinese', 'B', 16)
        pdf.cell(0, 12, 'MediTrace - 医疗 AI 诊断报告', 0, 1, 'C')
        pdf.ln(3)
        
        # 基本信息
        pdf.set_font('Chinese', '', 11)
        pdf.cell(0, 8, f'报告 ID: {diagnosis_id}', 0, 1)
        pdf.cell(0, 8, f'生成时间：{timestamp.strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.ln(5)
        
        # 症状描述部分
        pdf.set_font('Chinese', 'B', 12)
        pdf.cell(0, 10, '一、症状描述', 0, 1)
        pdf.set_font('Chinese', '', 11)
        pdf.multi_cell(0, 8, symptoms)
        pdf.ln(5)
        
        # 诊断建议部分
        pdf.set_font('Chinese', 'B', 12)
        pdf.cell(0, 10, '二、诊断建议', 0, 1)
        pdf.set_font('Chinese', '', 11)
        
        for i, suggestion in enumerate(suggestions, 1):
            disease = suggestion.get('disease', '未知')
            confidence = suggestion.get('confidence', 0) * 100
            
            # 疾病名称
            pdf.set_font('Chinese', 'B', 11)
            pdf.cell(0, 8, f'{i}. {disease}', 0, 1)
            
            # 置信度
            pdf.set_font('Chinese', '', 11)
            pdf.cell(0, 8, f'   置信度：{confidence:.0f}%', 0, 1)
            
            # 建议检查
            pdf.cell(0, 8, '   建议检查:', 0, 1)
            for rec in suggestion.get('recommendations', []):
                pdf.cell(10, 8, '', 0, 0)  # 缩进
                pdf.cell(0, 8, f'   - {rec}', 0, 1)
            
            pdf.ln(3)
        
        pdf.ln(5)
        
        # 重要提示/免责声明部分
        pdf.set_font('Chinese', 'B', 12)
        pdf.cell(0, 10, '三、重要提示', 0, 1)
        pdf.set_font('Chinese', '', 10)
        pdf.multi_cell(0, 6, disclaimer)
        pdf.ln(5)
        
        # 页脚信息
        pdf.set_font('Chinese', 'I', 9)
        pdf.cell(0, 8, '本报告由 MediTrace AI 系统生成', 0, 1, 'C')
        pdf.cell(0, 8, '仅供参考，请咨询专业医生', 0, 1, 'C')
        
        # 输出 PDF 字节
        return bytes(pdf.output())


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
                files = {"file": (filename, report_bytes, "application/pdf")}
                headers = {"Authorization": f"Bearer {jwt_token}"}
                
                # 设置 pinOptions，将文件设为公开，这样公共网关可以访问
                # 注意：pinOptions 需要作为单独的表单字段传递，而不是嵌套字典
                data = {
                    "pinOptions": '{"public":true}'  # 使用 JSON 字符串格式
                }
                
                upload_response = await client.post(
                    "https://api.pinata.cloud/pinning/pinFileToIPFS",
                    files=files,
                    headers=headers,
                    data=data
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
            filename_with_hash = f"{filename}_{content_hash}.pdf"
            
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
