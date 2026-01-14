# File: tests/test_tenant.py
"""
Tests for Multi-Tenant Support Module.

V5.4 - Phase 3: Enterprise Ready
"""

import pytest
import json
import threading
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch


# Import modules to test
from utils.tenant import (
    TenantStatus, TenantConfig, Tenant, TenantStore,
    TenantContext, TenantManager, require_tenant,
    get_tenant_manager, init_tenant_manager
)


# ============== Fixtures ==============

@pytest.fixture
def tenant_config():
    """Create test tenant configuration."""
    return TenantConfig(
        input_dir="test_input",
        output_dir="test_output",
        default_time_slot="8H-15H",
        include_cfs=True,
        email_recipients=["test@example.com"],
        email_enabled=True,
        max_files_per_batch=50,
    )


@pytest.fixture
def tenant(tenant_config):
    """Create test tenant."""
    return Tenant(
        id="test-tenant-001",
        name="Test Tenant",
        code="TST",
        status=TenantStatus.ACTIVE,
        config=tenant_config,
        metadata={"test": True}
    )


@pytest.fixture
def tenant_store(tmp_path):
    """Create tenant store with temp storage."""
    storage_path = tmp_path / "tenants.json"
    return TenantStore(storage_path)


@pytest.fixture
def tenant_manager(tmp_path):
    """Create tenant manager with temp paths."""
    storage_path = tmp_path / "tenants.json"
    base_data_path = tmp_path / "data"
    store = TenantStore(storage_path)
    return TenantManager(store, base_data_path)


# ============== TenantStatus Tests ==============

class TestTenantStatus:
    """Test TenantStatus enum."""
    
    def test_status_values(self):
        """Test all status values exist."""
        assert TenantStatus.ACTIVE.value == "active"
        assert TenantStatus.SUSPENDED.value == "suspended"
        assert TenantStatus.PENDING.value == "pending"
        assert TenantStatus.ARCHIVED.value == "archived"
    
    def test_status_from_string(self):
        """Test creating status from string."""
        assert TenantStatus("active") == TenantStatus.ACTIVE
        assert TenantStatus("suspended") == TenantStatus.SUSPENDED


# ============== TenantConfig Tests ==============

