# File: utils/tenant.py
"""
Multi-Tenant Support Module for Container Inventory Reconciliation Tool.

V5.4 - Phase 3: Enterprise Ready
Features:
- Tenant isolation for data and configurations
- Tenant-specific settings
- Cross-tenant admin operations
- Tenant context management
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import json
import threading
from contextlib import contextmanager


class TenantStatus(Enum):
    """Tenant status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    ARCHIVED = "archived"


@dataclass
class TenantConfig:
    """Tenant-specific configuration."""
    # Data paths
    input_dir: str = "data_input"
    output_dir: str = "data_output"
    
    # Processing settings
    default_time_slot: str = "8H-15H"
    include_cfs: bool = True
    auto_export_email: bool = False
    
    # Email settings
    email_recipients: List[str] = field(default_factory=list)
    email_enabled: bool = False
    
    # Feature flags
    enable_pdf_export: bool = True
    enable_dashboard: bool = True
    enable_api: bool = True
    
    # Limits
    max_files_per_batch: int = 100
    max_export_rows: int = 100000
    retention_days: int = 90
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "input_dir": self.input_dir,
            "output_dir": self.output_dir,
            "default_time_slot": self.default_time_slot,
            "include_cfs": self.include_cfs,
            "auto_export_email": self.auto_export_email,
            "email_recipients": self.email_recipients,
            "email_enabled": self.email_enabled,
            "enable_pdf_export": self.enable_pdf_export,
            "enable_dashboard": self.enable_dashboard,
            "enable_api": self.enable_api,
            "max_files_per_batch": self.max_files_per_batch,
            "max_export_rows": self.max_export_rows,
            "retention_days": self.retention_days,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TenantConfig":
        """Create from dictionary."""
        return cls(
            input_dir=data.get("input_dir", "data_input"),
            output_dir=data.get("output_dir", "data_output"),
            default_time_slot=data.get("default_time_slot", "8H-15H"),
            include_cfs=data.get("include_cfs", True),
            auto_export_email=data.get("auto_export_email", False),
            email_recipients=data.get("email_recipients", []),
            email_enabled=data.get("email_enabled", False),
            enable_pdf_export=data.get("enable_pdf_export", True),
            enable_dashboard=data.get("enable_dashboard", True),
            enable_api=data.get("enable_api", True),
            max_files_per_batch=data.get("max_files_per_batch", 100),
            max_export_rows=data.get("max_export_rows", 100000),
            retention_days=data.get("retention_days", 90),
        )


@dataclass
class Tenant:
    """Tenant model representing a container yard or organization."""
    id: str
    name: str
    code: str  # Short code (e.g., "TTT" for Tien-Tan Thuan)
    status: TenantStatus = TenantStatus.ACTIVE
    config: TenantConfig = field(default_factory=TenantConfig)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_input_path(self, base_path: Path) -> Path:
        """Get tenant-specific input directory."""
        return base_path / self.code / self.config.input_dir
    
    def get_output_path(self, base_path: Path) -> Path:
        """Get tenant-specific output directory."""
        return base_path / self.code / self.config.output_dir
    
    def is_active(self) -> bool:
        """Check if tenant is active."""
        return self.status == TenantStatus.ACTIVE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "status": self.status.value,
            "config": self.config.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tenant":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            code=data["code"],
            status=TenantStatus(data.get("status", "active")),
            config=TenantConfig.from_dict(data.get("config", {})),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            metadata=data.get("metadata", {}),
        )


class TenantStore:
    """Tenant storage and management."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("./data/tenants.json")
        self._tenants: Dict[str, Tenant] = {}
        self._lock = threading.Lock()
        self._load_tenants()
    
    def _load_tenants(self):
        """Load tenants from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for tenant_data in data.get("tenants", []):
                        tenant = Tenant.from_dict(tenant_data)
                        self._tenants[tenant.id] = tenant
                logging.info(f"Loaded {len(self._tenants)} tenants")
            except Exception as e:
                logging.error(f"Error loading tenants: {e}")
        
        # Create default tenant if none exist
        if not self._tenants:
            self._create_default_tenant()
    
    def _save_tenants(self):
        """Save tenants to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tenants": [t.to_dict() for t in self._tenants.values()]
        }
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _create_default_tenant(self):
        """Create default tenant."""
        import secrets
        default = Tenant(
            id=secrets.token_hex(16),
            name="Cảng Tân Thuận",
            code="TTT",
            status=TenantStatus.ACTIVE,
            metadata={"is_default": True}
        )
        self._tenants[default.id] = default
        self._save_tenants()
        logging.info(f"Created default tenant: {default.name}")
    
    def create_tenant(
        self,
        name: str,
        code: str,
        config: Optional[TenantConfig] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tenant:
        """Create a new tenant."""
        import secrets
        
        with self._lock:
            # Check for duplicate code
            for tenant in self._tenants.values():
                if tenant.code == code:
                    raise ValueError(f"Tenant code '{code}' already exists")
            
            tenant = Tenant(
                id=secrets.token_hex(16),
                name=name,
                code=code,
                config=config or TenantConfig(),
                metadata=metadata or {}
            )
            self._tenants[tenant.id] = tenant
            self._save_tenants()
            
            logging.info(f"Created tenant: {name} ({code})")
            return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return self._tenants.get(tenant_id)
    
    def get_tenant_by_code(self, code: str) -> Optional[Tenant]:
        """Get tenant by code."""
        for tenant in self._tenants.values():
            if tenant.code == code:
                return tenant
        return None
    
    def get_default_tenant(self) -> Optional[Tenant]:
        """Get default tenant."""
        for tenant in self._tenants.values():
            if tenant.metadata.get("is_default"):
                return tenant
        # Return first active tenant if no default
        for tenant in self._tenants.values():
            if tenant.is_active():
                return tenant
        return None
    
    def update_tenant(self, tenant_id: str, **kwargs) -> Optional[Tenant]:
        """Update tenant fields."""
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                return None
            
            for key, value in kwargs.items():
                if key == "config" and isinstance(value, dict):
                    tenant.config = TenantConfig.from_dict(value)
                elif key == "status" and isinstance(value, str):
                    tenant.status = TenantStatus(value)
                elif hasattr(tenant, key) and key != "id":
                    setattr(tenant, key, value)
            
            tenant.updated_at = datetime.now()
            self._save_tenants()
            return tenant
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant (soft delete - archive)."""
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                return False
            
            if tenant.metadata.get("is_default"):
                raise ValueError("Cannot delete default tenant")
            
            tenant.status = TenantStatus.ARCHIVED
            tenant.updated_at = datetime.now()
            self._save_tenants()
            return True
    
    def list_tenants(self, include_archived: bool = False) -> List[Tenant]:
        """List all tenants."""
        tenants = list(self._tenants.values())
        if not include_archived:
            tenants = [t for t in tenants if t.status != TenantStatus.ARCHIVED]
        return tenants


