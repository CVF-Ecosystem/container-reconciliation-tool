# File: tests/test_auth.py
"""
Tests for utils/auth.py authentication module.

V5.4 - Phase 3: Enterprise Ready
Tests cover:
- Password hashing (bcrypt/SHA256)
- User management (CRUD)
- JWT token generation and validation
- Role-based access control
- Permission checking
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import json

from utils.auth import (
    Role, Permission, ROLE_PERMISSIONS,
    User, TokenData,
    PasswordHasher, TokenManager, UserStore, AuthManager,
    require_auth, get_auth_manager, init_auth
)


# =============================================================================
# Role & Permission Tests
# =============================================================================

class TestRolePermissions:
    """Tests for Role and Permission enums."""
    
    def test_role_values(self):
        """Test all roles have correct values."""
        assert Role.ADMIN.value == "admin"
        assert Role.OPERATOR.value == "operator"
        assert Role.VIEWER.value == "viewer"
        assert Role.API.value == "api"
    
    def test_permission_values(self):
        """Test key permissions exist."""
        assert Permission.VIEW_REPORTS.value == "view_reports"
        assert Permission.RUN_RECONCILIATION.value == "run_reconciliation"
        assert Permission.MANAGE_USERS.value == "manage_users"
    
    def test_admin_has_all_permissions(self):
        """Test admin role has all permissions."""
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert len(admin_perms) == len(Permission)
        for perm in Permission:
            assert perm in admin_perms
    
    def test_viewer_limited_permissions(self):
        """Test viewer has limited permissions."""
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.VIEW_REPORTS in viewer_perms
        assert Permission.VIEW_DASHBOARD in viewer_perms
        assert Permission.MANAGE_USERS not in viewer_perms
        assert Permission.RUN_RECONCILIATION not in viewer_perms
    
    def test_operator_permissions(self):
        """Test operator has operational permissions."""
        op_perms = ROLE_PERMISSIONS[Role.OPERATOR]
        assert Permission.RUN_RECONCILIATION in op_perms
        assert Permission.EXPORT_DATA in op_perms
        assert Permission.MANAGE_USERS not in op_perms


# =============================================================================
# User Model Tests
# =============================================================================

class TestUser:
    """Tests for User dataclass."""
    
    def test_create_user(self):
        """Test user creation."""
        user = User(
            id="test123",
            username="testuser",
            email="test@test.com",
            password_hash="hashed",
            role=Role.VIEWER
        )
        
        assert user.id == "test123"
        assert user.username == "testuser"
        assert user.email == "test@test.com"
        assert user.role == Role.VIEWER
        assert user.is_active is True
    
    def test_user_has_permission(self):
        """Test user permission checking."""
        user = User(
            id="1", username="viewer", email="v@test.com",
            password_hash="h", role=Role.VIEWER
        )
        
        assert user.has_permission(Permission.VIEW_REPORTS) is True
        assert user.has_permission(Permission.MANAGE_USERS) is False
    
    def test_admin_has_all_permissions(self):
        """Test admin user has all permissions."""
        admin = User(
            id="1", username="admin", email="a@test.com",
            password_hash="h", role=Role.ADMIN
        )
        
        for perm in Permission:
            assert admin.has_permission(perm) is True
    
    def test_user_get_permissions(self):
        """Test getting all user permissions."""
        operator = User(
            id="1", username="op", email="o@test.com",
            password_hash="h", role=Role.OPERATOR
        )
        
        perms = operator.get_permissions()
        assert Permission.RUN_RECONCILIATION in perms
        assert Permission.MANAGE_USERS not in perms
    
    def test_user_to_dict(self):
        """Test user serialization to dict."""
        user = User(
            id="test123",
            username="testuser",
            email="test@test.com",
            password_hash="secret",
            role=Role.VIEWER
        )
        
        data = user.to_dict()
        
        assert data["id"] == "test123"
        assert data["username"] == "testuser"
        assert data["role"] == "viewer"
        assert "password_hash" not in data  # Should not include password


# =============================================================================
# PasswordHasher Tests
# =============================================================================

class TestPasswordHasher:
    """Tests for password hashing."""
    
    def test_hash_password(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = PasswordHasher.hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 20
    
    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        hash1 = PasswordHasher.hash_password("password1")
        hash2 = PasswordHasher.hash_password("password2")
        
        assert hash1 != hash2
    
    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "samepassword"
        hash1 = PasswordHasher.hash_password(password)
        hash2 = PasswordHasher.hash_password(password)
        
        # Different hashes due to random salt
        assert hash1 != hash2
    
    def test_verify_correct_password(self):
        """Test verifying correct password."""
        password = "correctpassword"
        hashed = PasswordHasher.hash_password(password)
        
        assert PasswordHasher.verify_password(password, hashed) is True
    
    def test_verify_wrong_password(self):
        """Test verifying wrong password."""
        hashed = PasswordHasher.hash_password("correctpassword")
        
        assert PasswordHasher.verify_password("wrongpassword", hashed) is False
    
    def test_verify_empty_password(self):
        """Test verifying empty password."""
        hashed = PasswordHasher.hash_password("realpassword")
        
        assert PasswordHasher.verify_password("", hashed) is False
    
    def test_verify_invalid_hash_format(self):
        """Test verifying with invalid hash format."""
        result = PasswordHasher.verify_password("password", "invalidhash")
        assert result is False


# =============================================================================
# TokenManager Tests
# =============================================================================

class TestTokenManager:
    """Tests for JWT token management."""
    
    @pytest.fixture
    def token_manager(self):
        """Create token manager for tests."""
        return TokenManager(
            secret_key="test-secret-key",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7
        )
    
    @pytest.fixture
    def test_user(self):
        """Create test user."""
        return User(
            id="user123",
            username="testuser",
            email="test@test.com",
            password_hash="hashed",
            role=Role.OPERATOR
        )
    
    def test_create_access_token(self, token_manager, test_user):
        """Test creating access token."""
        token = token_manager.create_access_token(test_user)
        
        assert token is not None
        assert len(token) > 20
    
    def test_create_refresh_token(self, token_manager, test_user):
        """Test creating refresh token."""
        token = token_manager.create_refresh_token(test_user)
        
        assert token is not None
        assert len(token) > 20
    
    def test_verify_valid_token(self, token_manager, test_user):
        """Test verifying valid token."""
        token = token_manager.create_access_token(test_user)
        payload = token_manager.verify_token(token)
        
        assert payload is not None
        # Check payload contents (if JWT is available)
        if "sub" in payload:
            assert payload["sub"] == test_user.id
    
    def test_verify_revoked_token(self, token_manager, test_user):
        """Test verifying revoked token."""
        token = token_manager.create_access_token(test_user)
        token_manager.revoke_token(token)
        
        payload = token_manager.verify_token(token)
        assert payload is None
    
    def test_token_revocation(self, token_manager, test_user):
        """Test token revocation flow."""
        token = token_manager.create_access_token(test_user)
        
        assert token_manager.is_token_revoked(token) is False
        
        token_manager.revoke_token(token)
        
        assert token_manager.is_token_revoked(token) is True


# =============================================================================
# UserStore Tests
# =============================================================================

class TestUserStore:
    """Tests for user storage."""
    
    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create temporary storage path."""
        return tmp_path / "users.json"
    
    @pytest.fixture
    def user_store(self, temp_storage):
        """Create user store with temp storage."""
        return UserStore(storage_path=temp_storage)
    
    def test_create_user(self, user_store):
        """Test creating a new user."""
        user = user_store.create_user(
            username="newuser",
            email="new@test.com",
            password="password123",
            role=Role.VIEWER
        )
        
        assert user.username == "newuser"
        assert user.email == "new@test.com"
        assert user.role == Role.VIEWER
    
    def test_create_duplicate_username(self, user_store):
        """Test creating user with duplicate username."""
        user_store.create_user(
            username="duplicate",
            email="first@test.com",
            password="pass"
        )
        
        with pytest.raises(ValueError, match="already exists"):
            user_store.create_user(
                username="duplicate",
                email="second@test.com",
                password="pass"
            )
    
    def test_create_duplicate_email(self, user_store):
        """Test creating user with duplicate email."""
        user_store.create_user(
            username="user1",
            email="same@test.com",
            password="pass"
        )
        
        with pytest.raises(ValueError, match="already exists"):
            user_store.create_user(
                username="user2",
                email="same@test.com",
                password="pass"
            )
    
    def test_get_user_by_id(self, user_store):
        """Test retrieving user by ID."""
        created = user_store.create_user(
            username="testuser",
            email="test@test.com",
            password="pass"
        )
        
        found = user_store.get_user_by_id(created.id)
        
        assert found is not None
        assert found.username == "testuser"
    
    def test_get_user_by_username(self, user_store):
        """Test retrieving user by username."""
        user_store.create_user(
            username="findme",
            email="find@test.com",
            password="pass"
        )
        
        found = user_store.get_user_by_username("findme")
        
        assert found is not None
        assert found.email == "find@test.com"
    
    def test_get_nonexistent_user(self, user_store):
        """Test retrieving non-existent user."""
        found = user_store.get_user_by_username("doesnotexist")
        assert found is None
    
    def test_authenticate_valid_credentials(self, user_store):
        """Test authentication with valid credentials."""
        user_store.create_user(
            username="authuser",
            email="auth@test.com",
            password="correctpassword"
        )
        
        authenticated = user_store.authenticate("authuser", "correctpassword")
        
        assert authenticated is not None
        assert authenticated.username == "authuser"
    
    def test_authenticate_invalid_password(self, user_store):
        """Test authentication with invalid password."""
        user_store.create_user(
            username="authuser",
            email="auth@test.com",
            password="correctpassword"
        )
        
        authenticated = user_store.authenticate("authuser", "wrongpassword")
        assert authenticated is None
    
    def test_authenticate_inactive_user(self, user_store):
        """Test authentication with inactive user."""
        user = user_store.create_user(
            username="inactive",
            email="inactive@test.com",
            password="password"
        )
        user_store.update_user(user.id, is_active=False)
        
        authenticated = user_store.authenticate("inactive", "password")
        assert authenticated is None
    
    def test_delete_user(self, user_store):
        """Test deleting user."""
        user = user_store.create_user(
            username="deleteme",
            email="delete@test.com",
            password="pass"
        )
        
        result = user_store.delete_user(user.id)
        assert result is True
        
        found = user_store.get_user_by_id(user.id)
        assert found is None
    
    def test_list_users(self, user_store):
        """Test listing all users."""
        user_store.create_user(username="user1", email="u1@test.com", password="p")
        user_store.create_user(username="user2", email="u2@test.com", password="p")
        
        users = user_store.list_users()
        
        assert len(users) == 2
    
    def test_persistence(self, temp_storage):
        """Test that users persist across store instances."""
        # Create store and add user
        store1 = UserStore(storage_path=temp_storage)
        store1.create_user(
            username="persistent",
            email="persist@test.com",
            password="password"
        )
        
        # Create new store instance
        store2 = UserStore(storage_path=temp_storage)
        
        found = store2.get_user_by_username("persistent")
        assert found is not None