class TestTenantConfig:
    """Test TenantConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = TenantConfig()
        assert config.input_dir == "data_input"
        assert config.output_dir == "data_output"
        assert config.default_time_slot == "8H-15H"
        assert config.include_cfs is True
        assert config.auto_export_email is False
        assert config.email_recipients == []
        assert config.max_files_per_batch == 100
        assert config.retention_days == 90
    
    def test_custom_values(self, tenant_config):
        """Test custom configuration values."""
        assert tenant_config.input_dir == "test_input"
        assert tenant_config.email_recipients == ["test@example.com"]
        assert tenant_config.max_files_per_batch == 50
    
    def test_to_dict(self, tenant_config):
        """Test converting config to dictionary."""
        data = tenant_config.to_dict()
        assert isinstance(data, dict)
        assert data["input_dir"] == "test_input"
        assert data["email_recipients"] == ["test@example.com"]
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "input_dir": "custom_input",
            "output_dir": "custom_output",
            "email_enabled": True,
        }
        config = TenantConfig.from_dict(data)
        assert config.input_dir == "custom_input"
        assert config.output_dir == "custom_output"
        assert config.email_enabled is True
        # Default values for missing keys
        assert config.default_time_slot == "8H-15H"
    
    def test_from_dict_empty(self):
        """Test creating config from empty dictionary."""
        config = TenantConfig.from_dict({})
        assert config.input_dir == "data_input"


# ============== Tenant Tests ==============

class TestTenant:
    """Test Tenant dataclass."""
    
    def test_tenant_creation(self, tenant):
        """Test tenant creation with all fields."""
        assert tenant.id == "test-tenant-001"
        assert tenant.name == "Test Tenant"
        assert tenant.code == "TST"
        assert tenant.status == TenantStatus.ACTIVE
        assert tenant.metadata == {"test": True}
    
    def test_tenant_is_active(self, tenant):
        """Test is_active method."""
        assert tenant.is_active() is True
        
        tenant.status = TenantStatus.SUSPENDED
        assert tenant.is_active() is False
    
    def test_tenant_paths(self, tenant):
        """Test tenant-specific paths."""
        base_path = Path("/data")
        
        input_path = tenant.get_input_path(base_path)
        # Use Path comparison for cross-platform compatibility
        assert input_path == base_path / "TST" / "test_input"
        
        output_path = tenant.get_output_path(base_path)
        assert output_path == base_path / "TST" / "test_output"
    
    def test_tenant_to_dict(self, tenant):
        """Test converting tenant to dictionary."""
        data = tenant.to_dict()
        
        assert data["id"] == "test-tenant-001"
        assert data["name"] == "Test Tenant"
        assert data["code"] == "TST"
        assert data["status"] == "active"
        assert "config" in data
        assert isinstance(data["config"], dict)
    
    def test_tenant_from_dict(self):
        """Test creating tenant from dictionary."""
        data = {
            "id": "tenant-123",
            "name": "From Dict Tenant",
            "code": "FDT",
            "status": "pending",
            "config": {"input_dir": "custom"},
            "metadata": {"key": "value"},
        }
        
        tenant = Tenant.from_dict(data)
        assert tenant.id == "tenant-123"
        assert tenant.name == "From Dict Tenant"
        assert tenant.status == TenantStatus.PENDING
        assert tenant.config.input_dir == "custom"


# ============== TenantStore Tests ==============

class TestTenantStore:
    """Test TenantStore class."""
    
    def test_store_creates_default_tenant(self, tenant_store):
        """Test that store creates default tenant."""
        tenants = tenant_store.list_tenants()
        assert len(tenants) >= 1
        
        default = tenant_store.get_default_tenant()
        assert default is not None
        assert default.metadata.get("is_default") is True
    
    def test_create_tenant(self, tenant_store):
        """Test creating a new tenant."""
        tenant = tenant_store.create_tenant(
            name="New Port",
            code="NP1",
            metadata={"region": "South"}
        )
        
        assert tenant.id is not None
        assert tenant.name == "New Port"
        assert tenant.code == "NP1"
        assert tenant.status == TenantStatus.ACTIVE
    
    def test_create_tenant_duplicate_code(self, tenant_store):
        """Test creating tenant with duplicate code fails."""
        tenant_store.create_tenant(name="Port A", code="PA1")
        
        with pytest.raises(ValueError, match="already exists"):
            tenant_store.create_tenant(name="Port B", code="PA1")
    
    def test_get_tenant(self, tenant_store):
        """Test getting tenant by ID."""
        created = tenant_store.create_tenant(name="Port X", code="PX1")
        
        retrieved = tenant_store.get_tenant(created.id)
        assert retrieved is not None
        assert retrieved.name == "Port X"
    
    def test_get_tenant_by_code(self, tenant_store):
        """Test getting tenant by code."""
        tenant_store.create_tenant(name="Port Y", code="PY1")
        
        retrieved = tenant_store.get_tenant_by_code("PY1")
        assert retrieved is not None
        assert retrieved.name == "Port Y"
    
    def test_update_tenant(self, tenant_store):
        """Test updating tenant fields."""
        tenant = tenant_store.create_tenant(name="Original", code="ORG")
        
        updated = tenant_store.update_tenant(
            tenant.id,
            name="Updated Name",
            status="suspended"
        )
        
        assert updated.name == "Updated Name"
        assert updated.status == TenantStatus.SUSPENDED
    
    def test_update_tenant_config(self, tenant_store):
        """Test updating tenant configuration."""
        tenant = tenant_store.create_tenant(name="Config Test", code="CFT")
        
        updated = tenant_store.update_tenant(
            tenant.id,
            config={"max_files_per_batch": 200}
        )
        
        assert updated.config.max_files_per_batch == 200
    
    def test_delete_tenant(self, tenant_store):
        """Test soft deleting a tenant."""
        tenant = tenant_store.create_tenant(name="To Delete", code="DEL")
        
        result = tenant_store.delete_tenant(tenant.id)
        assert result is True
        
        # Should still exist but archived
        deleted = tenant_store.get_tenant(tenant.id)
        assert deleted.status == TenantStatus.ARCHIVED
    
    def test_delete_default_tenant_fails(self, tenant_store):
        """Test that default tenant cannot be deleted."""
        default = tenant_store.get_default_tenant()
        
        with pytest.raises(ValueError, match="Cannot delete default"):
            tenant_store.delete_tenant(default.id)
    
    def test_list_tenants(self, tenant_store):
        """Test listing tenants."""
        tenant_store.create_tenant(name="List A", code="LA1")
        tenant_store.create_tenant(name="List B", code="LB1")
        
        tenants = tenant_store.list_tenants()
        # Default + 2 created
        assert len(tenants) >= 3
    
    def test_list_tenants_exclude_archived(self, tenant_store):
        """Test that archived tenants are excluded by default."""
        tenant = tenant_store.create_tenant(name="Archive Me", code="ARC")
        tenant_store.delete_tenant(tenant.id)
        
        active_tenants = tenant_store.list_tenants(include_archived=False)
        all_tenants = tenant_store.list_tenants(include_archived=True)
        
        assert len(all_tenants) > len(active_tenants)
    
    def test_persistence(self, tmp_path):
        """Test that tenants are persisted to file."""
        storage_path = tmp_path / "persist_test.json"
        
        # Create store and add tenant
        store1 = TenantStore(storage_path)
        store1.create_tenant(name="Persist Test", code="PER")
        
        # Create new store instance
        store2 = TenantStore(storage_path)
        tenant = store2.get_tenant_by_code("PER")
        
        assert tenant is not None
        assert tenant.name == "Persist Test"


# ============== TenantContext Tests ==============

class TestTenantContext:
    """Test TenantContext thread-local storage."""
    
    def test_set_and_get_tenant(self, tenant):
        """Test setting and getting current tenant."""
        TenantContext.set_current_tenant(None)  # Clear first
        
        assert TenantContext.get_current_tenant() is None
        
        TenantContext.set_current_tenant(tenant)
        assert TenantContext.get_current_tenant() == tenant
        
        TenantContext.set_current_tenant(None)
    
    def test_tenant_scope_context_manager(self, tenant):
        """Test tenant scope context manager."""
        TenantContext.set_current_tenant(None)
        
        with TenantContext.tenant_scope(tenant):
            assert TenantContext.get_current_tenant() == tenant
        
        assert TenantContext.get_current_tenant() is None
    
    def test_nested_tenant_scopes(self, tenant):
        """Test nested tenant scopes."""
        tenant2 = Tenant(
            id="tenant-2",
            name="Second Tenant",
            code="SC2"
        )
        
        TenantContext.set_current_tenant(None)
        
        with TenantContext.tenant_scope(tenant):
            assert TenantContext.get_current_tenant().code == "TST"
            
            with TenantContext.tenant_scope(tenant2):
                assert TenantContext.get_current_tenant().code == "SC2"
            
            assert TenantContext.get_current_tenant().code == "TST"
        
        assert TenantContext.get_current_tenant() is None
    
    def test_thread_isolation(self, tenant):
        """Test that tenant context is thread-local."""
        results = {}
        
        def thread_func(t_id, t_tenant):
            TenantContext.set_current_tenant(t_tenant)
            import time
            time.sleep(0.01)  # Small delay
            current = TenantContext.get_current_tenant()
            results[t_id] = current.code if current else None
        
        tenant2 = Tenant(id="t2", name="Thread 2", code="TH2")
        
        t1 = threading.Thread(target=thread_func, args=(1, tenant))
        t2 = threading.Thread(target=thread_func, args=(2, tenant2))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        assert results[1] == "TST"
        assert results[2] == "TH2"


# ============== TenantManager Tests ==============

class TestTenantManager:
    """Test TenantManager class."""
    
    def test_get_tenant(self, tenant_manager):
        """Test getting tenant by ID."""
        tenant = tenant_manager.store.create_tenant(name="Manager Test", code="MGR")
        
        result = tenant_manager.get_tenant(tenant.id)
        assert result is not None
        assert result.name == "Manager Test"
    
    def test_get_tenant_by_code(self, tenant_manager):
        """Test getting tenant by code."""
        tenant_manager.store.create_tenant(name="Code Test", code="CDT")
        
        result = tenant_manager.get_tenant_by_code("CDT")
        assert result is not None
    
    def test_get_current_tenant_default(self, tenant_manager):
        """Test getting current tenant returns default."""
        TenantContext.set_current_tenant(None)
        
        current = tenant_manager.get_current_tenant()
        assert current is not None  # Should return default
    
    def test_create_tenant_with_directories(self, tenant_manager):
        """Test creating tenant sets up directories."""
        tenant = tenant_manager.create_tenant(
            name="Dir Test",
            code="DIR",
            setup_directories=True
        )
        
        input_path = tenant.get_input_path(tenant_manager.base_data_path)
        output_path = tenant.get_output_path(tenant_manager.base_data_path)
        
        assert input_path.exists()
        assert output_path.exists()
    
    def test_get_tenant_paths(self, tenant_manager):
        """Test getting tenant-specific paths."""
        tenant = tenant_manager.store.create_tenant(name="Path Test", code="PTH")
        
        with tenant_manager.tenant_scope(tenant):
            input_path = tenant_manager.get_tenant_input_path()
            output_path = tenant_manager.get_tenant_output_path()
            
            assert "PTH" in str(input_path)
            assert "PTH" in str(output_path)
    
    def test_switch_tenant(self, tenant_manager):
        """Test switching current tenant."""
        tenant = tenant_manager.store.create_tenant(name="Switch Test", code="SWT")
        
        result = tenant_manager.switch_tenant(tenant.id)
        assert result is True
        
        current = TenantContext.get_current_tenant()
        assert current.code == "SWT"
        
        TenantContext.set_current_tenant(None)
    
    def test_switch_to_inactive_tenant_fails(self, tenant_manager):
        """Test switching to inactive tenant fails."""
        tenant = tenant_manager.store.create_tenant(name="Inactive", code="INA")
        tenant_manager.store.update_tenant(tenant.id, status="suspended")
        
        result = tenant_manager.switch_tenant(tenant.id)
        assert result is False
    
    def test_tenant_scope_context(self, tenant_manager):
        """Test tenant scope context manager."""
        tenant = tenant_manager.store.create_tenant(name="Scope Test", code="SCP")
        
        with tenant_manager.tenant_scope(tenant):
            current = TenantContext.get_current_tenant()
            assert current.code == "SCP"
    
    def test_tenant_scope_with_id(self, tenant_manager):
        """Test tenant scope with tenant ID."""
        tenant = tenant_manager.store.create_tenant(name="ID Scope", code="IDS")
        
        with tenant_manager.tenant_scope(tenant.id):
            current = TenantContext.get_current_tenant()
            assert current.code == "IDS"
    
    def test_tenant_scope_invalid_raises(self, tenant_manager):
        """Test tenant scope with invalid ID raises."""
        with pytest.raises(ValueError, match="Tenant not found"):
            with tenant_manager.tenant_scope("invalid-id"):
                pass
    
    def test_list_tenants(self, tenant_manager):
        """Test listing all tenants."""
        tenant_manager.store.create_tenant(name="List 1", code="LS1")
        tenant_manager.store.create_tenant(name="List 2", code="LS2")
        
        tenants = tenant_manager.list_tenants()
        assert len(tenants) >= 2


# ============== require_tenant Decorator Tests ==============

class TestRequireTenantDecorator:
    """Test require_tenant decorator."""
    
    def test_decorator_with_tenant(self, tenant):
        """Test decorator allows execution with tenant."""
        @require_tenant
        def protected_func():
            return "success"
        
        with TenantContext.tenant_scope(tenant):
            result = protected_func()
            assert result == "success"
    
    def test_decorator_without_tenant(self):
        """Test decorator raises without tenant."""
        @require_tenant
        def protected_func():
            return "success"
        
        TenantContext.set_current_tenant(None)
        
        with pytest.raises(ValueError, match="No tenant context"):
            protected_func()
    
    def test_decorator_with_inactive_tenant(self, tenant):
        """Test decorator raises with inactive tenant."""
        @require_tenant
        def protected_func():
            return "success"
        
        tenant.status = TenantStatus.SUSPENDED
        
        with TenantContext.tenant_scope(tenant):
            with pytest.raises(ValueError, match="not active"):
                protected_func()
    
    def test_decorator_preserves_function_info(self):
        """Test decorator preserves function name and docstring."""
        @require_tenant
        def my_function():
            """My docstring."""
            pass
        
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


# ============== Global Functions Tests ==============

class TestGlobalFunctions:
    """Test global tenant functions."""
    
    def test_get_tenant_manager(self):
        """Test getting global tenant manager."""
        manager = get_tenant_manager()
        assert manager is not None
        assert isinstance(manager, TenantManager)
    
    def test_init_tenant_manager(self, tmp_path):
        """Test initializing tenant manager with custom paths."""
        storage_path = tmp_path / "custom_tenants.json"
        base_path = tmp_path / "custom_data"
        
        manager = init_tenant_manager(storage_path, base_path)
        assert manager.base_data_path == base_path


# ============== Integration Tests ==============

class TestTenantIntegration:
    """Integration tests for multi-tenant functionality."""
    
    def test_full_tenant_lifecycle(self, tenant_manager):
        """Test complete tenant lifecycle."""
        # Create tenant
        tenant = tenant_manager.create_tenant(
            name="Full Lifecycle Test",
            code="FLC",
            config=TenantConfig(email_enabled=True)
        )
        
        # Verify creation
        assert tenant.is_active()
        
        # Switch to tenant
        tenant_manager.switch_tenant(tenant.id)
        assert TenantContext.get_current_tenant().code == "FLC"
        
        # Update tenant
        tenant_manager.store.update_tenant(
            tenant.id,
            name="Updated Lifecycle Test"
        )
        
        # Verify update
        updated = tenant_manager.get_tenant(tenant.id)
        assert updated.name == "Updated Lifecycle Test"
        
        # Suspend tenant
        tenant_manager.store.update_tenant(tenant.id, status="suspended")
        
        # Verify can't switch to suspended
        TenantContext.set_current_tenant(None)
        result = tenant_manager.switch_tenant(tenant.id)
        assert result is False
        
        # Cleanup
        TenantContext.set_current_tenant(None)
    
    def test_multi_tenant_data_isolation(self, tenant_manager):
        """Test that tenant data is isolated."""
        tenant1 = tenant_manager.create_tenant(
            name="Tenant One",
            code="T01",
            setup_directories=True
        )
        
        tenant2 = tenant_manager.create_tenant(
            name="Tenant Two",
            code="T02",
            setup_directories=True
        )
        
        # Get paths for each tenant
        with tenant_manager.tenant_scope(tenant1):
            path1 = tenant_manager.get_tenant_input_path()
        
        with tenant_manager.tenant_scope(tenant2):
            path2 = tenant_manager.get_tenant_input_path()
        
        # Verify paths are different
        assert path1 != path2
        assert "T01" in str(path1)
        assert "T02" in str(path2)
    
    def test_concurrent_tenant_operations(self, tenant_manager):
        """Test concurrent operations on different tenants."""
        tenant1 = tenant_manager.store.create_tenant(name="Concurrent 1", code="CC1")
        tenant2 = tenant_manager.store.create_tenant(name="Concurrent 2", code="CC2")
        
        results = {}
        errors = []
        
        def process_tenant(t_num, tenant):
            try:
                with tenant_manager.tenant_scope(tenant):
                    current = TenantContext.get_current_tenant()
                    # Simulate work
                    import time
                    time.sleep(0.01)
                    results[t_num] = current.code
            except Exception as e:
                errors.append(str(e))
        
        threads = [
            threading.Thread(target=process_tenant, args=(1, tenant1)),
            threading.Thread(target=process_tenant, args=(2, tenant2)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert results[1] == "CC1"
        assert results[2] == "CC2"
