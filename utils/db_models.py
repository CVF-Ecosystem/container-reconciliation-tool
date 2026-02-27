# File: utils/db_models.py — @2026 v1.0
"""
SQLAlchemy ORM models for the application database.

Replaces JSON file-based storage with proper relational database.
Supports SQLite (development) and PostgreSQL (production).
"""

from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer,
    ForeignKey, Index, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship, Session
from sqlalchemy.pool import StaticPool
import logging


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class UserModel(Base):
    """User account model."""
    __tablename__ = "users"
    
    id = Column(String(32), primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    api_keys = relationship("ApiKeyModel", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


class ApiKeyModel(Base):
    """API key model for machine-to-machine authentication."""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationships
    user = relationship("UserModel", back_populates="api_keys")
    
    def __repr__(self):
        return f"<ApiKey(id={self.id}, user_id={self.user_id})>"


class RevokedTokenModel(Base):
    """Revoked JWT tokens (for logout/invalidation)."""
    __tablename__ = "revoked_tokens"
    
    token_hash = Column(String(64), primary_key=True)
    revoked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    # Index for cleanup queries
    __table_args__ = (
        Index("idx_revoked_expires", "expires_at"),
    )
    
    def __repr__(self):
        return f"<RevokedToken(hash={self.token_hash[:8]}...)>"


class DatabaseManager:
    """
    Database connection and session manager.
    
    Supports SQLite (default) and PostgreSQL.
    Uses SQLAlchemy for ORM and connection pooling.
    
    Usage:
        db = DatabaseManager()
        with db.session() as session:
            user = session.query(UserModel).filter_by(username="admin").first()
    """
    
    _instance = None
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: SQLAlchemy database URL.
                SQLite: "sqlite:///./data/app.db"
                PostgreSQL: "postgresql://user:pass@host/dbname"
                In-memory (testing): "sqlite:///:memory:"
        """
        import os
        
        if database_url is None:
            # Default: SQLite in data directory
            db_path = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
            database_url = db_path
        
        self.database_url = database_url
        
        # Configure engine based on database type
        if "sqlite" in database_url:
            if ":memory:" in database_url:
                # In-memory SQLite for testing
                self._engine = create_engine(
                    database_url,
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                    echo=False
                )
            else:
                self._engine = create_engine(
                    database_url,
                    connect_args={"check_same_thread": False},
                    echo=False
                )
                # Enable WAL mode for better concurrent access
                @event.listens_for(self._engine, "connect")
                def set_sqlite_pragma(dbapi_conn, connection_record):
                    cursor = dbapi_conn.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()
        else:
            # PostgreSQL or other databases
            self._engine = create_engine(database_url, echo=False)
        
        # Create all tables
        Base.metadata.create_all(self._engine)
        logging.info(f"Database initialized: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    @classmethod
    def get_instance(cls, database_url: Optional[str] = None) -> "DatabaseManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(database_url)
        return cls._instance
    
    def session(self):
        """
        Get a database session (context manager).
        
        Usage:
            with db.session() as session:
                session.add(user)
                session.commit()
        """
        @contextmanager
        def _session():
            session = Session(self._engine)
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        
        return _session()
    
    def cleanup_expired_tokens(self) -> int:
        """Remove expired revoked tokens from database."""
        with self.session() as session:
            deleted = session.query(RevokedTokenModel).filter(
                RevokedTokenModel.expires_at < datetime.utcnow()
            ).delete()
            return deleted
    
    def close(self):
        """Close database connections."""
        self._engine.dispose()
