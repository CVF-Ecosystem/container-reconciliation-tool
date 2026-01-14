# File: tests/test_database.py
"""
Tests for Database Abstraction Layer.

V5.4 - Phase 3: Enterprise Ready
"""

import pytest
import json
import threading
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock


# Import modules to test
from utils.database import (
    DatabaseError, ConnectionError, QueryError,
    DatabaseConfig, Connection, SQLiteConnection,
    ConnectionPool, Database, Repository,
    Migration, MigrationManager, DEFAULT_MIGRATIONS,
    get_database, init_database, close_database
)


# ============== Fixtures ==============

@pytest.fixture
def db_config():
    """Create test database configuration."""
    return DatabaseConfig(
        database_type="sqlite",
        sqlite_path=":memory:",
        pool_min_size=1,
        pool_max_size=5,
    )


@pytest.fixture
def db_config_with_path(tmp_path):
    """Create database config with file path."""
    return DatabaseConfig(
        database_type="sqlite",
        sqlite_path=str(tmp_path / "test.db"),
    )


@pytest.fixture
def sqlite_connection(tmp_path):
    """Create SQLite connection."""
    db_path = str(tmp_path / "test_conn.db")
    conn = SQLiteConnection(db_path)
    yield conn
    conn.close()


@pytest.fixture
def database(tmp_path):
    """Create test database instance."""
    config = DatabaseConfig(
        database_type="sqlite",
        sqlite_path=str(tmp_path / "test_db.db"),
        pool_min_size=1,
        pool_max_size=3,
    )
    db = Database(config)
    yield db
    db.close()


# ============== Exception Tests ==============

class TestExceptions:
    """Test database exceptions."""
    
    def test_database_error(self):
        """Test base DatabaseError."""
        with pytest.raises(DatabaseError):
            raise DatabaseError("Test error")
    
    def test_connection_error(self):
        """Test ConnectionError is DatabaseError."""
        with pytest.raises(DatabaseError):
            raise ConnectionError("Connection failed")
    
    def test_query_error(self):
        """Test QueryError is DatabaseError."""
        with pytest.raises(DatabaseError):
            raise QueryError("Query failed")


# ============== DatabaseConfig Tests ==============

