"""Configuration management for QA Intelligence Agent.

Loads configuration from YAML file and overrides with environment variables.
"""

import os
import yaml
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ServiceConfig(BaseModel):
    """Service metadata configuration."""
    name: str = "QA Intelligence Agent"
    version: str = "0.1.0"
    port: int = 8000


class TeamCityConfig(BaseModel):
    """TeamCity connection configuration."""
    url: str = ""
    token: Optional[str] = None


class WebhookConfig(BaseModel):
    """Webhook processing configuration."""
    dedup_window: int = 3600
    secret: Optional[str] = None


class ProcessingConfig(BaseModel):
    """Build processing configuration."""
    branch_filters: List[str] = Field(default_factory=lambda: ["main", "master", "release/*"])
    max_retries: int = 3
    retry_base_delay: int = 5


class StartupConfig(BaseModel):
    """Startup behavior configuration."""
    poll_lookback_builds: int = 20


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"


class SlackConfig(BaseModel):
    """Slack integration configuration."""
    webhook_url: Optional[str] = None


class Settings(BaseModel):
    """Root configuration model."""
    service: ServiceConfig = Field(default_factory=ServiceConfig)
    teamcity: TeamCityConfig = Field(default_factory=TeamCityConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    startup: StartupConfig = Field(default_factory=StartupConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)


def load_yaml_config(config_path: str) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary of configuration values
    """
    if not os.path.exists(config_path):
        logger.warning(f"Configuration file not found: {config_path}, using defaults")
        return {}

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {config_path}")
            return config
    except Exception as e:
        logger.error(f"Error loading configuration from {config_path}: {e}")
        return {}


def apply_env_overrides(config: dict) -> dict:
    """Apply environment variable overrides to configuration.

    Environment variables take precedence over YAML values.

    Args:
        config: Configuration dictionary from YAML

    Returns:
        Configuration dictionary with env var overrides applied
    """
    # Service overrides
    if port := os.getenv("SERVICE_PORT"):
        config.setdefault("service", {})["port"] = int(port)

    # TeamCity overrides
    if url := os.getenv("TEAMCITY_URL"):
        config.setdefault("teamcity", {})["url"] = url
    if token := os.getenv("TEAMCITY_TOKEN"):
        config.setdefault("teamcity", {})["token"] = token

    # Webhook overrides
    if secret := os.getenv("TEAMCITY_WEBHOOK_SECRET"):
        config.setdefault("webhook", {})["secret"] = secret

    # Slack overrides
    if webhook_url := os.getenv("SLACK_WEBHOOK_URL"):
        config.setdefault("slack", {})["webhook_url"] = webhook_url

    return config


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get configuration settings (singleton).

    Loads configuration from YAML file and applies environment variable overrides.
    Configuration is cached after first load.

    Returns:
        Settings instance
    """
    global _settings

    if _settings is not None:
        return _settings

    # Determine config file path
    config_path = os.getenv("CONFIG_PATH", "config/settings.yaml")

    # Load YAML config
    config_dict = load_yaml_config(config_path)

    # Apply environment variable overrides
    config_dict = apply_env_overrides(config_dict)

    # Create Settings instance
    _settings = Settings(**config_dict)

    # Log warnings for missing critical config
    if not _settings.teamcity.url:
        logger.warning("TEAMCITY_URL is not configured - TeamCity integration will not work")

    return _settings
