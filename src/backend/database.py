"""
数据库配置 - 支持 SQLite (开发) 和 PostgreSQL (生产)
"""

import os
import json
import re
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# 检测环境
IS_VERCEL = os.getenv('VERCEL') == '1'
DATABASE_URL = os.getenv('DATABASE_URL')
if IS_VERCEL and not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required on Vercel; SQLite is not persistent")
DATABASE_URL = DATABASE_URL or "sqlite:///./meditrace.db"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
IS_PRODUCTION = not DATABASE_URL.startswith("sqlite")

# 数据库 URL
print("Database backend: PostgreSQL" if IS_PRODUCTION else "Database backend: SQLite")

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
        poolclass=NullPool,  # Neon handles pooling; do not retain connections in idle functions.
        connect_args={"connect_timeout": 10},
    )

class DatabaseRow(dict):
    """Keep the existing sqlite.Row interface, including JSON text and numeric indexing."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

class DatabaseResult:
    def __init__(self, result):
        self.result = result

    @staticmethod
    def _row(row):
        if row is None:
            return None
        return DatabaseRow({
            key: json.dumps(value) if isinstance(value, (dict, list)) else value
            for key, value in row._mapping.items()
        })

    def fetchone(self):
        return self._row(self.result.fetchone())

    def fetchall(self):
        return [self._row(row) for row in self.result.fetchall()]


class DatabaseConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=()):
        # Convert existing qmark queries to dialect-independent bound parameters.
        # Quoted SQL literals/identifiers must retain their question marks.
        bindings = {}

        def bind(match):
            if match.group() != "?":
                return match.group()
            index = len(bindings)
            name = f"param_{index}"
            bindings[name] = parameters[index]
            return f":{name}"

        query = re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\?", bind, statement)
        if len(bindings) != len(parameters):
            raise ValueError("SQL parameter count mismatch")
        return DatabaseResult(self.connection.execute(text(query), bindings))


@contextmanager
def get_db():
    """Commit successful operations and roll back failed operations on both databases."""
    with engine.begin() as connection:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        yield DatabaseConnection(connection)


@contextmanager
def get_db_connection():
    """获取单次连接（用于迁移等）"""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        yield conn


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
    
    with engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            conn.connection.driver_connection.executescript(migration_sql)
        else:
            conn.exec_driver_sql(migration_sql)
        print(f"Migration {migration_file} executed successfully")
