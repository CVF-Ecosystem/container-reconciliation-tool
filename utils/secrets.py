# File: utils/secrets.py — @2026 v1.0
"""
Secrets Management Module.

Provides a unified interface for accessing secrets from multiple backends:
1. Environment variables (default, always available)
2. HashiCorp Vault (production)
3. AWS Secrets Manager (cloud)
4. Azure Key Vault (cloud)

Usage:
    secrets = SecretsManager()
    email_password = secrets.get("email_password")
    db_password = secrets.get("database_password")
"""

import os
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod


# ============ BACKEND INTERFACE ============

class SecretsBackend(ABC):
    """Abstract interface for secrets backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Get a secret value by key."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available."""
        pass


# ============ ENVIRONMENT VARIABLES BACKEND ============

class EnvSecretsBackend(SecretsBackend):
    """
    Environment variables backend (always available).
    
    Maps logical secret names to environment variable names.
    """
    
    # Mapping: logical name → env var name
    ENV_MAPPING = {
        "email_password": "APP_EMAIL_PASSWORD",
        "email_user": "APP_EMAIL_USER",
        "database_url": "DATABASE_URL",
        "jwt_secret": "JWT_SECRET_KEY",
        "admin_password": "ADMIN_DEFAULT_PASSWORD",
        "celery_broker": "CELERY_BROKER_URL",
        "allowed_origins": "ALLOWED_ORIGINS",
    }
    
    def get(self, key: str) -> Optional[str]:
        """Get secret from environment variable."""
        env_var = self.ENV_MAPPING.get(key, key.upper())
        value = os.getenv(env_var)
        if value:
            logging.debug(f"Secret '{key}' loaded from env var '{env_var}'")
        return value
    
    def is_available(self) -> bool:
        return True


# ============ HASHICORP VAULT BACKEND ============

