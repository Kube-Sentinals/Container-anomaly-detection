import os
import yaml
from typing import Dict, Any, Optional
from .vault_config import VaultConfig, VaultError

class ConfigManager:
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize configuration manager."""
        self.config_path = config_path
        self.vault = VaultConfig()
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load config file: {str(e)}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value, resolving Vault references."""
        try:
            value = self.config.get(key, default)
            if isinstance(value, str) and value.startswith('vault://'):
                # Extract secret path from vault://path/to/secret
                secret_path = value[7:]  # Remove 'vault://' prefix
                return self.vault.get_secret(secret_path)
            return value
        except Exception as e:
            raise ValueError(f"Failed to get config value for {key}: {str(e)}")

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values, resolving Vault references."""
        result = {}
        for key in self.config:
            try:
                result[key] = self.get(key)
            except Exception as e:
                raise ValueError(f"Failed to get config value for {key}: {str(e)}")
        return result

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self.config[key] = value
        self._save_config()

    def _save_config(self) -> None:
        """Save configuration to YAML file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f)
        except Exception as e:
            raise ValueError(f"Failed to save config file: {str(e)}")

    def validate(self) -> bool:
        """Validate configuration values."""
        required_keys = [
            'aws.region',
            'aws.s3.bucket',
            'splunk.index',
            'model.parameters'
        ]
        
        for key in required_keys:
            if not self._get_nested(self.config, key.split('.')):
                raise ValueError(f"Missing required configuration: {key}")
        return True

    def _get_nested(self, d: Dict[str, Any], keys: list) -> Any:
        """Get nested dictionary value using dot notation."""
        for key in keys:
            if not isinstance(d, dict):
                return None
            d = d.get(key)
        return d

    def get_model_config(self) -> Dict[str, Any]:
        """Get model-specific configuration."""
        return self.get('model', {})

    def get_aws_config(self) -> Dict[str, Any]:
        """Get AWS-specific configuration."""
        return self.get('aws', {})

    def get_splunk_config(self) -> Dict[str, Any]:
        """Get Splunk-specific configuration."""
        return self.get('splunk', {})

    def get_lambda_config(self) -> Dict[str, Any]:
        """Get Lambda-specific configuration."""
        return self.get('lambda', {}) 