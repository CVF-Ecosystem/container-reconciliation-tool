# File: utils/database.py
"""
Database Abstraction Layer for Container Inventory Reconciliation Tool.

V5.4 - Phase 3: Enterprise Ready
Features:
- Abstract database interface
- SQLite implementation (default)
- PostgreSQL implementation (production)
- Connection pooling
- Migration support
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Protocol, TypeVar, Generic
from dataclasses import dataclass, field
from pathlib import Path
from abc import ABC, abstractmethod
from contextlib import contextmanager
import threading
import sqlite3
import json


T = TypeVar('T')


class DatabaseError(Exception):
    """Base database error."""
    pass


class ConnectionError(DatabaseError):
    """Database connection error."""
    pass


class QueryError(DatabaseError):
    """Query execution error."""
    pass


@dataclass
class DatabaseConfig:
    """Database configuration."""
    # Common settings
    database_type: str = "sqlite"  # sqlite, postgresql
    
    # SQLite settings
    sqlite_path: str = "./data/app.db"
    
    # PostgreSQL settings
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "container_inventory"
    pg_user: str = "app"
    pg_password: str = ""
    pg_ssl_mode: str = "prefer"
    
    # Connection pool settings
    pool_min_size: int = 1
    pool_max_size: int = 10
    pool_timeout: int = 30
    
    # Query settings
    query_timeout: int = 60
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without password)."""
        return {
            "database_type": self.database_type,
            "sqlite_path": self.sqlite_path,
            "pg_host": self.pg_host,
            "pg_port": self.pg_port,
            "pg_database": self.pg_database,
            "pg_user": self.pg_user,
            "pg_ssl_mode": self.pg_ssl_mode,
            "pool_min_size": self.pool_min_size,
            "pool_max_size": self.pool_max_size,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatabaseConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create from environment variables."""
        import os
        return cls(
            database_type=os.getenv("DB_TYPE", "sqlite"),
            sqlite_path=os.getenv("SQLITE_PATH", "./data/app.db"),
            pg_host=os.getenv("PG_HOST", "localhost"),
            pg_port=int(os.getenv("PG_PORT", "5432")),
            pg_database=os.getenv("PG_DATABASE", "container_inventory"),
            pg_user=os.getenv("PG_USER", "app"),
            pg_password=os.getenv("PG_PASSWORD", ""),
            pg_ssl_mode=os.getenv("PG_SSL_MODE", "prefer"),
        )


class Connection(ABC):
    """Abstract database connection."""
    
    @abstractmethod
    def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a query."""
        pass
    
    @abstractmethod
    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """Fetch one row."""
        pass
    
    @abstractmethod
    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Fetch all rows."""
        pass
    
    @abstractmethod
    def commit(self):
        """Commit transaction."""
        pass
    
    @abstractmethod
    def rollback(self):
        """Rollback transaction."""
        pass
    
    @abstractmethod
    def close(self):
        """Close connection."""
        pass


class SQLiteConnection(Connection):
    """SQLite connection implementation."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
    
    def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a query."""
        with self._lock:
            try:
                cursor = self._conn.execute(query, params or ())
                return cursor.lastrowid
            except sqlite3.Error as e:
                raise QueryError(f"Query failed: {e}")
    
    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """Fetch one row."""
        with self._lock:
            try:
                cursor = self._conn.execute(query, params or ())
                row = cursor.fetchone()
                return dict(row) if row else None
            except sqlite3.Error as e:
                raise QueryError(f"Query failed: {e}")
    
    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Fetch all rows."""
        with self._lock:
            try:
                cursor = self._conn.execute(query, params or ())
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                raise QueryError(f"Query failed: {e}")
    
    def commit(self):
        """Commit transaction."""
        with self._lock:
            self._conn.commit()
    
    def rollback(self):
        """Rollback transaction."""
        with self._lock:
            self._conn.rollback()
    
    def close(self):
        """Close connection."""
        self._conn.close()


class PostgreSQLConnection(Connection):
    """PostgreSQL connection implementation (requires psycopg2)."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._conn = None
        self._connect()
    
    def _connect(self):
        """Establish connection."""
        try:
            import psycopg2
            import psycopg2.extras
            
            self._conn = psycopg2.connect(
                host=self.config.pg_host,
                port=self.config.pg_port,
                database=self.config.pg_database,
                user=self.config.pg_user,
                password=self.config.pg_password,
                sslmode=self.config.pg_ssl_mode,
            )
            logging.info("Connected to PostgreSQL")
        except ImportError:
            raise ConnectionError("psycopg2 is required for PostgreSQL")
        except Exception as e:
            raise ConnectionError(f"PostgreSQL connection failed: {e}")
    
    def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a query."""
        try:
            cursor = self._conn.cursor()
            cursor.execute(query, params)
            return cursor.rowcount
        except Exception as e:
            raise QueryError(f"Query failed: {e}")
    
    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """Fetch one row."""
        try:
            import psycopg2.extras
            cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            raise QueryError(f"Query failed: {e}")
    
    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Fetch all rows."""
        try:
            import psycopg2.extras
            cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise QueryError(f"Query failed: {e}")
    
    def commit(self):
        """Commit transaction."""
        self._conn.commit()
    
    def rollback(self):
        """Rollback transaction."""
        self._conn.rollback()
    
    def close(self):
        """Close connection."""
        if self._conn:
            self._conn.close()


class ConnectionPool:
    """Simple connection pool."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: List[Connection] = []
        self._in_use: Dict[int, Connection] = {}
        self._lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize minimum connections."""
        for _ in range(self.config.pool_min_size):
            conn = self._create_connection()
            self._pool.append(conn)
    
    def _create_connection(self) -> Connection:
        """Create a new connection."""
        if self.config.database_type == "postgresql":
            return PostgreSQLConnection(self.config)
        else:
            return SQLiteConnection(self.config.sqlite_path)
    
    def acquire(self) -> Connection:
        """Acquire a connection from pool."""
        with self._lock:
            if self._pool:
                conn = self._pool.pop()
            elif len(self._in_use) < self.config.pool_max_size:
                conn = self._create_connection()
            else:
                raise ConnectionError("Connection pool exhausted")
            
            self._in_use[id(conn)] = conn
            return conn
    
    def release(self, conn: Connection):
        """Release a connection back to pool."""
        with self._lock:
            conn_id = id(conn)
            if conn_id in self._in_use:
                del self._in_use[conn_id]
                self._pool.append(conn)
    
    def close_all(self):
        """Close all connections."""
        with self._lock:
            for conn in self._pool:
                conn.close()
            for conn in self._in_use.values():
                conn.close()
            self._pool.clear()
            self._in_use.clear()


class Database:
    """Main database interface."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool = ConnectionPool(self.config)
        self._operation_lock = threading.Lock()
    
    @contextmanager
    def connection(self):
        """Get a database connection."""
        conn = self._pool.acquire()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.release(conn)
    
    @contextmanager
    def transaction(self):
        """Execute within a transaction."""
        conn = self._pool.acquire()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.release(conn)
    
    def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a query."""
        with self._operation_lock:
            with self.connection() as conn:
                return conn.execute(query, params)
    
    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """Fetch one row."""
        with self._operation_lock:
            with self.connection() as conn:
                return conn.fetch_one(query, params)
    
    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Fetch all rows."""
        with self._operation_lock:
            with self.connection() as conn:
                return conn.fetch_all(query, params)
    
    def close(self):
        """Close database and pool."""
        self._pool.close_all()


class Repository(Generic[T], ABC):
    """Abstract repository pattern for data access."""
    
    def __init__(self, db: Database, table_name: str):
        self.db = db
        self.table_name = table_name
    
    @abstractmethod
    def _to_entity(self, row: Dict) -> T:
        """Convert database row to entity."""
        pass
    
    @abstractmethod
    def _to_row(self, entity: T) -> Dict:
        """Convert entity to database row."""
        pass
    
    def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find entity by ID."""
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"
        row = self.db.fetch_one(query, (entity_id,))
        return self._to_entity(row) if row else None
    
    def find_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Find all entities."""
        query = f"SELECT * FROM {self.table_name} LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._to_entity(row) for row in rows]
    
    def save(self, entity: T) -> T:
        """Save entity (insert or update)."""
        row = self._to_row(entity)
        columns = ", ".join(row.keys())
        placeholders = ", ".join(["?" for _ in row])
        
        query = f"INSERT OR REPLACE INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        self.db.execute(query, tuple(row.values()))
        return entity
    
    def delete(self, entity_id: str) -> bool:
        """Delete entity by ID."""
        query = f"DELETE FROM {self.table_name} WHERE id = ?"
        self.db.execute(query, (entity_id,))
        return True
    
    def count(self) -> int:
        """Count all entities."""
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"
        result = self.db.fetch_one(query)
        return result["count"] if result else 0


# Migration support
@dataclass
class Migration:
    """Database migration."""
    version: int
    name: str
    up_sql: str
    down_sql: str


class MigrationManager:
    """Database migration manager."""
    
    MIGRATIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    def __init__(self, db: Database):
        self.db = db
        self._migrations: List[Migration] = []
        self._ensure_migrations_table()
    
    def _ensure_migrations_table(self):
        """Create migrations tracking table."""
        self.db.execute(self.MIGRATIONS_TABLE)
    
    def add_migration(self, migration: Migration):
        """Add a migration."""
        self._migrations.append(migration)
        self._migrations.sort(key=lambda m: m.version)
    
    def get_current_version(self) -> int:
        """Get current migration version."""
        result = self.db.fetch_one(
            "SELECT MAX(version) as version FROM migrations"
        )
        return result["version"] if result and result["version"] else 0
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get pending migrations."""
        current = self.get_current_version()
        return [m for m in self._migrations if m.version > current]
    
    def migrate(self, target_version: Optional[int] = None) -> List[Migration]:
        """Run pending migrations."""
        applied = []
        pending = self.get_pending_migrations()
        
        if target_version is not None:
            pending = [m for m in pending if m.version <= target_version]
        
        for migration in pending:
            logging.info(f"Applying migration {migration.version}: {migration.name}")
            
            try:
                self.db.execute(migration.up_sql)
                self.db.execute(
                    "INSERT INTO migrations (version, name) VALUES (?, ?)",
                    (migration.version, migration.name)
                )
                applied.append(migration)
            except Exception as e:
                logging.error(f"Migration {migration.version} failed: {e}")
                raise
        
        return applied
    
    def rollback(self, steps: int = 1) -> List[Migration]:
        """Rollback migrations."""
        rolled_back = []
        current = self.get_current_version()
        
        # Get migrations to rollback
        to_rollback = [m for m in reversed(self._migrations) 
                       if m.version <= current][:steps]
        
        for migration in to_rollback:
            logging.info(f"Rolling back migration {migration.version}: {migration.name}")
            
            try:
                self.db.execute(migration.down_sql)
                self.db.execute(
                    "DELETE FROM migrations WHERE version = ?",
                    (migration.version,)
                )
                rolled_back.append(migration)
            except Exception as e:
                logging.error(f"Rollback {migration.version} failed: {e}")
                raise
        
        return rolled_back


# Default migrations for the application
DEFAULT_MIGRATIONS = [
    Migration(
        version=1,
        name="create_users_table",
        up_sql="""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            tenant_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        down_sql="DROP TABLE IF EXISTS users"
    ),
    Migration(
        version=2,
        name="create_tenants_table",
        up_sql="""
        CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        down_sql="DROP TABLE IF EXISTS tenants"
    ),
    Migration(
        version=3,
        name="create_reconciliation_results_table",
        up_sql="""
        CREATE TABLE IF NOT EXISTS reconciliation_results (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            file_list TEXT,
            matched_count INTEGER,
            unmatched_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
        """,
        down_sql="DROP TABLE IF EXISTS reconciliation_results"
    ),
    Migration(
        version=4,
        name="create_audit_logs_table",
        up_sql="""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            tenant_id TEXT,
            action TEXT NOT NULL,
            resource TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        down_sql="DROP TABLE IF EXISTS audit_logs"
    ),
    Migration(
        version=5,
        name="create_scheduled_tasks_table",
        up_sql="""
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            task_type TEXT NOT NULL,
            schedule TEXT NOT NULL,
            config TEXT,
            last_run TIMESTAMP,
            next_run TIMESTAMP,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        down_sql="DROP TABLE IF EXISTS scheduled_tasks"
    ),
]


# Global database instance
_database: Optional[Database] = None


def get_database() -> Database:
    """Get global database instance."""
    global _database
    if _database is None:
        _database = Database()
    return _database


def init_database(config: Optional[DatabaseConfig] = None) -> Database:
    """Initialize database with migrations."""
    global _database
    _database = Database(config)
    
    # Run migrations
    migration_manager = MigrationManager(_database)
    for migration in DEFAULT_MIGRATIONS:
        migration_manager.add_migration(migration)
    
    applied = migration_manager.migrate()
    if applied:
        logging.info(f"Applied {len(applied)} migrations")
    
    return _database


def close_database():
    """Close global database."""
    global _database
    if _database:
        _database.close()
        _database = None