class TestDatabaseConfig:
    """Test DatabaseConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = DatabaseConfig()
        
        assert config.database_type == "sqlite"
        assert config.sqlite_path == "./data/app.db"
        assert config.pg_host == "localhost"
        assert config.pg_port == 5432
        assert config.pool_min_size == 1
        assert config.pool_max_size == 10
    
    def test_custom_values(self, db_config):
        """Test custom configuration values."""
        assert db_config.sqlite_path == ":memory:"
        assert db_config.pool_max_size == 5
    
    def test_to_dict(self, db_config):
        """Test converting config to dictionary."""
        data = db_config.to_dict()
        
        assert isinstance(data, dict)
        assert data["database_type"] == "sqlite"
        # Password should not be in dict (security)
        assert "pg_password" not in data
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "database_type": "postgresql",
            "pg_host": "db.example.com",
            "pg_port": 5433,
        }
        config = DatabaseConfig.from_dict(data)
        
        assert config.database_type == "postgresql"
        assert config.pg_host == "db.example.com"
        assert config.pg_port == 5433
    
    def test_from_env(self):
        """Test creating config from environment."""
        with patch.dict('os.environ', {
            'DB_TYPE': 'postgresql',
            'PG_HOST': 'env-host.com',
            'PG_PORT': '5434',
        }):
            config = DatabaseConfig.from_env()
            assert config.database_type == "postgresql"
            assert config.pg_host == "env-host.com"
            assert config.pg_port == 5434


# ============== SQLiteConnection Tests ==============

class TestSQLiteConnection:
    """Test SQLiteConnection class."""
    
    def test_connection_creates_directory(self, tmp_path):
        """Test connection creates parent directory."""
        db_path = tmp_path / "subdir" / "test.db"
        conn = SQLiteConnection(str(db_path))
        
        assert db_path.parent.exists()
        conn.close()
    
    def test_execute_create_table(self, sqlite_connection):
        """Test executing CREATE TABLE."""
        result = sqlite_connection.execute(
            "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"
        )
        sqlite_connection.commit()
        # Returns lastrowid (0 for CREATE)
        assert result is not None
    
    def test_execute_insert(self, sqlite_connection):
        """Test executing INSERT."""
        sqlite_connection.execute(
            "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"
        )
        
        result = sqlite_connection.execute(
            "INSERT INTO items (name) VALUES (?)",
            ("Item 1",)
        )
        sqlite_connection.commit()
        
        assert result == 1  # First row ID
    
    def test_fetch_one(self, sqlite_connection):
        """Test fetching one row."""
        sqlite_connection.execute(
            "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)"
        )
        sqlite_connection.execute(
            "INSERT INTO products (name) VALUES (?)",
            ("Product A",)
        )
        sqlite_connection.commit()
        
        row = sqlite_connection.fetch_one("SELECT * FROM products WHERE id = ?", (1,))
        
        assert row is not None
        assert row["name"] == "Product A"
    
    def test_fetch_one_none(self, sqlite_connection):
        """Test fetching non-existent row returns None."""
        sqlite_connection.execute(
            "CREATE TABLE empty_table (id INTEGER PRIMARY KEY)"
        )
        
        row = sqlite_connection.fetch_one("SELECT * FROM empty_table WHERE id = ?", (999,))
        assert row is None
    
    def test_fetch_all(self, sqlite_connection):
        """Test fetching all rows."""
        sqlite_connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        sqlite_connection.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))
        sqlite_connection.execute("INSERT INTO users (name) VALUES (?)", ("Bob",))
        sqlite_connection.execute("INSERT INTO users (name) VALUES (?)", ("Charlie",))
        sqlite_connection.commit()
        
        rows = sqlite_connection.fetch_all("SELECT * FROM users ORDER BY id")
        
        assert len(rows) == 3
        assert rows[0]["name"] == "Alice"
        assert rows[2]["name"] == "Charlie"
    
    def test_rollback(self, sqlite_connection):
        """Test transaction rollback."""
        sqlite_connection.execute(
            "CREATE TABLE rollback_test (id INTEGER PRIMARY KEY, value TEXT)"
        )
        sqlite_connection.commit()
        
        sqlite_connection.execute(
            "INSERT INTO rollback_test (value) VALUES (?)",
            ("should_rollback",)
        )
        sqlite_connection.rollback()
        
        rows = sqlite_connection.fetch_all("SELECT * FROM rollback_test")
        assert len(rows) == 0
    
    def test_invalid_query_raises(self, sqlite_connection):
        """Test invalid query raises QueryError."""
        with pytest.raises(QueryError):
            sqlite_connection.execute("INVALID SQL SYNTAX")


# ============== ConnectionPool Tests ==============

class TestConnectionPool:
    """Test ConnectionPool class."""
    
    def test_pool_initialization(self, db_config_with_path):
        """Test pool creates minimum connections."""
        pool = ConnectionPool(db_config_with_path)
        
        assert len(pool._pool) == db_config_with_path.pool_min_size
        pool.close_all()
    
    def test_acquire_connection(self, db_config_with_path):
        """Test acquiring connection from pool."""
        pool = ConnectionPool(db_config_with_path)
        
        conn = pool.acquire()
        assert conn is not None
        assert isinstance(conn, Connection)
        
        pool.release(conn)
        pool.close_all()
    
    def test_release_connection(self, db_config_with_path):
        """Test releasing connection back to pool."""
        pool = ConnectionPool(db_config_with_path)
        initial_pool_size = len(pool._pool)
        
        conn = pool.acquire()
        assert len(pool._pool) == initial_pool_size - 1
        
        pool.release(conn)
        assert len(pool._pool) == initial_pool_size
        
        pool.close_all()
    
    def test_pool_creates_new_connection(self, db_config_with_path):
        """Test pool creates new connection when empty."""
        db_config_with_path.pool_min_size = 1
        db_config_with_path.pool_max_size = 3
        pool = ConnectionPool(db_config_with_path)
        
        conn1 = pool.acquire()
        conn2 = pool.acquire()  # Should create new
        
        assert conn1 is not conn2
        
        pool.release(conn1)
        pool.release(conn2)
        pool.close_all()
    
    def test_pool_exhaustion_raises(self, db_config_with_path):
        """Test pool exhaustion raises error."""
        db_config_with_path.pool_min_size = 1
        db_config_with_path.pool_max_size = 2
        pool = ConnectionPool(db_config_with_path)
        
        conn1 = pool.acquire()
        conn2 = pool.acquire()
        
        with pytest.raises(ConnectionError, match="pool exhausted"):
            pool.acquire()
        
        pool.release(conn1)
        pool.release(conn2)
        pool.close_all()
    
    def test_close_all(self, db_config_with_path):
        """Test closing all connections."""
        pool = ConnectionPool(db_config_with_path)
        conn = pool.acquire()
        pool.release(conn)
        
        pool.close_all()
        
        assert len(pool._pool) == 0
        assert len(pool._in_use) == 0


# ============== Database Tests ==============

class TestDatabase:
    """Test Database class."""
    
    def test_database_initialization(self, database):
        """Test database initializes properly."""
        assert database._pool is not None
    
    def test_connection_context(self, database):
        """Test connection context manager."""
        with database.connection() as conn:
            conn.execute("CREATE TABLE ctx_test (id INTEGER)")
        
        # Verify table was created
        result = database.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ctx_test'"
        )
        assert result is not None
    
    def test_transaction_context(self, database):
        """Test transaction context manager."""
        database.execute("CREATE TABLE tx_test (id INTEGER, val TEXT)")
        
        with database.transaction() as conn:
            conn.execute("INSERT INTO tx_test (id, val) VALUES (?, ?)", (1, "test"))
        
        row = database.fetch_one("SELECT * FROM tx_test WHERE id = ?", (1,))
        assert row["val"] == "test"
    
    def test_transaction_rollback_on_error(self, database):
        """Test transaction rolls back on error."""
        database.execute("CREATE TABLE tx_err (id INTEGER PRIMARY KEY, val TEXT)")
        database.execute("INSERT INTO tx_err (id, val) VALUES (?, ?)", (1, "original"))
        
        try:
            with database.transaction() as conn:
                conn.execute("UPDATE tx_err SET val = ? WHERE id = ?", ("changed", 1))
                raise ValueError("Simulated error")
        except ValueError:
            pass
        
        row = database.fetch_one("SELECT * FROM tx_err WHERE id = ?", (1,))
        assert row["val"] == "original"  # Rollback happened
    
    def test_execute(self, database):
        """Test direct execute method."""
        database.execute("CREATE TABLE exec_test (id INTEGER, name TEXT)")
        result = database.execute(
            "INSERT INTO exec_test (id, name) VALUES (?, ?)",
            (1, "Test Name")
        )
        
        assert result is not None
    
    def test_fetch_one(self, database):
        """Test direct fetch_one method."""
        database.execute("CREATE TABLE fetch1 (id INTEGER, data TEXT)")
        database.execute("INSERT INTO fetch1 (id, data) VALUES (?, ?)", (1, "data1"))
        
        row = database.fetch_one("SELECT * FROM fetch1 WHERE id = ?", (1,))
        assert row["data"] == "data1"
    
    def test_fetch_all(self, database):
        """Test direct fetch_all method."""
        database.execute("CREATE TABLE fetch_all (id INTEGER, name TEXT)")
        database.execute("INSERT INTO fetch_all (id, name) VALUES (?, ?)", (1, "A"))
        database.execute("INSERT INTO fetch_all (id, name) VALUES (?, ?)", (2, "B"))
        
        rows = database.fetch_all("SELECT * FROM fetch_all ORDER BY id")
        assert len(rows) == 2


# ============== Migration Tests ==============

class TestMigration:
    """Test Migration dataclass."""
    
    def test_migration_creation(self):
        """Test creating a migration."""
        migration = Migration(
            version=1,
            name="create_test_table",
            up_sql="CREATE TABLE test (id INTEGER)",
            down_sql="DROP TABLE test"
        )
        
        assert migration.version == 1
        assert migration.name == "create_test_table"


class TestMigrationManager:
    """Test MigrationManager class."""
    
    def test_manager_creates_migrations_table(self, database):
        """Test manager creates migrations tracking table."""
        manager = MigrationManager(database)
        
        result = database.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
        )
        assert result is not None
    
    def test_add_migration(self, database):
        """Test adding migration to manager."""
        manager = MigrationManager(database)
        
        migration = Migration(1, "test", "CREATE TABLE t(id INT)", "DROP TABLE t")
        manager.add_migration(migration)
        
        assert len(manager._migrations) == 1
    
    def test_migrations_sorted_by_version(self, database):
        """Test migrations are sorted by version."""
        manager = MigrationManager(database)
        
        manager.add_migration(Migration(3, "third", "", ""))
        manager.add_migration(Migration(1, "first", "", ""))
        manager.add_migration(Migration(2, "second", "", ""))
        
        assert manager._migrations[0].version == 1
        assert manager._migrations[2].version == 3
    
    def test_get_current_version_initial(self, database):
        """Test initial version is 0."""
        manager = MigrationManager(database)
        
        version = manager.get_current_version()
        assert version == 0
    
    def test_get_pending_migrations(self, database):
        """Test getting pending migrations."""
        manager = MigrationManager(database)
        
        manager.add_migration(Migration(1, "m1", "CREATE TABLE m1(id INT)", ""))
        manager.add_migration(Migration(2, "m2", "CREATE TABLE m2(id INT)", ""))
        
        pending = manager.get_pending_migrations()
        assert len(pending) == 2
    
    def test_migrate_applies_pending(self, database):
        """Test migrate applies pending migrations."""
        manager = MigrationManager(database)
        
        manager.add_migration(Migration(1, "create_t1", "CREATE TABLE t1(id INT)", "DROP TABLE t1"))
        manager.add_migration(Migration(2, "create_t2", "CREATE TABLE t2(id INT)", "DROP TABLE t2"))
        
        applied = manager.migrate()
        
        assert len(applied) == 2
        assert manager.get_current_version() == 2
    
    def test_migrate_to_target_version(self, database):
        """Test migrate to specific target version."""
        manager = MigrationManager(database)
        
        manager.add_migration(Migration(1, "m1", "CREATE TABLE m1(id INT)", ""))
        manager.add_migration(Migration(2, "m2", "CREATE TABLE m2(id INT)", ""))
        manager.add_migration(Migration(3, "m3", "CREATE TABLE m3(id INT)", ""))
        
        applied = manager.migrate(target_version=2)
        
        assert len(applied) == 2
        assert manager.get_current_version() == 2
    
    def test_migrate_skips_applied(self, database):
        """Test migrate skips already applied migrations."""
        manager = MigrationManager(database)
        
        manager.add_migration(Migration(1, "m1", "CREATE TABLE skip_test(id INT)", ""))
        manager.migrate()
        
        # Try to migrate again
        applied = manager.migrate()
        assert len(applied) == 0
    
    def test_rollback(self, database):
        """Test rolling back migrations."""
        manager = MigrationManager(database)
        
        manager.add_migration(Migration(1, "rb1", "CREATE TABLE rb1(id INT)", "DROP TABLE rb1"))
        manager.add_migration(Migration(2, "rb2", "CREATE TABLE rb2(id INT)", "DROP TABLE rb2"))
        
        manager.migrate()
        assert manager.get_current_version() == 2
        
        rolled_back = manager.rollback(steps=1)
        
        assert len(rolled_back) == 1
        assert manager.get_current_version() == 1


# ============== DEFAULT_MIGRATIONS Tests ==============

class TestDefaultMigrations:
    """Test default migrations."""
    
    def test_default_migrations_exist(self):
        """Test default migrations are defined."""
        assert len(DEFAULT_MIGRATIONS) >= 5
    
    def test_default_migrations_versions(self):
        """Test default migrations have sequential versions."""
        versions = [m.version for m in DEFAULT_MIGRATIONS]
        assert versions == sorted(versions)
        assert versions == list(range(1, len(DEFAULT_MIGRATIONS) + 1))
    
    def test_apply_default_migrations(self, database):
        """Test applying default migrations."""
        manager = MigrationManager(database)
        
        for migration in DEFAULT_MIGRATIONS:
            manager.add_migration(migration)
        
        applied = manager.migrate()
        
        assert len(applied) == len(DEFAULT_MIGRATIONS)
        
        # Verify tables exist
        tables = database.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = [t["name"] for t in tables]
        
        assert "users" in table_names
        assert "tenants" in table_names
        assert "reconciliation_results" in table_names


# ============== Repository Tests ==============

class TestRepository:
    """Test Repository abstract class."""
    
    def test_repository_implementation(self, database):
        """Test implementing a repository."""
        from dataclasses import dataclass
        
        @dataclass
        class Item:
            id: str
            name: str
            value: int
        
        class ItemRepository(Repository[Item]):
            def _to_entity(self, row):
                return Item(
                    id=row["id"],
                    name=row["name"],
                    value=row["value"]
                )
            
            def _to_row(self, entity):
                return {
                    "id": entity.id,
                    "name": entity.name,
                    "value": entity.value
                }
        
        # Create table
        database.execute(
            "CREATE TABLE items (id TEXT PRIMARY KEY, name TEXT, value INTEGER)"
        )
        
        repo = ItemRepository(database, "items")
        
        # Test save
        item = Item(id="item-1", name="Test Item", value=100)
        saved = repo.save(item)
        assert saved.name == "Test Item"
        
        # Test find_by_id
        found = repo.find_by_id("item-1")
        assert found is not None
        assert found.value == 100
        
        # Test find_all
        repo.save(Item(id="item-2", name="Item 2", value=200))
        all_items = repo.find_all()
        assert len(all_items) == 2
        
        # Test count
        count = repo.count()
        assert count == 2
        
        # Test delete
        repo.delete("item-1")
        assert repo.count() == 1


# ============== Global Functions Tests ==============

class TestGlobalFunctions:
    """Test global database functions."""
    
    def test_get_database(self):
        """Test getting global database instance."""
        db = get_database()
        assert db is not None
        assert isinstance(db, Database)
    
    def test_init_database(self, tmp_path):
        """Test initializing database with migrations."""
        config = DatabaseConfig(
            sqlite_path=str(tmp_path / "init_test.db")
        )
        
        db = init_database(config)
        
        assert db is not None
        
        # Check migrations were applied
        result = db.fetch_one(
            "SELECT MAX(version) as version FROM migrations"
        )
        assert result["version"] == len(DEFAULT_MIGRATIONS)
    
    def test_close_database(self, tmp_path):
        """Test closing global database."""
        config = DatabaseConfig(
            sqlite_path=str(tmp_path / "close_test.db")
        )
        init_database(config)
        
        close_database()
        # Should not raise


# ============== Thread Safety Tests ==============

class TestThreadSafety:
    """Test thread safety of database operations."""
    
    def test_concurrent_reads(self, database):
        """Test concurrent read operations."""
        database.execute("CREATE TABLE concurrent_read (id INTEGER, data TEXT)")
        for i in range(10):
            database.execute(
                "INSERT INTO concurrent_read (id, data) VALUES (?, ?)",
                (i, f"data_{i}")
            )
        
        results = []
        errors = []
        
        def read_data(thread_id):
            try:
                rows = database.fetch_all("SELECT * FROM concurrent_read")
                results.append((thread_id, len(rows)))
            except Exception as e:
                errors.append(str(e))
        
        threads = [
            threading.Thread(target=read_data, args=(i,))
            for i in range(5)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert all(count == 10 for _, count in results)
    
    def test_concurrent_writes(self, database):
        """Test concurrent write operations."""
        database.execute(
            "CREATE TABLE concurrent_write (id INTEGER PRIMARY KEY, thread_id INTEGER)"
        )
        
        errors = []
        
        def write_data(thread_id):
            try:
                for i in range(5):
                    database.execute(
                        "INSERT INTO concurrent_write (thread_id) VALUES (?)",
                        (thread_id,)
                    )
            except Exception as e:
                errors.append(str(e))
        
        threads = [
            threading.Thread(target=write_data, args=(i,))
            for i in range(3)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        
        count = database.fetch_one("SELECT COUNT(*) as count FROM concurrent_write")
        assert count["count"] == 15  # 3 threads * 5 inserts
