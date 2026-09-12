"""
Vercel Serverless Function - FastAPI 入口
将所有 API 请求路由到后端应用
"""

import os
import sys
from typing import Any

# 添加后端目录到 Python 路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, 'src', 'backend')
sys.path.insert(0, BACKEND_DIR)

# 导入 FastAPI 应用
from main import app as fastapi_app

# 导入 ASGI 适配器
from vercel.asgi import VercelASGI

# 创建 Vercel ASGI 应用
asgi_app = VercelASGI(fastapi_app)

# 导出 handler
async def handler(request):
    """Vercel Serverless Function Handler"""
    return await asgi_app.handle(request)

export = handler
