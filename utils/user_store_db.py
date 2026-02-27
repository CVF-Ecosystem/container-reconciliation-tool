# File: utils/user_store_db.py — @2026 v1.0
"""
SQLAlchemy-based UserStore replacing JSON file storage.

Drop-in replacement for the JSON-based UserStore in utils/auth.py.
Provides the same interface but with proper database persistence.
"""

import hashlib
import secrets
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from sqlalchemy.orm import joinedload
from utils.db_models import DatabaseManager, UserModel, ApiKeyModel, RevokedTokenModel
from utils.auth import User, Role, PasswordHasher


class UserStoreDB:
    """
    Database-backed user store using SQLAlchemy.
    
    Replaces the JSON file-based UserStore with proper relational storage.
    Supports SQLite (development) and PostgreSQL (production).
    
    Usage:
        store = UserStoreDB()  # Uses DATABASE_URL env var or SQLite default
        user = store.create_user("admin", "admin@example.com", "password", Role.ADMIN)
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize with database connection.
        
        Args:
            database_url: SQLAlchemy URL. Defaults to DATABASE_URL env var or SQLite.
        """
        self._db = DatabaseManager.get_instance(database_url)
    
    def _model_to_user(self, model: UserModel) -> User:
        """Convert SQLAlchemy model to User dataclass."""
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            password_hash=model.password_hash,
            role=Role(model.role),
            is_active=model.is_active,
            created_at=model.created_at,
            last_login=model.last_login,
            metadata={
                "api_keys": [
                    {
                        "key_hash": k.key_hash,
                        "description": k.description,
                        "created_at": k.created_at.isoformat() if k.created_at else None,
                        "last_used": k.last_used.isoformat() if k.last_used else None,
                    }
                    for k in model.api_keys if k.is_active
                ]
            }
        )
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: Role = Role.VIEWER
    ) -> User:
        """Create a new user."""
        with self._db.session() as session:
            # Check for existing username/email
            existing = session.query(UserModel).options(
                joinedload(UserModel.api_keys)
            ).filter(
                (UserModel.username == username) | (UserModel.email == email)
            ).first()
            
            if existing:
                if existing.username == username:
                    raise ValueError(f"Username '{username}' already exists")
                raise ValueError(f"Email '{email}' already exists")
            
            model = UserModel(
                id=secrets.token_hex(16),
                username=username,
                email=email,
                password_hash=PasswordHasher.hash_password(password),
                role=role.value,
                is_active=True,
                created_at=datetime.utcnow()
            )
            session.add(model)
            session.flush()  # Get the ID
            
            logging.info(f"Created user: {username} ({role.value})")
            return self._model_to_user(model)
    
    def _query_user(self, session, **filters) -> Optional[UserModel]:
        """Query user with eager-loaded api_keys to avoid lazy-load after session close."""
        return session.query(UserModel).options(
            joinedload(UserModel.api_keys)
        ).filter_by(**filters).first()
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        with self._db.session() as session:
            model = self._query_user(session, id=user_id)
            return self._model_to_user(model) if model else None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        with self._db.session() as session:
            model = self._query_user(session, username=username)
            return self._model_to_user(model) if model else None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        with self._db.session() as session:
            model = self._query_user(session, email=email)
            return self._model_to_user(model) if model else None
    
    def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        """Update user fields."""
        with self._db.session() as session:
            model = session.query(UserModel).filter_by(id=user_id).first()
            if not model:
                return None
            
            for key, value in kwargs.items():
                if key == "password":
                    model.password_hash = PasswordHasher.hash_password(value)
                elif key == "role" and isinstance(value, str):
                    model.role = value
                elif key == "role" and isinstance(value, Role):
                    model.role = value.value
                elif hasattr(model, key) and key != "id":
                    setattr(model, key, value)
            
            return self._model_to_user(model)
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        with self._db.session() as session:
            model = session.query(UserModel).filter_by(id=user_id).first()
            if model:
                session.delete(model)
                return True
            return False
    
    def list_users(self) -> List[User]:
        """List all users."""
        with self._db.session() as session:
            models = session.query(UserModel).options(
                joinedload(UserModel.api_keys)
            ).all()
            return [self._model_to_user(m) for m in models]
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        with self._db.session() as session:
            model = self._query_user(session, username=username)
            if not model:
                return None
            
            if not model.is_active:
                logging.warning(f"Inactive user attempted login: {username}")
                return None
            
            if PasswordHasher.verify_password(password, model.password_hash):
                model.last_login = datetime.utcnow()
                logging.info(f"User authenticated: {username}")
                return self._model_to_user(model)
            
            logging.warning(f"Failed login attempt for: {username}")
            return None
    
    # ============ API KEY MANAGEMENT ============
    
    def create_api_key(self, user_id: str, description: str = "") -> Optional[str]:
        """
        Create a new API key for a user.
        
        Returns the raw key (shown only once).
        """
        with self._db.session() as session:
            user = session.query(UserModel).filter_by(id=user_id).first()
            if not user:
                return None
            
            raw_key = f"ak_{secrets.token_urlsafe(32)}"
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            
            api_key = ApiKeyModel(
                user_id=user_id,
                key_hash=key_hash,
                description=description,
                created_at=datetime.utcnow(),
                is_active=True
            )
            session.add(api_key)
            
            logging.info(f"Created API key for user: {user.username}")
            return raw_key
    
    def verify_api_key(self, raw_key: str) -> Optional[User]:
        """Verify API key and return associated user."""
        if not raw_key or not raw_key.startswith('ak_'):
            return None
        
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        with self._db.session() as session:
            api_key = session.query(ApiKeyModel).filter_by(
                key_hash=key_hash,
                is_active=True
            ).first()
            
            if not api_key:
                return None
            
            user = session.query(UserModel).filter_by(
                id=api_key.user_id,
                is_active=True
            ).first()
            
            if not user:
                return None
            
            # Update last_used
            api_key.last_used = datetime.utcnow()
            
            return self._model_to_user(user)
    
    def revoke_api_key(self, user_id: str, key_hash: str) -> bool:
        """Revoke an API key."""
        with self._db.session() as session:
            api_key = session.query(ApiKeyModel).filter_by(
                user_id=user_id,
                key_hash=key_hash
            ).first()
            
            if api_key:
                api_key.is_active = False
                return True
            return False
    
    # ============ TOKEN REVOCATION ============
    
    def revoke_token(self, token_hash: str, expires_at: Optional[datetime] = None):
        """Add token hash to revocation list."""
        with self._db.session() as session:
            revoked = RevokedTokenModel(
                token_hash=token_hash,
                revoked_at=datetime.utcnow(),
                expires_at=expires_at
            )
            session.merge(revoked)  # INSERT OR REPLACE
    
    def is_token_revoked(self, token_hash: str) -> bool:
        """Check if token is revoked."""
        with self._db.session() as session:
            revoked = session.query(RevokedTokenModel).filter_by(
                token_hash=token_hash
            ).first()
            
            if not revoked:
                return False
            
            # Check if expired (auto-cleanup)
            if revoked.expires_at and revoked.expires_at < datetime.utcnow():
                session.delete(revoked)
                return False
            
            return True
    
    def cleanup_expired_tokens(self) -> int:
        """Remove expired revoked tokens."""
        return self._db.cleanup_expired_tokens()
