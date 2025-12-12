# db_singleton.py
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import psycopg2
from psycopg2.extensions import connection as pg_connection
from psycopg2.extras import RealDictCursor


class PgDB:
    """
    Простой Singleton для работы с PostgreSQL (без ORM).
    Открывает соединение на каждый вызов метода и сразу закрывает.
    """

    _instance: PgDB | None = None

    def __init__(self, **conn_params: Any) -> None:
        # Инициализируется один раз через init()
        self._conn_params = dict(conn_params)

    @classmethod
    def init(cls, **conn_params: Any) -> None:
        """
        Однократная инициализация параметров подключения (создаёт/обновляет Singleton).
        """
        if cls._instance is None:
            cls._instance = PgDB(**conn_params)
        else:
            cls._instance._conn_params = dict(conn_params)

    @classmethod
    def get(cls) -> PgDB:
        if cls._instance is None:
            raise RuntimeError("PgDB не инициализирован. Сначала вызовите PgDB.init(...).")
        return cls._instance

    def connect(self) -> pg_connection:
        """
        Возвращает новое подключение с autocommit=True.
        Вызывающий не обязан использовать контекст-менеджер: нижние методы
        (fetch_one/fetch_all/execute/execute_returning) сами открывают/закрывают.
        """
        conn: pg_connection = psycopg2.connect(**self._conn_params)  # type: ignore[call-arg]
        conn.autocommit = True
        return conn

    # --- Простые обёртки: открыть соединение, выполнить запрос, закрыть. ---

    def fetch_one(self, sql: str, params: Iterable[Any] | None = None) -> dict[str, Any] | None:
        conn = self.connect()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(sql, params)
                row = cur.fetchone()
                # row может быть None, либо RealDictRow (dict-подобный)
                return dict(row) if row is not None else None
            finally:
                cur.close()
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            finally:
                cur.close()
        finally:
            conn.close()

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> int:
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

    def execute_returning(
        self, sql: str, params: Iterable[Any] | None = None
    ) -> dict[str, Any] | None:
        """
        Выполняет запрос с RETURNING и возвращает первую строку результата (dict) либо None.
        """
        conn = self.connect()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(sql, params)
                row = cur.fetchone()
                return dict(row) if row is not None else None
            finally:
                cur.close()
        finally:
            conn.close()