class VaultSecretsBackend(SecretsBackend):
    """
    HashiCorp Vault backend.
    
    Requires: pip install hvac
    Environment variables:
        VAULT_ADDR: Vault server URL (e.g., http://vault:8200)
        VAULT_TOKEN: Vault authentication token
        VAULT_SECRET_PATH: Base path for secrets (default: secret/app)
    """
    
    def __init__(self):
        self._client = None
        self._secret_path = os.getenv("VAULT_SECRET_PATH", "secret/app")
        self._cache: Dict[str, str] = {}
    
    def _get_client(self):
        """Lazy initialization of Vault client."""
        if self._client is None:
            try:
                import hvac
                vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
                vault_token = os.getenv("VAULT_TOKEN")
                
                self._client = hvac.Client(url=vault_addr, token=vault_token)
                
                if not self._client.is_authenticated():
                    logging.warning("Vault client not authenticated")
                    self._client = None
            except ImportError:
                logging.debug("hvac not installed, Vault backend unavailable")
            except Exception as e:
                logging.warning(f"Could not connect to Vault: {e}")
        
        return self._client
    
    def get(self, key: str) -> Optional[str]:
        """Get secret from Vault."""
        if key in self._cache:
            return self._cache[key]
        
        client = self._get_client()
        if not client:
            return None
        
        try:
            secret = client.secrets.kv.read_secret_version(
                path=f"{self._secret_path}/{key}"
            )
            value = secret["data"]["data"].get("value")
            if value:
                self._cache[key] = value
                logging.debug(f"Secret '{key}' loaded from Vault")
            return value
        except Exception as e:
            logging.debug(f"Could not read secret '{key}' from Vault: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Vault is available and authenticated."""
        return self._get_client() is not None


# ============ AWS SECRETS MANAGER BACKEND ============

class AWSSecretsBackend(SecretsBackend):
    """
    AWS Secrets Manager backend.
    
    Requires: pip install boto3
    Environment variables:
        AWS_REGION: AWS region (default: us-east-1)
        AWS_SECRET_PREFIX: Prefix for secret names (default: app/)
    """
    
    def __init__(self):
        self._client = None
        self._prefix = os.getenv("AWS_SECRET_PREFIX", "app/")
        self._cache: Dict[str, str] = {}
    
    def _get_client(self):
        """Lazy initialization of AWS client."""
        if self._client is None:
            try:
                import boto3
                region = os.getenv("AWS_REGION", "us-east-1")
                self._client = boto3.client("secretsmanager", region_name=region)
            except ImportError:
                logging.debug("boto3 not installed, AWS Secrets Manager unavailable")
            except Exception as e:
                logging.warning(f"Could not create AWS Secrets Manager client: {e}")
        
        return self._client
    
    def get(self, key: str) -> Optional[str]:
        """Get secret from AWS Secrets Manager."""
        if key in self._cache:
            return self._cache[key]
        
        client = self._get_client()
        if not client:
            return None
        
        try:
            import json
            secret_name = f"{self._prefix}{key}"
            response = client.get_secret_value(SecretId=secret_name)
            
            # Secrets can be string or JSON
            secret_string = response.get("SecretString", "")
            try:
                secret_dict = json.loads(secret_string)
                value = secret_dict.get("value", secret_string)
            except json.JSONDecodeError:
                value = secret_string
            
            if value:
                self._cache[key] = value
                logging.debug(f"Secret '{key}' loaded from AWS Secrets Manager")
            return value
        except Exception as e:
            logging.debug(f"Could not read secret '{key}' from AWS: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if AWS Secrets Manager is available."""
        return self._get_client() is not None


# ============ SECRETS MANAGER ============

class SecretsManager:
    """
    Unified secrets manager with fallback chain.
    
    Tries backends in order:
    1. Vault (if VAULT_ADDR is set)
    2. AWS Secrets Manager (if AWS credentials are available)
    3. Environment variables (always available)
    
    Usage:
        secrets = SecretsManager()
        password = secrets.get("email_password")
        
        # With default value
        db_url = secrets.get("database_url", "sqlite:///./data/app.db")
    """
    
    _instance = None
    
    def __init__(self):
        self._backends: list = []
        self._setup_backends()
    
    @classmethod
    def get_instance(cls) -> "SecretsManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _setup_backends(self):
        """Setup backends in priority order."""
        # Vault (highest priority if configured)
        if os.getenv("VAULT_ADDR"):
            vault = VaultSecretsBackend()
            if vault.is_available():
                self._backends.append(vault)
                logging.info("Vault secrets backend enabled")
        
        # AWS Secrets Manager
        if os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"):
            aws = AWSSecretsBackend()
            if aws.is_available():
                self._backends.append(aws)
                logging.info("AWS Secrets Manager backend enabled")
        
        # Environment variables (always last, always available)
        self._backends.append(EnvSecretsBackend())
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value, trying backends in order.
        
        Args:
            key: Logical secret name
            default: Default value if not found in any backend
        
        Returns:
            Secret value or default
        """
        for backend in self._backends:
            value = backend.get(key)
            if value is not None:
                return value
        
        if default is not None:
            logging.debug(f"Secret '{key}' not found, using default")
        
        return default
    
    def require(self, key: str) -> str:
        """
        Get a required secret. Raises ValueError if not found.
        
        Args:
            key: Logical secret name
        
        Returns:
            Secret value
        
        Raises:
            ValueError: If secret is not found in any backend
        """
        value = self.get(key)
        if value is None:
            raise ValueError(
                f"Required secret '{key}' not found. "
                f"Set environment variable '{EnvSecretsBackend.ENV_MAPPING.get(key, key.upper())}' "
                f"or configure a secrets backend."
            )
        return value
    
    def get_all_available(self) -> Dict[str, bool]:
        """Check which secrets are available (without revealing values)."""
        keys = list(EnvSecretsBackend.ENV_MAPPING.keys())
        return {key: self.get(key) is not None for key in keys}


# Global instance
_secrets: Optional[SecretsManager] = None


def get_secrets() -> SecretsManager:
    """Get global secrets manager instance."""
    global _secrets
    if _secrets is None:
        _secrets = SecretsManager()
    return _secrets
