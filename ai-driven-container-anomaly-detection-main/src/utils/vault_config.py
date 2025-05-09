import os
import hvac
import logging
from typing import Dict, Any, Optional
from functools import lru_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VaultError(Exception):
    """Custom exception for Vault-related errors."""
    pass

class VaultConfig:
    def __init__(self):
        """Initialize Vault client with environment variables."""
        self._validate_environment()
        self.client = self._create_client()
        self.secret_path = os.getenv('VAULT_SECRET_PATH', 'secret/container-anomaly-detection')
        logger.info(f"Initialized VaultConfig with secret path: {self.secret_path}")

    def _validate_environment(self):
        """Validate required environment variables."""
        required_vars = ['VAULT_URL', 'VAULT_TOKEN']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise VaultError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _create_client(self) -> hvac.Client:
        """Create and validate Vault client."""
        try:
            client = hvac.Client(
                url=os.getenv('VAULT_URL'),
                token=os.getenv('VAULT_TOKEN'),
                verify=os.getenv('VAULT_VERIFY_SSL', 'True').lower() == 'true'
            )
            # Test connection
            if not client.is_authenticated():
                raise VaultError("Failed to authenticate with Vault")
            return client
        except Exception as e:
            raise VaultError(f"Failed to create Vault client: {str(e)}")

    @lru_cache(maxsize=100)
    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret from Vault with caching."""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=self.secret_path
            )
            value = response['data']['data'].get(key)
            if value is None:
                logger.warning(f"Secret key '{key}' not found in Vault")
            return value
        except Exception as e:
            logger.error(f"Error retrieving secret {key} from Vault: {str(e)}")
            raise VaultError(f"Failed to retrieve secret {key}: {str(e)}")

    def get_all_secrets(self) -> Dict[str, Any]:
        """Retrieve all secrets from the configured path."""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=self.secret_path
            )
            return response['data']['data']
        except Exception as e:
            logger.error(f"Error retrieving secrets from Vault: {str(e)}")
            raise VaultError(f"Failed to retrieve secrets: {str(e)}")

    def set_secret(self, key: str, value: str) -> bool:
        """Set a secret in Vault."""
        try:
            current_secrets = self.get_all_secrets()
            current_secrets[key] = value
            self.client.secrets.kv.v2.create_or_update_secret(
                path=self.secret_path,
                secret=current_secrets
            )
            logger.info(f"Successfully set secret key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error setting secret {key} in Vault: {str(e)}")
            raise VaultError(f"Failed to set secret {key}: {str(e)}")

    def delete_secret(self, key: str) -> bool:
        """Delete a secret from Vault."""
        try:
            current_secrets = self.get_all_secrets()
            if key in current_secrets:
                del current_secrets[key]
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=self.secret_path,
                    secret=current_secrets
                )
                logger.info(f"Successfully deleted secret key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting secret {key} from Vault: {str(e)}")
            raise VaultError(f"Failed to delete secret {key}: {str(e)}")

    def rotate_secret(self, key: str) -> bool:
        """Rotate a secret value in Vault."""
        try:
            current_value = self.get_secret(key)
            if current_value is None:
                raise VaultError(f"Secret {key} not found")
            
            # Generate new value (implement your rotation logic here)
            new_value = self._generate_new_secret(current_value)
            
            # Update the secret
            return self.set_secret(key, new_value)
        except Exception as e:
            logger.error(f"Error rotating secret {key}: {str(e)}")
            raise VaultError(f"Failed to rotate secret {key}: {str(e)}")

    def _generate_new_secret(self, current_value: str) -> str:
        """Generate a new secret value (implement your rotation logic here)."""
        # This is a placeholder - implement your secret rotation logic
        import secrets
        return secrets.token_urlsafe(32) 