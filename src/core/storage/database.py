"""SQLite 数据库连接管理"""

import sqlite3
import threading
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

logger = get_logger("storage.database")


class Database:
    """SQLite 数据库管理器，线程安全连接池"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的连接（线程隔离）"""
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn = conn
        return self._local.conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL，返回 cursor"""
        conn = self._get_conn()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor

    def executemany(self, sql: str, params_list: list[tuple]) -> None:
        """批量执行"""
        conn = self._get_conn()
        conn.executemany(sql, params_list)
        conn.commit()

    def query_one(self, sql: str, params: tuple = ()) -> dict | None:
        """查询单行，返回 dict 或 None"""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def query_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """查询多行，返回 dict 列表"""
        cursor = self.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def _init_schema(self) -> None:
        """初始化数据库表结构"""
        schema_sql = """
        -- 邮件元数据
        CREATE TABLE IF NOT EXISTS mails (
            message_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL DEFAULT 'default',
            sender TEXT, sender_domain TEXT, recipient TEXT,
            subject TEXT, send_time TEXT, receive_time TEXT,
            body_text TEXT, body_html TEXT, body_file_path TEXT,
            category TEXT, priority TEXT, confidence REAL DEFAULT 0.0,
            need_reply INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            classify_source TEXT,
            content_fingerprint TEXT,
            thread_id TEXT,
            in_reply_to TEXT,
            references_hdr TEXT,
            status TEXT DEFAULT 'new',
            is_read INTEGER DEFAULT 0,
            is_sent INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_mails_category ON mails(category);
        CREATE INDEX IF NOT EXISTS idx_mails_status ON mails(status);
        CREATE INDEX IF NOT EXISTS idx_mails_send_time ON mails(send_time);
        CREATE INDEX IF NOT EXISTS idx_mails_fingerprint ON mails(content_fingerprint);
        CREATE INDEX IF NOT EXISTS idx_mails_thread ON mails(thread_id);

        -- 流程执行记录
        CREATE TABLE IF NOT EXISTS execution_records (
            id TEXT PRIMARY KEY,
            mail_id TEXT, workflow_name TEXT, workflow_version TEXT,
            status TEXT,
            current_step TEXT, context_snapshot TEXT,
            started_at DATETIME, completed_at DATETIME,
            error_message TEXT,
            FOREIGN KEY (mail_id) REFERENCES mails(message_id)
        );

        -- 去重缓存
        CREATE TABLE IF NOT EXISTS seen_message_ids (
            message_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL DEFAULT 'default',
            first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- 分类缓存
        CREATE TABLE IF NOT EXISTS classify_cache (
            mail_hash TEXT PRIMARY KEY,
            category TEXT, priority TEXT, confidence REAL,
            need_reply INTEGER, reason TEXT, source TEXT,
            tags TEXT DEFAULT '[]',
            result_json TEXT,
            classified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME
        );

        -- 任务状态表（容错恢复）
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            type TEXT,
            mail_id TEXT,
            workflow_name TEXT,
            notification_data TEXT,
            status TEXT DEFAULT 'pending',
            current_step TEXT,
            context_data TEXT,
            attempt_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME,
            completed_at DATETIME,
            error_message TEXT,
            next_retry_at DATETIME
        );

        -- 通知失败队列
        CREATE TABLE IF NOT EXISTS failed_notifications (
            id TEXT PRIMARY KEY,
            channel TEXT, recipient TEXT,
            content TEXT, error TEXT,
            retry_count INTEGER DEFAULT 0,
            first_failed_at REAL,
            last_failed_at REAL,
            next_retry_at REAL,
            status TEXT DEFAULT 'pending'
        );
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript(schema_sql)
        conn.commit()
        conn.close()
        logger.debug(f"数据库 schema 初始化完成: {self.db_path}")

    def close(self) -> None:
        """关闭当前线程连接"""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn
