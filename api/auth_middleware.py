# File: api/auth_middleware.py
"""
Authentication Middleware for FastAPI.

V5.4 - Phase 3: Enterprise Ready
Provides:
- JWT token validation
- Role-based access control
- API key authentication
- Rate limiting
"""

import logging
from datetime import datetime
from typing import Optional, Callable, List
from functools import wraps

try:
    from fastapi import Request, HTTPException, Depends, status
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logging.warning("FastAPI not installed")

from utils.auth import (
    AuthManager, User, Permission, Role,
    get_auth_manager, TokenManager
)


if FASTAPI_AVAILABLE:
    
    # Security schemes
    bearer_scheme = HTTPBearer(auto_error=False)
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
    
    
    class AuthenticationError(HTTPException):
        """Authentication failed."""
        def __init__(self, detail: str = "Authentication required"):
            super().__init__(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail,
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    
    class AuthorizationError(HTTPException):
        """Authorization failed (insufficient permissions)."""
        def __init__(self, detail: str = "Insufficient permissions"):
            super().__init__(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail
            )
    
    
    async def get_current_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        api_key: Optional[str] = Depends(api_key_header)
    ) -> User:
        """
        Get current authenticated user from JWT token or API key.
        
        Raises:
            AuthenticationError: If authentication fails
        """
        auth_manager = get_auth_manager()
        
        # Try JWT token first
        if credentials:
            token = credentials.credentials
            user = auth_manager.verify_access_token(token)
            if user:
                return user
        
        # Try API key
        if api_key:
            # API keys are in format: user_id.secret
            # For simplicity, we use username as API key
            user = auth_manager.user_store.get_user_by_username(api_key)
            if user and user.is_active and user.role == Role.API:
                return user
        
        raise AuthenticationError("Invalid or expired token")
    
    
    async def get_current_user_optional(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        api_key: Optional[str] = Depends(api_key_header)
    ) -> Optional[User]:
        """
        Get current user if authenticated, None otherwise.
        Does not raise exception if not authenticated.
        """
        try:
            return await get_current_user(credentials, api_key)
        except AuthenticationError:
            return None
    
    
    async def get_admin_user(
        user: User = Depends(get_current_user)
    ) -> User:
        """Get current user and verify admin role."""
        if user.role != Role.ADMIN:
            raise AuthorizationError("Admin access required")
        return user
    
    
    def require_permission(permission: Permission):
        """
        Dependency that checks if user has specific permission.
        
        Usage:
            @app.get("/reports")
            async def get_reports(user: User = Depends(require_permission(Permission.VIEW_REPORTS))):
                ...
        """
        async def permission_checker(
            user: User = Depends(get_current_user)
        ) -> User:
            if not user.has_permission(permission):
                raise AuthorizationError(
                    f"Permission denied: {permission.value}"
                )
            return user
        return permission_checker
    
    
    def require_roles(*roles: Role):
        """
        Dependency that checks if user has one of the specified roles.
        
        Usage:
            @app.delete("/users/{user_id}")
            async def delete_user(user: User = Depends(require_roles(Role.ADMIN))):
                ...
        """
        async def role_checker(
            user: User = Depends(get_current_user)
        ) -> User:
            if user.role not in roles:
                raise AuthorizationError(
                    f"Required role: {', '.join(r.value for r in roles)}"
                )
            return user
        return role_checker
    
    
    # Rate limiting (simple in-memory implementation)
    class RateLimiter:
        """Simple rate limiter."""
        
        def __init__(self, requests_per_minute: int = 60):
            self.requests_per_minute = requests_per_minute
            self._requests: dict = {}  # ip -> list of timestamps
        
        def _clean_old_requests(self, ip: str):
            """Remove requests older than 1 minute."""
            now = datetime.now()
            if ip in self._requests:
                self._requests[ip] = [
                    t for t in self._requests[ip]
                    if (now - t).total_seconds() < 60
                ]
        
        def is_rate_limited(self, ip: str) -> bool:
            """Check if IP is rate limited."""
            self._clean_old_requests(ip)
            
            if ip not in self._requests:
                self._requests[ip] = []
            
            if len(self._requests[ip]) >= self.requests_per_minute:
                return True
            
            self._requests[ip].append(datetime.now())
            return False
        
        def get_remaining(self, ip: str) -> int:
            """Get remaining requests for IP."""
            self._clean_old_requests(ip)
            current = len(self._requests.get(ip, []))
            return max(0, self.requests_per_minute - current)
    
    
    # Global rate limiter
    rate_limiter = RateLimiter(requests_per_minute=100)
    
    
    async def check_rate_limit(request: Request):
        """
        Dependency to check rate limit.
        
        Raises HTTPException 429 if rate limited.
        """
        client_ip = request.client.host if request.client else "unknown"
        
        if rate_limiter.is_rate_limited(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(rate_limiter.requests_per_minute),
                    "X-RateLimit-Remaining": "0"
                }
            )
        
        return True
    
    
    # Auth routes to add to API
    from fastapi import APIRouter
    from pydantic import BaseModel
    
    auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
    
    
    class LoginRequest(BaseModel):
        """Login request model."""
        username: str
        password: str
    
    
    class TokenResponse(BaseModel):
        """Token response model."""
        access_token: str
        refresh_token: str
        token_type: str = "bearer"
        expires_in: int
        user: dict
    
    
    class RefreshRequest(BaseModel):
        """Refresh token request."""
        refresh_token: str
    
    
    class UserCreate(BaseModel):
        """User creation model."""
        username: str
        email: str
        password: str
        role: str = "viewer"
    
    
    class UserResponse(BaseModel):
        """User response model."""
        id: str
        username: str
        email: str
        role: str
        is_active: bool
        created_at: str
        last_login: Optional[str]
    
    
    @auth_router.post("/login", response_model=TokenResponse)
    async def login(request: LoginRequest):
        """
        Login with username and password.
        
        Returns JWT access token and refresh token.
        """
        auth_manager = get_auth_manager()
        result = auth_manager.login(request.username, request.password)
        
        if not result:
            raise AuthenticationError("Invalid username or password")
        
        return TokenResponse(**result)
    
    
    @auth_router.post("/refresh", response_model=dict)
    async def refresh_token(request: RefreshRequest):
        """
        Get new access token using refresh token.
        """
        auth_manager = get_auth_manager()
        result = auth_manager.refresh_access_token(request.refresh_token)
        
        if not result:
            raise AuthenticationError("Invalid or expired refresh token")
        
        return result
    
    
    @auth_router.post("/logout")
    async def logout(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ):
        """
        Logout and invalidate token.
        """
        if credentials:
            auth_manager = get_auth_manager()
            auth_manager.logout(credentials.credentials)
        
        return {"message": "Logged out successfully"}
    
    
    @auth_router.get("/me", response_model=UserResponse)
    async def get_current_user_info(
        user: User = Depends(get_current_user)
    ):
        """
        Get current user information.
        """
        return UserResponse(**user.to_dict())
    
    
    @auth_router.get("/users", response_model=List[UserResponse])
    async def list_users(
        user: User = Depends(get_admin_user)
    ):
        """
        List all users (admin only).
        """
        auth_manager = get_auth_manager()
        users = auth_manager.user_store.list_users()
        return [UserResponse(**u.to_dict()) for u in users]
    
    
    @auth_router.post("/users", response_model=UserResponse)
    async def create_user(
        request: UserCreate,
        user: User = Depends(get_admin_user)
    ):
        """
        Create new user (admin only).
        """
        auth_manager = get_auth_manager()
        
        try:
            new_user = auth_manager.user_store.create_user(
                username=request.username,
                email=request.email,
                password=request.password,
                role=Role(request.role)
            )
            return UserResponse(**new_user.to_dict())
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    
    
    @auth_router.delete("/users/{user_id}")
    async def delete_user(
        user_id: str,
        user: User = Depends(get_admin_user)
    ):
        """
        Delete user (admin only).
        """
        if user.id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself"
            )
        
        auth_manager = get_auth_manager()
        if auth_manager.user_store.delete_user(user_id):
            return {"message": "User deleted"}
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


else:
    # Stub implementations when FastAPI not available
    def get_current_user():
        raise NotImplementedError("FastAPI not installed")
    
    def get_admin_user():
        raise NotImplementedError("FastAPI not installed")
    
    def require_permission(permission):
        def decorator(func):
            return func
        return decorator
    
    def require_roles(*roles):
        def decorator(func):
            return func
        return decorator
    
    auth_router = None
