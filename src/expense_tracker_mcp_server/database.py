"""Shared PostgreSQL connection and query helpers."""

import logging
import os
import threading
import time
from contextlib import contextmanager

import psycopg
from psycopg.conninfo import conninfo_to_dict
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


class Database:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._conn = None
        self._lock = threading.RLock()
        self._connection_info = self._build_connection_info()
        self._initialized = True

    @staticmethod
    def _build_connection_info() -> dict[str, str]:
        connection_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
        if connection_url:
            params = conninfo_to_dict(connection_url)
        else:
            params = {
                "host": os.getenv("DB_HOST", "localhost"),
                "port": os.getenv("DB_PORT", "5432"),
                "dbname": os.getenv("DB_NAME", "expense_tracker"),
            }
            for env_name, param_name in (
                ("DB_USER", "user"),
                ("DB_PASSWORD", "password"),
            ):
                value = os.getenv(env_name)
                if value:
                    params[param_name] = value

        params.setdefault("sslmode", os.getenv("DB_SSLMODE", "require"))
        params.setdefault("connect_timeout", "10")
        ssl_root_cert = os.getenv("DB_SSLROOTCERT")
        if ssl_root_cert:
            params.setdefault("sslrootcert", ssl_root_cert)
        return params

    def connect(self):
        """Connect, retrying while PostgreSQL is starting."""
        retries = int(os.getenv("DB_CONNECT_RETRIES", "10"))
        delay = float(os.getenv("DB_RETRY_DELAY", "3"))

        with self._lock:
            last_error = None
            for attempt in range(1, retries + 1):
                try:
                    self._conn = psycopg.connect(
                        **self._connection_info,
                        autocommit=False,
                    )
                    log.info("Connected to PostgreSQL (attempt %d)", attempt)
                    return self._conn
                except (psycopg.OperationalError, OSError, TimeoutError) as exc:
                    last_error = exc
                    log.warning(
                        "DB connection attempt %d/%d failed: %s", attempt, retries, exc
                    )
                    if attempt < retries:
                        time.sleep(delay)
            raise ConnectionError(
                f"Could not connect to PostgreSQL after {retries} attempts. "
                "Check DATABASE_URL or the DB_HOST, DB_PORT, DB_NAME, DB_USER, "
                f"and DB_PASSWORD settings. Last error: {last_error}"
            ) from last_error

    def _ensure_connection(self):
        if self._conn is None:
            self.connect()
            return

        cursor = self._conn.cursor()
        try:
            cursor.execute("SELECT 1")
        except (psycopg.OperationalError, OSError, TimeoutError):
            self.connect()
        finally:
            cursor.close()

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @staticmethod
    def _rows_to_dicts(cursor, rows):
        cols = [column[0] for column in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            self._ensure_connection()
            cur = self._conn.cursor()
            try:
                cur.execute(query, params)
                return self._rows_to_dicts(cur, cur.fetchall())
            finally:
                cur.close()

    def fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        rows = self.fetch_all(query, params)
        return rows[0] if rows else None

    def execute(self, query: str, params: tuple = ()) -> int:
        """Execute a write query, commit on success, and return affected rows."""
        with self._lock:
            self._ensure_connection()
            cur = self._conn.cursor()
            try:
                cur.execute(query, params)
                affected = cur.rowcount
                self._conn.commit()
                return affected
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    def execute_many(self, query: str, params_list: list[tuple]) -> int:
        with self._lock:
            self._ensure_connection()
            cur = self._conn.cursor()
            try:
                cur.executemany(query, params_list)
                self._conn.commit()
                return cur.rowcount
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    @contextmanager
    def transaction(self):
        with self._lock:
            self._ensure_connection()
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()


db = Database()