# =============================================================================
# AuthManager Tests
# =============================================================================

class TestAuthManager:
    """Tests for main authentication manager."""
    
    @pytest.fixture
    def auth_manager(self, tmp_path):
        """Create auth manager with temp storage."""
        storage_path = tmp_path / "users.json"
        user_store = UserStore(storage_path=storage_path)
        return AuthManager(
            secret_key="test-secret",
            user_store=user_store,
            access_token_expire_minutes=30
        )
    
    def test_default_admin_created(self, auth_manager):
        """Test that default admin is created."""
        admin = auth_manager.user_store.get_user_by_username("admin")
        assert admin is not None
        assert admin.role == Role.ADMIN
    
    def test_login_success(self, auth_manager):
        """Test successful login."""
        result = auth_manager.login("admin", "admin123")
        
        assert result is not None
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
    
    def test_login_failure(self, auth_manager):
        """Test failed login."""
        result = auth_manager.login("admin", "wrongpassword")
        assert result is None
    
    def test_login_nonexistent_user(self, auth_manager):
        """Test login with non-existent user."""
        result = auth_manager.login("nouser", "anypassword")
        assert result is None
    
    def test_verify_access_token(self, auth_manager):
        """Test verifying access token."""
        tokens = auth_manager.login("admin", "admin123")
        
        user = auth_manager.verify_access_token(tokens["access_token"])
        
        assert user is not None
        assert user.username == "admin"
    
    def test_logout(self, auth_manager):
        """Test logout revokes token."""
        tokens = auth_manager.login("admin", "admin123")
        token = tokens["access_token"]
        
        # Verify token works before logout
        user = auth_manager.verify_access_token(token)
        assert user is not None
        
        # Logout
        auth_manager.logout(token)
        
        # Verify token no longer works
        user = auth_manager.verify_access_token(token)
        assert user is None
    
    def test_refresh_token(self, auth_manager):
        """Test refreshing access token."""
        tokens = auth_manager.login("admin", "admin123")
        
        new_tokens = auth_manager.refresh_access_token(tokens["refresh_token"])
        
        assert new_tokens is not None
        assert "access_token" in new_tokens
    
    def test_check_permission(self, auth_manager):
        """Test permission checking."""
        tokens = auth_manager.login("admin", "admin123")
        user = auth_manager.verify_access_token(tokens["access_token"])
        
        assert auth_manager.check_permission(user, Permission.MANAGE_USERS) is True
    
    def test_require_permission_success(self, auth_manager):
        """Test require_permission succeeds for allowed permission."""
        tokens = auth_manager.login("admin", "admin123")
        user = auth_manager.verify_access_token(tokens["access_token"])
        
        # Should not raise
        auth_manager.require_permission(user, Permission.MANAGE_USERS)
    
    def test_require_permission_failure(self, auth_manager):
        """Test require_permission fails for denied permission."""
        # Create viewer user
        auth_manager.user_store.create_user(
            username="viewer",
            email="viewer@test.com",
            password="viewerpass",
            role=Role.VIEWER
        )
        
        tokens = auth_manager.login("viewer", "viewerpass")
        user = auth_manager.verify_access_token(tokens["access_token"])
        
        with pytest.raises(PermissionError):
            auth_manager.require_permission(user, Permission.MANAGE_USERS)


