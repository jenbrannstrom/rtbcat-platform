"""Encrypted configuration management for RTBcat.

This module provides secure storage and retrieval of credentials
using Fernet symmetric encryption. Configuration is stored in
~/.catscan/ directory.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field, SecretStr

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration operations fail."""

    pass


class AuthorizedBuyersConfig(BaseModel):
    """Google Authorized Buyers RTB API configuration."""

    service_account_path: str
    account_id: str


class S3Config(BaseModel):
    """S3 storage configuration."""

    bucket_name: str
    region: str = "us-east-1"
    access_key_id: SecretStr
    secret_access_key: SecretStr
    endpoint_url: Optional[str] = None


class S3ArchiveConfig(BaseModel):
    """S3 archive configuration for CSV backup."""

    bucket: str = "rtbcat-csv-archive-frankfurt-328614522524"
    region: str = "eu-central-1"
    compress: bool = True
    enabled: bool = True


class RetentionConfig(BaseModel):
    """Data retention configuration."""

    database_days: int = 90  # Days to keep in SQLite
    archive_enabled: bool = True  # Archive to S3 before cleanup


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: str = Field(default="~/.catscan/catscan.db")
    echo: bool = False


class AppConfig(BaseModel):
    """Application configuration."""

    authorized_buyers: Optional[AuthorizedBuyersConfig] = None
    s3: Optional[S3Config] = None
    s3_archive: S3ArchiveConfig = Field(default_factory=S3ArchiveConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000


class ConfigManager:
    """Manages encrypted configuration storage.

    Configuration is stored in ~/.catscan/ with encryption keys
    managed separately for security.

    Attributes:
        config_dir: Path to the configuration directory.
    """

    DEFAULT_CONFIG_DIR = Path.home() / ".catscan"
    CONFIG_FILE = "config.enc"
    KEY_FILE = ".key"

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """Initialize the configuration manager.

        Args:
            config_dir: Custom configuration directory path.
        """
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self._fernet: Optional[Fernet] = None
        self._config: Optional[AppConfig] = None

    def _ensure_config_dir(self) -> None:
        """Create the configuration directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions on config directory
        os.chmod(self.config_dir, 0o700)

    @property
    def key_path(self) -> Path:
        """Path to the encryption key file."""
        return self.config_dir / self.KEY_FILE

    @property
    def config_path(self) -> Path:
        """Path to the encrypted configuration file."""
        return self.config_dir / self.CONFIG_FILE

    def _get_or_create_key(self) -> bytes:
        """Get existing encryption key or create a new one.

        Returns:
            The Fernet encryption key bytes.
        """
        self._ensure_config_dir()

        if self.key_path.exists():
            key = self.key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            # Set restrictive permissions on key file
            os.chmod(self.key_path, 0o600)
            logger.info(f"Generated new encryption key at {self.key_path}")

        return key

    def _get_fernet(self) -> Fernet:
        """Get or create the Fernet cipher instance."""
        if self._fernet is None:
            key = self._get_or_create_key()
            self._fernet = Fernet(key)
        return self._fernet

    def _encrypt(self, data: str) -> bytes:
        """Encrypt a string using Fernet.

        Args:
            data: The plaintext data to encrypt.

        Returns:
            Encrypted bytes.
        """
        fernet = self._get_fernet()
        return fernet.encrypt(data.encode("utf-8"))

    def _decrypt(self, data: bytes) -> str:
        """Decrypt Fernet-encrypted bytes.

        Args:
            data: The encrypted data.

        Returns:
            Decrypted string.

        Raises:
            ConfigError: If decryption fails.
        """
        fernet = self._get_fernet()
        try:
            return fernet.decrypt(data).decode("utf-8")
        except InvalidToken as e:
            raise ConfigError("Failed to decrypt configuration. Invalid key.") from e

    def _serialize_config(self, config: AppConfig) -> str:
        """Serialize configuration to JSON, exposing secrets.

        Args:
            config: The configuration to serialize.

        Returns:
            JSON string representation.
        """
        data = config.model_dump()
        # Convert SecretStr to plain strings for storage
        self._expose_secrets(data)
        return json.dumps(data, indent=2)

    def _expose_secrets(self, data: dict) -> None:
        """Recursively expose SecretStr values in a dict."""
        for key, value in data.items():
            if isinstance(value, dict):
                self._expose_secrets(value)
            elif hasattr(value, "get_secret_value"):
                data[key] = value.get_secret_value()

    def save(self, config: AppConfig) -> None:
        """Save configuration to encrypted storage.

        Args:
            config: The configuration to save.

        Raises:
            ConfigError: If save operation fails.
        """
        self._ensure_config_dir()

        try:
            serialized = self._serialize_config(config)
            encrypted = self._encrypt(serialized)
            self.config_path.write_bytes(encrypted)
            os.chmod(self.config_path, 0o600)
            self._config = config
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            raise ConfigError(f"Failed to save configuration: {e}") from e

    def load(self) -> AppConfig:
        """Load configuration from encrypted storage.

        Returns:
            The loaded AppConfig.

        Raises:
            ConfigError: If configuration doesn't exist or can't be loaded.
        """
        if not self.config_path.exists():
            raise ConfigError(
                f"Configuration not found at {self.config_path}. "
                "Run 'catscan configure' to set up."
            )

        try:
            encrypted = self.config_path.read_bytes()
            decrypted = self._decrypt(encrypted)
            data = json.loads(decrypted)
            self._config = AppConfig(**data)
            return self._config
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid configuration format: {e}") from e
        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}") from e

    def get_config(self) -> AppConfig:
        """Get the current configuration, loading if necessary.

        Returns:
            The current AppConfig.
        """
        if self._config is None:
            self._config = self.load()
        return self._config

    def update(self, **kwargs: Any) -> AppConfig:
        """Update specific configuration values.

        Args:
            **kwargs: Configuration fields to update.

        Returns:
            The updated AppConfig.
        """
        config = self.get_config()
        config_dict = config.model_dump()

        for key, value in kwargs.items():
            if key in config_dict:
                config_dict[key] = value

        new_config = AppConfig(**config_dict)
        self.save(new_config)
        return new_config

    def get_service_account_path(self) -> Path:
        """Get the path to the service account credentials file.

        Returns:
            Path to the service account JSON file.

        Raises:
            ConfigError: If Authorized Buyers config is not set.
        """
        config = self.get_config()

        if not config.authorized_buyers:
            raise ConfigError("Authorized Buyers configuration not set")

        return Path(config.authorized_buyers.service_account_path).expanduser()

    def is_configured(self) -> bool:
        """Check if configuration exists.

        Returns:
            True if configuration file exists.
        """
        return self.config_path.exists()

    def reset(self) -> None:
        """Delete all configuration files.

        Warning: This will delete the encryption key and all stored credentials.
        """
        if self.config_path.exists():
            self.config_path.unlink()
        if self.key_path.exists():
            self.key_path.unlink()
        self._config = None
        self._fernet = None
        logger.info("Configuration reset complete")
