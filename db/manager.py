"""Database connection manager with dependency injection pattern using raw SQL."""

from contextlib import contextmanager
from typing import Generator
import logging
import psycopg2
from psycopg2 import pool, extras
from psycopg2.extensions import connection as PGConnection

from config.settings import settings


class DatabaseManager:
    """Manages database connections with auto commit/rollback using raw SQL."""

    def __init__(self, database_url: str | None = None):
        """Initialize database manager with connection pooling.

        Args:
            database_url: Database connection URL. If None, uses settings.
        """
        self.database_url = database_url or settings.database_url
        self._connection_pool: pool.SimpleConnectionPool | None = None
        self.logger = logging.getLogger(__name__)

    @property
    def connection_pool(self) -> pool.SimpleConnectionPool:
        """Get or create connection pool."""
        if self._connection_pool is None:
            # Parse database URL for psycopg2
            # Format: postgresql://user:password@host:port/database
            self._connection_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=self.database_url,
            )
        return self._connection_pool

    @contextmanager
    def get_connection(self) -> Generator[PGConnection, None, None]:
        """Get database connection with auto commit/rollback.

        Yields:
            Database connection that auto-commits on success, auto-rolls back on error.

        Example:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM customers WHERE cif_no = %s", (cif_no,))
                    result = cur.fetchone()
                # Auto-commits if no exception
                # Auto-rolls back if exception occurs
        """
        conn = self.connection_pool.getconn()
        self.logger.info("DB: acquired connection from pool")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.logger.info("DB: returning connection to pool")
            self.connection_pool.putconn(conn)

    @contextmanager
    def get_cursor(self, cursor_factory=None) -> Generator:
        """Get database cursor with auto connection management.

        Args:
            cursor_factory: Optional cursor factory (e.g., RealDictCursor for dict results)

        Yields:
            Database cursor ready to execute queries.

        Example:
            # Regular cursor
            with db_manager.get_cursor() as cur:
                cur.execute("SELECT * FROM customers")
                rows = cur.fetchall()

            # Dict cursor (returns dicts instead of tuples)
            from psycopg2.extras import RealDictCursor
            with db_manager.get_cursor(RealDictCursor) as cur:
                cur.execute("SELECT * FROM customers")
                rows = cur.fetchall()  # List[Dict]
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                self.logger.info("DB: opened cursor")
                yield cursor
            finally:
                self.logger.info("DB: closing cursor")
                cursor.close()

    def close_all_connections(self):
        """Close all connections in the pool."""
        if self._connection_pool:
            self._connection_pool.closeall()


# Global database manager instance
db_manager = DatabaseManager()


# Dependency injection function for FastAPI-style usage
def get_db_connection() -> Generator[PGConnection, None, None]:
    """Dependency injection for database connections.

    Usage:
        def some_function(conn = Depends(get_db_connection)):
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM customers")
            # Auto commits on success, auto rolls back on error
    """
    with db_manager.get_connection() as conn:
        yield conn


def get_db_cursor(cursor_factory=None) -> Generator:
    """Dependency injection for database cursors.

    Usage:
        from psycopg2.extras import RealDictCursor

        def some_function(cur = Depends(lambda: get_db_cursor(RealDictCursor))):
            cur.execute("SELECT * FROM customers")
            customers = cur.fetchall()  # List[Dict]
    """
    with db_manager.get_cursor(cursor_factory=cursor_factory) as cursor:
        yield cursor
