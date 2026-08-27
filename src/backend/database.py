"""
数据库配置和连接管理
支持 SQLite (开发) 和 PostgreSQL (生产)
"""

import sqlite3
import os
from typing import Optional
from contextlib import contextmanager

# 从环境变量读取数据库 URL，默认使用 SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./meditrace.db")


def get_db_connection():
    """获取数据库连接"""
    if DATABASE_URL.startswith("sqlite"):
        conn = sqlite3.connect("meditrace.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        # PostgreSQL 连接逻辑（生产环境）
        # 使用 psycopg2 或 asyncpg
        raise NotImplementedError("PostgreSQL support coming soon")


@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """初始化数据库表结构"""
    with get_db() as conn:
        # 创建 conversations 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id VARCHAR(36) PRIMARY KEY,
                patient_id VARCHAR(42) NOT NULL,
                title VARCHAR(200) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSON
            )
        """)
        
        # 创建 messages 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR(36) PRIMARY KEY,
                conversation_id VARCHAR(36) NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                context_refs JSON,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        
        # 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_patient_id ON conversations(patient_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON conversations(updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conversation ON messages(conversation_id, timestamp)")
        
        print("Database tables initialized successfully")


def run_migration(migration_file: str):
    """运行迁移脚本"""
    migration_path = os.path.join(os.path.dirname(__file__), "migrations", migration_file)
    
    if not os.path.exists(migration_path):
        print(f"Migration file not found: {migration_path}")
        return
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    with get_db() as conn:
        conn.executescript(migration_sql)
        print(f"Migration {migration_file} executed successfully")
