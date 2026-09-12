"""
数据库配置 - 支持 SQLite (开发) 和 PostgreSQL (生产)
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional

# 检测环境
IS_VERCEL = os.getenv('VERCEL') == '1'
IS_PRODUCTION = os.getenv('DATABASE_URL') is not None

# 数据库 URL
if IS_PRODUCTION:
    DATABASE_URL = os.getenv('DATABASE_URL')
    print(f"🔧 使用 PostgreSQL 数据库：{DATABASE_URL.split('@')[0]}@...")
else:
    DATABASE_URL = "sqlite:///./meditrace.db"
    print("🔧 使用 SQLite 数据库 (开发模式)")

# 创建数据库引擎
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # 自动重连
        pool_size=5,         # 连接池大小
        max_overflow=10      # 最大溢出连接数
    )

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """初始化数据库表"""
    from models import Base
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表初始化完成")


def get_db_connection():
    """获取单次连接（用于迁移等）"""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        return conn


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