# =============================================================================
# Decorator Tests
# =============================================================================

class TestAuthDecorators:
    """Tests for authentication decorators."""
    
    def test_require_auth_success(self):
        """Test require_auth decorator with valid user."""
        user = User(
            id="1", username="op", email="o@test.com",
            password_hash="h", role=Role.OPERATOR
        )
        
        @require_auth(Permission.VIEW_REPORTS)
        def protected_function(user):
            return "success"
        
        result = protected_function(user)
        assert result == "success"
    
    def test_require_auth_missing_permission(self):
        """Test require_auth decorator with missing permission."""
        user = User(
            id="1", username="viewer", email="v@test.com",
            password_hash="h", role=Role.VIEWER
        )
        
        @require_auth(Permission.MANAGE_USERS)
        def admin_function(user):
            return "success"
        
        with pytest.raises(PermissionError, match="Permission denied"):
            admin_function(user)
    
    def test_require_auth_inactive_user(self):
        """Test require_auth decorator with inactive user."""
        user = User(
            id="1", username="inactive", email="i@test.com",
            password_hash="h", role=Role.ADMIN, is_active=False
        )
        
        @require_auth(Permission.VIEW_REPORTS)
        def protected_function(user):
            return "success"
        
        with pytest.raises(PermissionError, match="inactive"):
            protected_function(user)


# =============================================================================
# Integration Tests
# =============================================================================

class TestAuthIntegration:
    """Integration tests for auth system."""
    
    def test_full_authentication_flow(self, tmp_path):
        """Test complete authentication workflow."""
        # Initialize auth
        auth = init_auth(
            secret_key="integration-test-secret",
            user_storage_path=tmp_path / "users.json"
        )
        
        # Create new user
        auth.user_store.create_user(
            username="newuser",
            email="new@test.com",
            password="newpassword",
            role=Role.OPERATOR
        )
        
        # Login
        tokens = auth.login("newuser", "newpassword")
        assert tokens is not None
        
        # Access protected resource
        user = auth.verify_access_token(tokens["access_token"])
        assert user is not None
        assert auth.check_permission(user, Permission.RUN_RECONCILIATION)
        
        # Refresh token
        new_tokens = auth.refresh_access_token(tokens["refresh_token"])
        assert new_tokens is not None
        
        # Logout
        auth.logout(tokens["access_token"])
        
        # Old token should be invalid
        user = auth.verify_access_token(tokens["access_token"])
        assert user is None
