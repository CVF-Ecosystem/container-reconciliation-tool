# File: utils/auth.py — @2026 v1.0
"""
Authentication & Authorization Module for Container Inventory Reconciliation Tool.

V5.4 - Phase 3: Enterprise Ready
Features:
- JWT token-based authentication
- Role-based access control (RBAC)
- Password hashing with bcrypt
- Token refresh mechanism
- User management
"""

import hashlib
import os
import secrets
import sqlite3
import logging
import base64
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

# JWT imports (optional - fallback to simple tokens if not available)
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logging.warning("PyJWT not installed. Using simple token authentication.")

# Bcrypt for password hashing (optional)
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    logging.warning("bcrypt not installed. Using SHA256 for password hashing.")


class Role(Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    API = "api"


class Permission(Enum):
    """Permissions for different operations."""
    # Read permissions
    VIEW_REPORTS = "view_reports"
    VIEW_AUDIT = "view_audit"
    VIEW_DASHBOARD = "view_dashboard"
    
    # Write permissions
    RUN_RECONCILIATION = "run_reconciliation"
    EXPORT_DATA = "export_data"
    SEND_EMAIL = "send_email"
    
    # Admin permissions
    MANAGE_USERS = "manage_users"
    MANAGE_CONFIG = "manage_config"
    VIEW_LOGS = "view_logs"
    MANAGE_SYSTEM = "manage_system"


# Role-Permission mapping
ROLE_PERMISSIONS: Dict[Role, List[Permission]] = {
    Role.ADMIN: list(Permission),  # All permissions
    Role.OPERATOR: [
        Permission.VIEW_REPORTS,
        Permission.VIEW_AUDIT,
        Permission.VIEW_DASHBOARD,
        Permission.RUN_RECONCILIATION,
        Permission.EXPORT_DATA,
        Permission.SEND_EMAIL,
    ],
    Role.VIEWER: [
        Permission.VIEW_REPORTS,
        Permission.VIEW_DASHBOARD,
    ],
    Role.API: [
        Permission.VIEW_REPORTS,
        Permission.RUN_RECONCILIATION,
        Permission.EXPORT_DATA,
    ],
}


@dataclass
class User:
    """User model."""
    id: str
    username: str
    email: str
    password_hash: str
    role: Role
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in ROLE_PERMISSIONS.get(self.role, [])
    
    def get_permissions(self) -> List[Permission]:
        """Get all permissions for user's role."""
        return ROLE_PERMISSIONS.get(self.role, [])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary (excluding password)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


@dataclass
class TokenData:
    """JWT token payload data."""
    user_id: str
    username: str
    role: str
    permissions: List[str]
    exp: datetime
    iat: datetime = field(default_factory=datetime.now)
    token_type: str = "access"


class PasswordHasher:
    """Password hashing utility."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt or SHA256."""
        if BCRYPT_AVAILABLE:
            salt = bcrypt.gensalt(rounds=12)
            return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        else:
            # Fallback to SHA256 with salt
            salt = secrets.token_hex(16)
            hash_obj = hashlib.sha256((password + salt).encode('utf-8'))
            return f"sha256${salt}${hash_obj.hexdigest()}"
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        if BCRYPT_AVAILABLE and not password_hash.startswith("sha256$"):
            try:
                return bcrypt.checkpw(
                    password.encode('utf-8'),
                    password_hash.encode('utf-8')
                )
            except Exception:
                return False
        else:
            # SHA256 verification
            if not password_hash.startswith("sha256$"):
                return False
            parts = password_hash.split("$")
            if len(parts) != 3:
                return False
            _, salt, stored_hash = parts
            hash_obj = hashlib.sha256((password + salt).encode('utf-8'))
            return hash_obj.hexdigest() == stored_hash


class TokenManager:
    """JWT token management."""
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
        revoked_tokens_db_path: Optional[Path] = None
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = timedelta(minutes=access_token_expire_minutes)
        self.refresh_token_expire = timedelta(days=refresh_token_expire_days)
        # In-memory cache + SQLite persistence để tránh mất khi restart
        self._revoked_tokens: set = set()
        self._revoked_db_path = revoked_tokens_db_path
        if self._revoked_db_path:
            self._init_revoked_db()
            self._load_revoked_tokens()
    
    def create_access_token(self, user: User) -> str:
        """Create JWT access token."""
        now = datetime.utcnow()
        expire = now + self.access_token_expire
        
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value,
            "permissions": [p.value for p in user.get_permissions()],
            "exp": expire,
            "iat": now,
            "type": "access"
        }
        
        if JWT_AVAILABLE:
            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        else:
            return self._encode_simple_token(payload)
    
    def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token."""
        now = datetime.utcnow()
        expire = now + self.refresh_token_expire
        
        payload = {
            "sub": user.id,
            "exp": expire,
            "iat": now,
            "type": "refresh",
            "jti": secrets.token_hex(16)  # Unique token ID
        }
        
        if JWT_AVAILABLE:
            return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        else:
            return self._encode_simple_token(payload)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token."""
        if self.is_token_revoked(token):
            return None
        
        if JWT_AVAILABLE:
            try:
                payload = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=[self.algorithm]
                )
                return payload
            except jwt.ExpiredSignatureError:
                logging.warning("Token expired")
                return None
            except jwt.InvalidTokenError as e:
                logging.warning(f"Invalid token: {e}")
                return None
        else:
            return self._decode_simple_token(token)

    def _encode_simple_token(self, payload: Dict[str, Any]) -> str:
        token_data = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
        body = base64.urlsafe_b64encode(token_data).decode("ascii").rstrip("=")
        signature = hmac.new(self.secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{body}.{signature}"

    def _decode_simple_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            body, signature = token.rsplit(".", 1)
            expected = hmac.new(self.secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None

            padded = body + "=" * (-len(body) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
            exp = payload.get("exp")
            if exp and datetime.fromisoformat(str(exp)) < datetime.utcnow():
                logging.warning("Token expired")
                return None
            return payload
        except Exception as e:
            logging.warning(f"Invalid fallback token: {e}")
            return None
    
    def _init_revoked_db(self):
        """Khởi tạo bảng revoked_tokens trong SQLite."""
        self._revoked_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._revoked_db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    token_hash TEXT PRIMARY KEY,
                    revoked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME
                )
            """)
            conn.commit()
    
    def _load_revoked_tokens(self):
        """Load revoked tokens từ SQLite vào in-memory set."""
        try:
            with sqlite3.connect(str(self._revoked_db_path)) as conn:
                # Chỉ load token chưa hết hạn
                rows = conn.execute(
                    "SELECT token_hash FROM revoked_tokens WHERE expires_at > datetime('now') OR expires_at IS NULL"
                ).fetchall()
                self._revoked_tokens = {row[0] for row in rows}
                logging.debug(f"Loaded {len(self._revoked_tokens)} revoked tokens from DB")
        except Exception as e:
            logging.warning(f"Could not load revoked tokens: {e}")
    
    def _hash_token(self, token: str) -> str:
        """Hash token để lưu vào DB (không lưu token gốc)."""
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()
    
    def revoke_token(self, token: str):
        """Revoke a token (logout). Persist vào SQLite nếu có DB."""
        token_hash = self._hash_token(token)
        self._revoked_tokens.add(token_hash)
        
        if self._revoked_db_path:
            try:
                # Tính expiry time từ token nếu có thể
                expires_at = None
                if JWT_AVAILABLE:
                    try:
                        payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], options={"verify_exp": False})
                        exp = payload.get("exp")
                        if exp:
                            from datetime import timezone
                            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                
                with sqlite3.connect(str(self._revoked_db_path)) as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO revoked_tokens (token_hash, expires_at) VALUES (?, ?)",
                        (token_hash, expires_at)
                    )
                    conn.commit()
            except Exception as e:
                logging.warning(f"Could not persist revoked token: {e}")
    
    def is_token_revoked(self, token: str) -> bool:
        """Check if token is revoked."""
        token_hash = self._hash_token(token)
        return token_hash in self._revoked_tokens


class UserStore:
    """Simple user storage (JSON file based for development)."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("./data/users.json")
        self._users: Dict[str, User] = {}
        self._load_users()
    
    def _load_users(self):
        """Load users from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_data in data.get("users", []):
                        user = User(
                            id=user_data["id"],
                            username=user_data["username"],
                            email=user_data["email"],
                            password_hash=user_data["password_hash"],
                            role=Role(user_data["role"]),
                            is_active=user_data.get("is_active", True),
                            created_at=datetime.fromisoformat(user_data["created_at"]),
                            last_login=datetime.fromisoformat(user_data["last_login"]) if user_data.get("last_login") else None,
                            metadata=user_data.get("metadata", {}),
                        )
                        self._users[user.id] = user
                logging.info(f"Loaded {len(self._users)} users from storage")
            except Exception as e:
                logging.error(f"Error loading users: {e}")
    
    def _save_users(self):
        """Save users to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "password_hash": u.password_hash,
                    "role": u.role.value,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat(),
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                    "metadata": u.metadata,
                }
                for u in self._users.values()
            ]
        }
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: Role = Role.VIEWER
    ) -> User:
        """Create a new user."""
        # Check for existing username/email
        for user in self._users.values():
            if user.username == username:
                raise ValueError(f"Username '{username}' already exists")
            if user.email == email:
                raise ValueError(f"Email '{email}' already exists")
        
        user = User(
            id=secrets.token_hex(16),
            username=username,
            email=email,
            password_hash=PasswordHasher.hash_password(password),
            role=role
        )
        self._users[user.id] = user
        self._save_users()
        logging.info(f"Created user: {username} ({role.value})")
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        for user in self._users.values():
            if user.username == username:
                return user
        return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        for user in self._users.values():
            if user.email == email:
                return user
        return None
    
    def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        """Update user fields."""
        user = self._users.get(user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if hasattr(user, key) and key != "id":
                if key == "password":
                    user.password_hash = PasswordHasher.hash_password(value)
                elif key == "role" and isinstance(value, str):
                    user.role = Role(value)
                else:
                    setattr(user, key, value)
        
        self._save_users()
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        if user_id in self._users:
            del self._users[user_id]
            self._save_users()
            return True
        return False
    
    def list_users(self) -> List[User]:
        """List all users."""
        return list(self._users.values())
    
    # ============ API KEY MANAGEMENT ============
    
    def create_api_key(self, user_id: str, description: str = "") -> Optional[str]:
        """
        Tạo API key mới cho user.
        
        API key là random token 32 bytes, được hash trước khi lưu.
        Trả về raw key (chỉ hiển thị một lần).
        
        Args:
            user_id: ID của user cần tạo API key
            description: Mô tả mục đích sử dụng API key
        
        Returns:
            Raw API key string (chỉ hiển thị một lần), hoặc None nếu user không tồn tại
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        # Generate random API key
        raw_key = f"ak_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Lưu vào metadata của user
        if 'api_keys' not in user.metadata:
            user.metadata['api_keys'] = []
        
        user.metadata['api_keys'].append({
            'key_hash': key_hash,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'last_used': None
        })
        
        self._save_users()
        logging.info(f"Created API key for user: {user.username}")
        return raw_key
    
    def verify_api_key(self, raw_key: str) -> Optional[User]:
        """
        Xác thực API key và trả về user tương ứng.
        
        Args:
            raw_key: Raw API key từ request header
        
        Returns:
            User nếu key hợp lệ và user active, None nếu không hợp lệ
        """
        if not raw_key or not raw_key.startswith('ak_'):
            return None
        
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        for user in self._users.values():
            if not user.is_active:
                continue
            api_keys = user.metadata.get('api_keys', [])
            for key_entry in api_keys:
                if key_entry.get('key_hash') == key_hash:
                    # Cập nhật last_used
                    key_entry['last_used'] = datetime.now().isoformat()
                    self._save_users()
                    return user
        
        return None
    
    def revoke_api_key(self, user_id: str, key_hash: str) -> bool:
        """Revoke một API key cụ thể."""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        api_keys = user.metadata.get('api_keys', [])
        original_count = len(api_keys)
        user.metadata['api_keys'] = [k for k in api_keys if k.get('key_hash') != key_hash]
        
        if len(user.metadata['api_keys']) < original_count:
            self._save_users()
            return True
        return False
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password."""
        user = self.get_user_by_username(username)
        if not user:
            return None
        
        if not user.is_active:
            logging.warning(f"Inactive user attempted login: {username}")
            return None
        
        if PasswordHasher.verify_password(password, user.password_hash):
            user.last_login = datetime.now()
            self._save_users()
            logging.info(f"User authenticated: {username}")
            return user
        
        logging.warning(f"Failed login attempt for: {username}")
        return None


class AuthManager:
    """Main authentication manager."""
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        user_store: Optional[UserStore] = None,
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7
    ):
        configured_secret = secret_key or os.getenv("JWT_SECRET_KEY") or os.getenv("AUTH_SECRET_KEY")
        server_mode = os.getenv("APP_MODE", "").lower() in {"api-server", "api_server", "server"}
        production_mode = os.getenv("APP_ENV", "").lower() == "production"
        require_stable_secret = os.getenv("REQUIRE_STABLE_JWT_SECRET", "").lower() in {"1", "true", "yes"}
        if not configured_secret and (server_mode or production_mode or require_stable_secret):
            raise RuntimeError(
                "JWT_SECRET_KEY is required in server/production mode. "
                "Set JWT_SECRET_KEY to a stable secret so tokens survive process restarts."
            )
        self.secret_key = configured_secret or secrets.token_hex(32)
        self.user_store = user_store or UserStore()
        self.token_manager = TokenManager(
            secret_key=self.secret_key,
            access_token_expire_minutes=access_token_expire_minutes,
            refresh_token_expire_days=refresh_token_expire_days
        )
        
        # Create default admin if no users exist
        if not self.user_store.list_users():
            self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user.
        
        Password được đọc từ env var ADMIN_DEFAULT_PASSWORD.
        Nếu không có, tự động generate random password an toàn và log ra console.
        """
        import os
        
        # Đọc password từ env var, nếu không có thì generate random
        default_password = os.getenv("ADMIN_DEFAULT_PASSWORD")
        if not default_password:
            default_password = secrets.token_urlsafe(16)
            logging.warning(
                f"[SECURITY] No ADMIN_DEFAULT_PASSWORD env var set. "
                f"Generated random admin password: {default_password}\n"
                f"Please set ADMIN_DEFAULT_PASSWORD env var or change password immediately after first login."
            )
        
        try:
            self.user_store.create_user(
                username="admin",
                email="admin@localhost",
                password=default_password,
                role=Role.ADMIN
            )
            logging.info("Created default admin user (username: admin). Check logs for password if not set via env var.")
        except ValueError:
            pass  # Admin already exists
    
    def login(self, username: str, password: str) -> Optional[Dict[str, str]]:
        """
        Authenticate user and return tokens.
        
        Returns:
            Dict with access_token, refresh_token, and token_type
        """
        user = self.user_store.authenticate(username, password)
        if not user:
            return None
        
        access_token = self.token_manager.create_access_token(user)
        refresh_token = self.token_manager.create_refresh_token(user)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(self.token_manager.access_token_expire.total_seconds()),
            "user": user.to_dict()
        }
    
    def logout(self, token: str):
        """Logout user by revoking token."""
        self.token_manager.revoke_token(token)
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Get new access token using refresh token."""
        payload = self.token_manager.verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        
        user = self.user_store.get_user_by_id(payload["sub"])
        if not user or not user.is_active:
            return None
        
        new_access_token = self.token_manager.create_access_token(user)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": int(self.token_manager.access_token_expire.total_seconds())
        }
    
    def verify_access_token(self, token: str) -> Optional[User]:
        """Verify access token and return user."""
        payload = self.token_manager.verify_token(token)
        if not payload or payload.get("type") != "access":
            return None
        
        user = self.user_store.get_user_by_id(payload["sub"])
        if not user or not user.is_active:
            return None
        
        return user
    
    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has permission."""
        return user.has_permission(permission)
    
    def require_permission(self, user: User, permission: Permission):
        """Raise exception if user lacks permission."""
        if not self.check_permission(user, permission):
            raise PermissionError(
                f"User '{user.username}' lacks permission: {permission.value}"
            )


# Decorator for permission checking
def require_auth(permission: Optional[Permission] = None):
    """
    Decorator to require authentication and optionally check permission.
    
    Usage:
        @require_auth(Permission.RUN_RECONCILIATION)
        def run_reconciliation(user: User, ...):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get user from kwargs or first arg
            user = kwargs.get('user') or (args[0] if args else None)
            
            if not isinstance(user, User):
                raise ValueError("User not provided or invalid")
            
            if not user.is_active:
                raise PermissionError("User account is inactive")
            
            if permission and not user.has_permission(permission):
                raise PermissionError(
                    f"Permission denied: {permission.value}"
                )
            
            return func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


# Global auth manager instance (singleton pattern)
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """Get global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def init_auth(
    secret_key: Optional[str] = None,
    user_storage_path: Optional[Path] = None,
    **kwargs
) -> AuthManager:
    """Initialize auth manager with custom settings."""
    global _auth_manager
    user_store = UserStore(user_storage_path) if user_storage_path else None
    _auth_manager = AuthManager(
        secret_key=secret_key,
        user_store=user_store,
        **kwargs
    )
    return _auth_manager
