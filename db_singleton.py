# db_singleton.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor


class PgDB:
    """
    Singleton для работы с PostgreSQL
    """
    _instance: Optional["PgDB"] = None

    def __init__(self, **conn_params) -> None:
        # Инициализируется один раз через init()
        self._conn_params = dict(conn_params)

    @classmethod
    def init(cls, **conn_params) -> None:
        """
        Однократная инициализация подключения (Singleton)
        """
        if cls._instance is None:
            cls._instance = PgDB(**conn_params)
        else:
            cls._instance._conn_params = dict(conn_params)

    @classmethod
    def get(cls) -> "PgDB":
        if cls._instance is None:
            raise RuntimeError("PgDB не инициализирован. Сначала надо вызвать PgDB.init()")
        return cls._instance

    def connect(self):
        """
        Возвращает новое подключение с autocommit=True.
        """
        conn = psycopg2.connect(**self._conn_params)
        conn.autocommit = True
        return conn

    # --- Открываем соединение, выполняем запрос, закрываем. ---

    def fetch_one(self, sql: str, params: Iterable | None = None) -> Optional[Dict[str, Any]]:
        conn = self.connect()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(sql, params)
                return cur.fetchone()
            finally:
                cur.close()
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: Iterable | None = None) -> List[Dict[str, Any]]:
        conn = self.connect()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(sql, params)
                return cur.fetchall()
            finally:
                cur.close()
        finally:
            conn.close()

    def execute(self, sql: str, params: Iterable | None = None) -> int:
        conn = self.connect()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(sql, params)
                return cur.rowcount
            finally:
                cur.close()
        finally:
            conn.close()

    def execute_returning(self, sql: str, params: Iterable | None = None) -> Optional[Dict[str, Any]]:
        """
        Выполняет запрос с RETURNING и возвращает первую строку результата (dict) либо None.
        """
        conn = self.connect()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(sql, params)
                return cur.fetchone()
            finally:
                cur.close()
        finally:
            conn.close()