class TenantContext:
    """Thread-local tenant context manager."""
    
    _local = threading.local()
    
    @classmethod
    def get_current_tenant(cls) -> Optional[Tenant]:
        """Get current tenant from context."""
        return getattr(cls._local, 'tenant', None)
    
    @classmethod
    def set_current_tenant(cls, tenant: Optional[Tenant]):
        """Set current tenant in context."""
        cls._local.tenant = tenant
    
    @classmethod
    @contextmanager
    def tenant_scope(cls, tenant: Tenant):
        """Context manager for tenant scope."""
        previous = cls.get_current_tenant()
        try:
            cls.set_current_tenant(tenant)
            yield tenant
        finally:
            cls.set_current_tenant(previous)


class TenantManager:
    """Main tenant management class."""
    
    def __init__(
        self,
        store: Optional[TenantStore] = None,
        base_data_path: Optional[Path] = None
    ):
        self.store = store or TenantStore()
        self.base_data_path = base_data_path or Path("./data")
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return self.store.get_tenant(tenant_id)
    
    def get_tenant_by_code(self, code: str) -> Optional[Tenant]:
        """Get tenant by code."""
        return self.store.get_tenant_by_code(code)
    
    def get_current_tenant(self) -> Optional[Tenant]:
        """Get current tenant from context or default."""
        tenant = TenantContext.get_current_tenant()
        if tenant:
            return tenant
        return self.store.get_default_tenant()
    
    def create_tenant(
        self,
        name: str,
        code: str,
        config: Optional[TenantConfig] = None,
        setup_directories: bool = True
    ) -> Tenant:
        """Create a new tenant with optional directory setup."""
        tenant = self.store.create_tenant(name, code, config)
        
        if setup_directories:
            self._setup_tenant_directories(tenant)
        
        return tenant
    
    def _setup_tenant_directories(self, tenant: Tenant):
        """Create tenant-specific directories."""
        input_path = tenant.get_input_path(self.base_data_path)
        output_path = tenant.get_output_path(self.base_data_path)
        
        input_path.mkdir(parents=True, exist_ok=True)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"Created directories for tenant {tenant.code}")
    
    def get_tenant_input_path(self, tenant: Optional[Tenant] = None) -> Path:
        """Get input path for tenant."""
        tenant = tenant or self.get_current_tenant()
        if not tenant:
            return self.base_data_path / "data_input"
        return tenant.get_input_path(self.base_data_path)
    
    def get_tenant_output_path(self, tenant: Optional[Tenant] = None) -> Path:
        """Get output path for tenant."""
        tenant = tenant or self.get_current_tenant()
        if not tenant:
            return self.base_data_path / "data_output"
        return tenant.get_output_path(self.base_data_path)
    
    def switch_tenant(self, tenant_id: str) -> bool:
        """Switch to a different tenant."""
        tenant = self.store.get_tenant(tenant_id)
        if not tenant or not tenant.is_active():
            return False
        
        TenantContext.set_current_tenant(tenant)
        logging.info(f"Switched to tenant: {tenant.name}")
        return True
    
    def list_tenants(self) -> List[Tenant]:
        """List all active tenants."""
        return self.store.list_tenants()
    
    @contextmanager
    def tenant_scope(self, tenant_or_id):
        """Context manager for tenant operations."""
        if isinstance(tenant_or_id, str):
            tenant = self.store.get_tenant(tenant_or_id)
        else:
            tenant = tenant_or_id
        
        if not tenant:
            raise ValueError("Tenant not found")
        
        with TenantContext.tenant_scope(tenant):
            yield tenant


# Decorator for tenant-aware operations
def require_tenant(func):
    """
    Decorator to require a tenant context.
    
    Usage:
        @require_tenant
        def process_data():
            tenant = TenantContext.get_current_tenant()
            ...
    """
    def wrapper(*args, **kwargs):
        tenant = TenantContext.get_current_tenant()
        if not tenant:
            raise ValueError("No tenant context set")
        if not tenant.is_active():
            raise ValueError(f"Tenant '{tenant.name}' is not active")
        return func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# Global tenant manager instance
_tenant_manager: Optional[TenantManager] = None


def get_tenant_manager() -> TenantManager:
    """Get global tenant manager instance."""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager


def init_tenant_manager(
    storage_path: Optional[Path] = None,
    base_data_path: Optional[Path] = None
) -> TenantManager:
    """Initialize tenant manager with custom settings."""
    global _tenant_manager
    store = TenantStore(storage_path) if storage_path else None
    _tenant_manager = TenantManager(store, base_data_path)
    return _tenant_manager
