"""
database.py - one shared SQL Server connection for the whole project.

Usage from any other file:
    from database import db
    rows = db.fetch_all("SELECT * FROM users WHERE name = ?", ("Asha",))
"""
import logging
import os
import threading
import time
from contextlib import contextmanager

import pyodbc
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


class Database:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        # Singleton: every Database() call returns the same object
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._conn = None
        self._lock = threading.RLock()  # pyodbc connections aren't thread-safe
        self._conn_str = self._build_conn_string()
        self._initialized = True
        self.connect()

    # ---------- connection management ----------
    @staticmethod
    def _build_conn_string() -> str:
        driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
        if driver not in pyodbc.drivers():
            raise RuntimeError(
                f"ODBC driver '{driver}' not found. Installed drivers: {pyodbc.drivers()}. "
                "Install 'ODBC Driver 17 for SQL Server' on this machine "
                "(Docker only provides the server, not the client driver)."
            )

        # DB_HOST + DB_PORT match the docker-compose container (default 1433).
        # DB_SERVER, if set, overrides both (e.g. a named instance: localhost\\SQLEXPRESS).
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "1433")
        server = os.getenv("DB_SERVER") or f"{host},{port}"

        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={server}",
            f"DATABASE={os.getenv('DB_NAME', 'mydb')}",
            f"TrustServerCertificate={os.getenv('DB_TRUST_CERT', 'yes')}",
        ]
        user = os.getenv("DB_USER")
        if user:  # SQL login, e.g. 'sa' for the Docker container
            parts += [f"UID={user}", f"PWD={os.getenv('DB_PASSWORD', '')}"]
        else:  # Windows authentication
            parts.append("Trusted_Connection=yes")
        return ";".join(parts) + ";"

    def connect(self):
        """Connect, retrying for a while so the app can start right after
        `docker compose up -d` while SQL Server / the init job is still starting."""
        retries = int(os.getenv("DB_CONNECT_RETRIES", "10"))
        delay = float(os.getenv("DB_RETRY_DELAY", "3"))

        with self._lock:
            last_error = None
            for attempt in range(1, retries + 1):
                try:
                    self._conn = pyodbc.connect(self._conn_str, timeout=10)
                    self._conn.autocommit = False
                    log.info("Connected to SQL Server (attempt %d)", attempt)
                    return self._conn
                except pyodbc.Error as exc:
                    last_error = exc
                    log.warning(
                        "DB connection attempt %d/%d failed: %s", attempt, retries, exc
                    )
                    if attempt < retries:
                        time.sleep(delay)
            raise ConnectionError(
                f"Could not connect to SQL Server after {retries} attempts. "
                "Is the container running (`docker compose ps`) and do the .env "
                f"settings match? Last error: {last_error}"
            ) from last_error

    def _ensure_connection(self):
        """Reconnect automatically if the connection was dropped."""
        try:
            self._conn.cursor().execute("SELECT 1")
        except (pyodbc.Error, AttributeError):
            self.connect()

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ---------- query helpers ----------
    @staticmethod
    def _rows_to_dicts(cursor, rows):
        cols = [c[0] for c in cursor.description]
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
        """INSERT / UPDATE / DELETE. Commits on success, rolls back on error.
        Returns the number of affected rows."""
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
                cur.fast_executemany = True
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
        """Run several statements as one unit:

            with db.transaction() as cur:
                cur.execute("UPDATE ...", (...))
                cur.execute("INSERT ...", (...))
        """
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


# Shared instance: import this from other files
db = Database()