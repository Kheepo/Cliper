"""Secrets management for secure handling of sensitive configuration data.

Provides encryption, decryption, and secure storage of secrets with:
- File-based secret storage with encryption
- Environment variable fallback
- Secret rotation capabilities
- Audit logging for secret access
- Integration with external secret managers
"""

import os
import json
import base64
import secrets
from typing import Optional, Dict, Any, Union
from pathlib import Path
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class SecretNotFoundError(Exception):
    """Raised when a secret is not found."""
    pass


class SecretEncryptionError(Exception):
    """Raised when secret encryption/decryption fails."""
    pass


class SecretManager:
    """Manages encrypted secrets with file-based storage."""
    
    def __init__(
        self,
        secrets_file: Union[str, Path] = "secrets.enc",
        master_key: Optional[str] = None,
        salt: Optional[bytes] = None
    ):
        """Initialize the secret manager.
        
        Args:
            secrets_file: Path to the encrypted secrets file
            master_key: Master key for encryption (from env if not provided)
            salt: Salt for key derivation (generated if not provided)
        """
        self.secrets_file = Path(secrets_file)
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Get or generate master key
        if master_key is None:
            master_key = os.getenv("SECRETS_MASTER_KEY")
            if not master_key:
                master_key = self._generate_master_key()
                logger.warning(
                    "No master key provided. Generated new key. "
                    "Set SECRETS_MASTER_KEY environment variable to persist."
                )
        
        # Get or generate salt
        if salt is None:
            salt = self._load_or_generate_salt()
        
        self.master_key = master_key
        self.salt = salt
        self._fernet = self._create_fernet()
        
        # Load existing secrets
        self._secrets: Dict[str, Any] = self._load_secrets()
        
        # Audit log
        self._audit_log: List[Dict[str, Any]] = []
    
    def _generate_master_key(self) -> str:
        """Generate a new master key."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    
    def _load_or_generate_salt(self) -> bytes:
        """Load existing salt or generate new one."""
        salt_file = self.secrets_file.with_suffix('.salt')
        
        if salt_file.exists():
            try:
                with open(salt_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to load salt file: {e}")
        
        # Generate new salt
        salt = os.urandom(16)
        try:
            with open(salt_file, 'wb') as f:
                f.write(salt)
        except Exception as e:
            logger.warning(f"Failed to save salt file: {e}")
        
        return salt
    
    def _create_fernet(self) -> Fernet:
        """Create Fernet cipher from master key and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)
    
    def _load_secrets(self) -> Dict[str, Any]:
        """Load and decrypt secrets from file."""
        if not self.secrets_file.exists():
            return {}
        
        try:
            with open(self.secrets_file, 'rb') as f:
                encrypted_data = f.read()
            
            if not encrypted_data:
                return {}
            
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
            raise SecretEncryptionError(f"Failed to decrypt secrets: {e}")
    
    def _save_secrets(self) -> None:
        """Encrypt and save secrets to file."""
        try:
            data = json.dumps(self._secrets, indent=2).encode()
            encrypted_data = self._fernet.encrypt(data)
            
            # Atomic write
            temp_file = self.secrets_file.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                f.write(encrypted_data)
            
            temp_file.replace(self.secrets_file)
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise SecretEncryptionError(f"Failed to encrypt secrets: {e}")
    
    def _log_access(self, action: str, key: str, success: bool = True) -> None:
        """Log secret access for auditing."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "key": key,
            "success": success
        }
        self._audit_log.append(log_entry)
        
        # Keep only last 1000 entries
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]
    
    def set_secret(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Set a secret value.
        
        Args:
            key: Secret key
            value: Secret value
            metadata: Optional metadata (expiration, description, etc.)
        """
        secret_data = {
            "value": value,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        self._secrets[key] = secret_data
        self._save_secrets()
        self._log_access("set", key)
        
        logger.info(f"Secret '{key}' has been set")
    
    def get_secret(
        self,
        key: str,
        default: Any = None,
        fallback_env: bool = True
    ) -> Any:
        """Get a secret value.
        
        Args:
            key: Secret key
            default: Default value if secret not found
            fallback_env: Whether to check environment variables as fallback
        
        Returns:
            Secret value or default
        """
        try:
            # Check encrypted secrets first
            if key in self._secrets:
                secret_data = self._secrets[key]
                
                # Check expiration
                if self._is_expired(secret_data):
                    logger.warning(f"Secret '{key}' has expired")
                    self._log_access("get", key, success=False)
                    if default is not None:
                        return default
                    raise SecretNotFoundError(f"Secret '{key}' has expired")
                
                self._log_access("get", key)
                return secret_data["value"]
            
            # Fallback to environment variable
            if fallback_env:
                env_value = os.getenv(key)
                if env_value is not None:
                    self._log_access("get_env", key)
                    return env_value
            
            # Not found
            self._log_access("get", key, success=False)
            if default is not None:
                return default
            
            raise SecretNotFoundError(f"Secret '{key}' not found")
        
        except SecretNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get secret '{key}': {e}")
            self._log_access("get", key, success=False)
            if default is not None:
                return default
            raise
    
    def delete_secret(self, key: str) -> bool:
        """Delete a secret.
        
        Args:
            key: Secret key
        
        Returns:
            True if secret was deleted, False if not found
        """
        if key in self._secrets:
            del self._secrets[key]
            self._save_secrets()
            self._log_access("delete", key)
            logger.info(f"Secret '{key}' has been deleted")
            return True
        
        self._log_access("delete", key, success=False)
        return False
    
    def list_secrets(self, include_metadata: bool = False) -> Dict[str, Any]:
        """List all secret keys and optionally their metadata.
        
        Args:
            include_metadata: Whether to include metadata
        
        Returns:
            Dictionary of secret keys and metadata
        """
        result = {}
        
        for key, secret_data in self._secrets.items():
            if include_metadata:
                result[key] = {
                    "created_at": secret_data["created_at"],
                    "metadata": secret_data["metadata"],
                    "expired": self._is_expired(secret_data)
                }
            else:
                result[key] = {
                    "exists": True,
                    "expired": self._is_expired(secret_data)
                }
        
        self._log_access("list", "*")
        return result
    
    def rotate_secret(self, key: str, new_value: Any) -> None:
        """Rotate a secret by updating its value.
        
        Args:
            key: Secret key
            new_value: New secret value
        """
        if key not in self._secrets:
            raise SecretNotFoundError(f"Secret '{key}' not found")
        
        # Keep old value in metadata for rollback
        old_data = self._secrets[key]
        metadata = old_data["metadata"].copy()
        metadata["previous_value"] = old_data["value"]
        metadata["rotated_at"] = datetime.utcnow().isoformat()
        
        self.set_secret(key, new_value, metadata)
        self._log_access("rotate", key)
        
        logger.info(f"Secret '{key}' has been rotated")
    
    def _is_expired(self, secret_data: Dict[str, Any]) -> bool:
        """Check if a secret has expired."""
        metadata = secret_data.get("metadata", {})
        expires_at = metadata.get("expires_at")
        
        if not expires_at:
            return False
        
        try:
            expiry_date = datetime.fromisoformat(expires_at)
            return datetime.utcnow() > expiry_date
        except (ValueError, TypeError):
            return False
    
    def cleanup_expired(self) -> int:
        """Remove expired secrets.
        
        Returns:
            Number of secrets removed
        """
        expired_keys = [
            key for key, secret_data in self._secrets.items()
            if self._is_expired(secret_data)
        ]
        
        for key in expired_keys:
            del self._secrets[key]
            self._log_access("cleanup", key)
        
        if expired_keys:
            self._save_secrets()
            logger.info(f"Cleaned up {len(expired_keys)} expired secrets")
        
        return len(expired_keys)
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit log entries.
        
        Args:
            limit: Maximum number of entries to return
        
        Returns:
            List of audit log entries
        """
        return self._audit_log[-limit:]
    
    def export_secrets(self, include_values: bool = False) -> Dict[str, Any]:
        """Export secrets for backup or migration.
        
        Args:
            include_values: Whether to include secret values (dangerous!)
        
        Returns:
            Exported secrets data
        """
        export_data = {
            "exported_at": datetime.utcnow().isoformat(),
            "secrets": {}
        }
        
        for key, secret_data in self._secrets.items():
            if include_values:
                export_data["secrets"][key] = secret_data
            else:
                export_data["secrets"][key] = {
                    "created_at": secret_data["created_at"],
                    "metadata": secret_data["metadata"]
                }
        
        self._log_access("export", "*")
        return export_data
    
    def import_secrets(self, secrets_data: Dict[str, Any], overwrite: bool = False) -> int:
        """Import secrets from exported data.
        
        Args:
            secrets_data: Exported secrets data
            overwrite: Whether to overwrite existing secrets
        
        Returns:
            Number of secrets imported
        """
        imported_count = 0
        secrets = secrets_data.get("secrets", {})
        
        for key, secret_data in secrets.items():
            if key in self._secrets and not overwrite:
                logger.warning(f"Secret '{key}' already exists, skipping")
                continue
            
            self._secrets[key] = secret_data
            imported_count += 1
            self._log_access("import", key)
        
        if imported_count > 0:
            self._save_secrets()
            logger.info(f"Imported {imported_count} secrets")
        
        return imported_count


# Global secret manager instance
_secret_manager: Optional[SecretManager] = None


def get_secret_manager(
    secrets_file: Optional[Union[str, Path]] = None,
    master_key: Optional[str] = None
) -> SecretManager:
    """Get the global secret manager instance."""
    global _secret_manager
    
    if _secret_manager is None:
        secrets_file = secrets_file or os.getenv("SECRETS_FILE", "secrets.enc")
        _secret_manager = SecretManager(secrets_file, master_key)
    
    return _secret_manager


def get_secret(key: str, default: Any = None, fallback_env: bool = True) -> Any:
    """Convenience function to get a secret."""
    manager = get_secret_manager()
    return manager.get_secret(key, default, fallback_env)


def set_secret(key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Convenience function to set a secret."""
    manager = get_secret_manager()
    manager.set_secret(key, value, metadata)


def delete_secret(key: str) -> bool:
    """Convenience function to delete a secret."""
    manager = get_secret_manager()
    return manager.delete_secret(key)


def list_secrets(include_metadata: bool = False) -> Dict[str, Any]:
    """Convenience function to list secrets."""
    manager = get_secret_manager()
    return manager.list_secrets(include_metadata)