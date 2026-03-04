"""Centralized configuration management for SDD server.

This module provides a unified configuration system that supports:
- Environment variables (highest priority)
- Configuration files (YAML/JSON)
- Default values (lowest priority)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)

# Default paths
DEFAULT_CONFIG_DIR = Path.home() / ".sdd"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
ENV_PREFIX = "SDD_"


class LogLevel(StrEnum):
    """Log levels for the application."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(StrEnum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class ServerConfig:
    """Configuration for the SDD MCP server."""

    host: str = "localhost"
    port: int = 8000
    debug: bool = False
    workers: int = 1
    timeout_seconds: float = 300.0

    @classmethod
    def from_env(cls) -> ServerConfig:
        """Load server configuration from environment variables."""
        return cls(
            host=os.getenv(f"{ENV_PREFIX}HOST", cls.host),
            port=int(os.getenv(f"{ENV_PREFIX}PORT", str(cls.port))),
            debug=os.getenv(f"{ENV_PREFIX}DEBUG", "false").lower() == "true",
            workers=int(os.getenv(f"{ENV_PREFIX}WORKERS", str(cls.workers))),
            timeout_seconds=float(os.getenv(f"{ENV_PREFIX}TIMEOUT", str(cls.timeout_seconds))),
        )


@dataclass
class RetrySettings:
    """Retry configuration settings."""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

    @classmethod
    def from_env(cls) -> RetrySettings:
        """Load retry settings from environment variables."""
        return cls(
            max_retries=int(os.getenv(f"{ENV_PREFIX}RETRY_MAX", str(cls.max_retries))),
            initial_delay=float(
                os.getenv(f"{ENV_PREFIX}RETRY_INITIAL_DELAY", str(cls.initial_delay))
            ),
            max_delay=float(os.getenv(f"{ENV_PREFIX}RETRY_MAX_DELAY", str(cls.max_delay))),
            exponential_base=float(os.getenv(f"{ENV_PREFIX}RETRY_BASE", str(cls.exponential_base))),
            jitter=os.getenv(f"{ENV_PREFIX}RETRY_JITTER", "true").lower() == "true",
        )


@dataclass
class ExecutionConfig:
    """Configuration for role execution pipeline."""

    max_parallel_roles: int = 3
    role_timeout_seconds: float = 600.0
    enable_streaming: bool = True
    failure_strategy: str = "continue_on_failure"
    retry: RetrySettings = field(default_factory=RetrySettings)

    @classmethod
    def from_env(cls) -> ExecutionConfig:
        """Load execution configuration from environment variables."""
        return cls(
            max_parallel_roles=int(
                os.getenv(f"{ENV_PREFIX}MAX_PARALLEL", str(cls.max_parallel_roles))
            ),
            role_timeout_seconds=float(
                os.getenv(f"{ENV_PREFIX}ROLE_TIMEOUT", str(cls.role_timeout_seconds))
            ),
            enable_streaming=os.getenv(f"{ENV_PREFIX}STREAMING", str(cls.enable_streaming).lower())
            == "true",
            failure_strategy=os.getenv(f"{ENV_PREFIX}FAILURE_STRATEGY", cls.failure_strategy),
            retry=RetrySettings.from_env(),
        )


@dataclass
class PluginConfig:
    """Configuration for plugin system."""

    discovery_paths: list[str] = field(default_factory=lambda: ["sdd_server.plugins"])
    enabled_plugins: list[str] = field(default_factory=list)
    disabled_plugins: list[str] = field(default_factory=list)
    custom_plugin_dir: str | None = None
    auto_discover: bool = True

    @classmethod
    def from_env(cls) -> PluginConfig:
        """Load plugin configuration from environment variables."""
        paths = os.getenv(f"{ENV_PREFIX}PLUGIN_PATHS", "")
        enabled = os.getenv(f"{ENV_PREFIX}ENABLED_PLUGINS", "")
        disabled = os.getenv(f"{ENV_PREFIX}DISABLED_PLUGINS", "")
        default = cls()

        return cls(
            discovery_paths=paths.split(",") if paths else default.discovery_paths,
            enabled_plugins=enabled.split(",") if enabled else [],
            disabled_plugins=disabled.split(",") if disabled else [],
            custom_plugin_dir=os.getenv(f"{ENV_PREFIX}CUSTOM_PLUGIN_DIR"),
            auto_discover=os.getenv(f"{ENV_PREFIX}AUTO_DISCOVER", "true").lower() == "true",
        )


@dataclass
class LoggingConfig:
    """Configuration for logging system."""

    level: LogLevel = LogLevel.INFO
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    output: str = "stderr"
    include_timestamp: bool = True
    include_correlation_id: bool = True
    json_format: bool = False

    @classmethod
    def from_env(cls) -> LoggingConfig:
        """Load logging configuration from environment variables."""
        level_str = os.getenv(f"{ENV_PREFIX}LOG_LEVEL", cls.level.value).upper()
        try:
            level = LogLevel(level_str)
        except ValueError:
            level = cls.level
            logger.warning(f"Invalid log level '{level_str}', using default: {level}")

        return cls(
            level=level,
            format=os.getenv(f"{ENV_PREFIX}LOG_FORMAT", cls.format),
            output=os.getenv(f"{ENV_PREFIX}LOG_OUTPUT", cls.output),
            include_timestamp=os.getenv(
                f"{ENV_PREFIX}LOG_TIMESTAMP", str(cls.include_timestamp).lower()
            )
            == "true",
            include_correlation_id=os.getenv(
                f"{ENV_PREFIX}LOG_CORRELATION", str(cls.include_correlation_id).lower()
            )
            == "true",
            json_format=os.getenv(f"{ENV_PREFIX}LOG_JSON", "false").lower() == "true",
        )


@dataclass
class RateLimitSettings:
    """Rate limiting configuration."""

    requests_per_window: int = 100
    window_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> RateLimitSettings:
        """Load rate limit settings from environment variables."""
        return cls(
            requests_per_window=int(
                os.getenv(
                    f"{ENV_PREFIX}RATE_LIMIT_REQUESTS",
                    str(cls.requests_per_window),
                )
            ),
            window_seconds=float(
                os.getenv(f"{ENV_PREFIX}RATE_LIMIT_WINDOW", str(cls.window_seconds))
            ),
        )


@dataclass
class SecurityConfig:
    """Configuration for security features."""

    rate_limit: RateLimitSettings = field(default_factory=RateLimitSettings)
    max_request_size: int = 10 * 1024 * 1024  # 10 MB
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    enable_input_validation: bool = True
    enable_path_traversal_protection: bool = True

    @classmethod
    def from_env(cls) -> SecurityConfig:
        """Load security configuration from environment variables."""
        origins = os.getenv(f"{ENV_PREFIX}ALLOWED_ORIGINS", "*")

        return cls(
            rate_limit=RateLimitSettings.from_env(),
            max_request_size=int(
                os.getenv(f"{ENV_PREFIX}MAX_REQUEST_SIZE", str(cls.max_request_size))
            ),
            allowed_origins=origins.split(","),
            enable_input_validation=os.getenv(f"{ENV_PREFIX}INPUT_VALIDATION", "true").lower()
            == "true",
            enable_path_traversal_protection=os.getenv(
                f"{ENV_PREFIX}PATH_TRAVERSAL_PROTECTION", "true"
            ).lower()
            == "true",
        )


@dataclass
class MetricsSettings:
    """Metrics collection configuration."""

    prefix: str = "sdd"
    enable_default_metrics: bool = True

    @classmethod
    def from_env(cls) -> MetricsSettings:
        """Load metrics settings from environment variables."""
        return cls(
            prefix=os.getenv(f"{ENV_PREFIX}METRICS_PREFIX", cls.prefix),
            enable_default_metrics=os.getenv(f"{ENV_PREFIX}METRICS_DEFAULT", "true").lower()
            == "true",
        )


@dataclass
class HealthCheckSettings:
    """Health check configuration."""

    check_interval: float = 30.0

    @classmethod
    def from_env(cls) -> HealthCheckSettings:
        """Load health check settings from environment variables."""
        return cls(
            check_interval=float(
                os.getenv(f"{ENV_PREFIX}HEALTH_INTERVAL", str(cls.check_interval))
            ),
        )


@dataclass
class AuditSettings:
    """Audit logging configuration."""

    enabled: bool = True
    file_path: str | None = None

    @classmethod
    def from_env(cls) -> AuditSettings:
        """Load audit settings from environment variables."""
        return cls(
            enabled=os.getenv(f"{ENV_PREFIX}AUDIT_ENABLED", "true").lower() == "true",
            file_path=os.getenv(f"{ENV_PREFIX}AUDIT_FILE"),
        )


@dataclass
class ObservabilityConfig:
    """Configuration for observability features."""

    metrics: MetricsSettings = field(default_factory=MetricsSettings)
    health: HealthCheckSettings = field(default_factory=HealthCheckSettings)
    audit: AuditSettings = field(default_factory=AuditSettings)
    enable_tracing: bool = False

    @classmethod
    def from_env(cls) -> ObservabilityConfig:
        """Load observability configuration from environment variables."""
        return cls(
            metrics=MetricsSettings.from_env(),
            health=HealthCheckSettings.from_env(),
            audit=AuditSettings.from_env(),
            enable_tracing=os.getenv(f"{ENV_PREFIX}TRACING", "false").lower() == "true",
        )


@dataclass
class SDDConfig:
    """Main configuration class aggregating all configuration sections.

    Configuration priority:
    1. Environment variables (highest)
    2. Configuration file (YAML/JSON)
    3. Default values (lowest)
    """

    environment: Environment = Environment.DEVELOPMENT
    server: ServerConfig = field(default_factory=ServerConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    @classmethod
    def from_env(cls) -> SDDConfig:
        """Load all configuration from environment variables."""
        env_str = os.getenv(f"{ENV_PREFIX}ENV", cls.environment.value).lower()
        try:
            environment = Environment(env_str)
        except ValueError:
            environment = cls.environment
            logger.warning(f"Invalid environment '{env_str}', using default: {environment}")

        return cls(
            environment=environment,
            server=ServerConfig.from_env(),
            execution=ExecutionConfig.from_env(),
            plugins=PluginConfig.from_env(),
            logging=LoggingConfig.from_env(),
            security=SecurityConfig.from_env(),
            observability=ObservabilityConfig.from_env(),
        )

    @classmethod
    def from_file(cls, path: Path) -> SDDConfig:
        """Load configuration from a YAML or JSON file."""
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        content = path.read_text()

        if path.suffix in (".yaml", ".yml"):
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in config file: {e}") from e
        elif path.suffix == ".json":
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in config file: {e}") from e
        else:
            raise ValueError(f"Unsupported config file format: {path.suffix}")

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> SDDConfig:
        """Create configuration from dictionary."""
        env_str = data.get("environment", cls.environment.value)
        try:
            environment = Environment(env_str)
        except ValueError:
            environment = cls.environment

        server_data = data.get("server", {})
        execution_data = data.get("execution", {})
        plugins_data = data.get("plugins", {})
        logging_data = data.get("logging", {})
        security_data = data.get("security", {})
        observability_data = data.get("observability", {})

        # Handle nested configs
        retry_data = execution_data.get("retry", {})
        retry_settings = RetrySettings(**retry_data) if retry_data else RetrySettings()

        rate_limit_data = security_data.get("rate_limit", {})
        rate_limit_settings = (
            RateLimitSettings(**rate_limit_data) if rate_limit_data else RateLimitSettings()
        )

        # Parse log level
        level_str = logging_data.get("level", LogLevel.INFO.value)
        try:
            log_level = LogLevel(level_str)
        except ValueError:
            log_level = LogLevel.INFO

        # Get defaults from fresh instances
        default_execution = ExecutionConfig()
        default_logging = LoggingConfig()
        default_security = SecurityConfig()
        default_observability = ObservabilityConfig()

        return cls(
            environment=environment,
            server=ServerConfig(**server_data) if server_data else ServerConfig(),
            execution=ExecutionConfig(
                max_parallel_roles=execution_data.get(
                    "max_parallel_roles", default_execution.max_parallel_roles
                ),
                role_timeout_seconds=execution_data.get(
                    "role_timeout_seconds", default_execution.role_timeout_seconds
                ),
                enable_streaming=execution_data.get(
                    "enable_streaming", default_execution.enable_streaming
                ),
                failure_strategy=execution_data.get(
                    "failure_strategy", default_execution.failure_strategy
                ),
                retry=retry_settings,
            ),
            plugins=PluginConfig(**plugins_data) if plugins_data else PluginConfig(),
            logging=LoggingConfig(
                level=log_level,
                format=logging_data.get("format", default_logging.format),
                output=logging_data.get("output", default_logging.output),
                include_timestamp=logging_data.get(
                    "include_timestamp", default_logging.include_timestamp
                ),
                include_correlation_id=logging_data.get(
                    "include_correlation_id", default_logging.include_correlation_id
                ),
                json_format=logging_data.get("json_format", default_logging.json_format),
            ),
            security=SecurityConfig(
                rate_limit=rate_limit_settings,
                max_request_size=security_data.get(
                    "max_request_size", default_security.max_request_size
                ),
                allowed_origins=security_data.get(
                    "allowed_origins", default_security.allowed_origins
                ),
                enable_input_validation=security_data.get(
                    "enable_input_validation", default_security.enable_input_validation
                ),
                enable_path_traversal_protection=security_data.get(
                    "enable_path_traversal_protection",
                    default_security.enable_path_traversal_protection,
                ),
            ),
            observability=ObservabilityConfig(
                metrics=MetricsSettings(**observability_data.get("metrics", {}))
                if observability_data.get("metrics")
                else MetricsSettings(),
                health=HealthCheckSettings(**observability_data.get("health", {}))
                if observability_data.get("health")
                else HealthCheckSettings(),
                audit=AuditSettings(**observability_data.get("audit", {}))
                if observability_data.get("audit")
                else AuditSettings(),
                enable_tracing=observability_data.get(
                    "enable_tracing", default_observability.enable_tracing
                ),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary representation."""
        return {
            "environment": self.environment.value,
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "debug": self.server.debug,
                "workers": self.server.workers,
                "timeout_seconds": self.server.timeout_seconds,
            },
            "execution": {
                "max_parallel_roles": self.execution.max_parallel_roles,
                "role_timeout_seconds": self.execution.role_timeout_seconds,
                "enable_streaming": self.execution.enable_streaming,
                "failure_strategy": self.execution.failure_strategy,
                "retry": {
                    "max_retries": self.execution.retry.max_retries,
                    "initial_delay": self.execution.retry.initial_delay,
                    "max_delay": self.execution.retry.max_delay,
                    "exponential_base": self.execution.retry.exponential_base,
                    "jitter": self.execution.retry.jitter,
                },
            },
            "plugins": {
                "discovery_paths": self.plugins.discovery_paths,
                "enabled_plugins": self.plugins.enabled_plugins,
                "disabled_plugins": self.plugins.disabled_plugins,
                "custom_plugin_dir": self.plugins.custom_plugin_dir,
                "auto_discover": self.plugins.auto_discover,
            },
            "logging": {
                "level": self.logging.level.value,
                "format": self.logging.format,
                "output": self.logging.output,
                "include_timestamp": self.logging.include_timestamp,
                "include_correlation_id": self.logging.include_correlation_id,
                "json_format": self.logging.json_format,
            },
            "security": {
                "rate_limit": {
                    "requests_per_window": self.security.rate_limit.requests_per_window,
                    "window_seconds": self.security.rate_limit.window_seconds,
                },
                "max_request_size": self.security.max_request_size,
                "allowed_origins": self.security.allowed_origins,
                "enable_input_validation": self.security.enable_input_validation,
                "enable_path_traversal_protection": self.security.enable_path_traversal_protection,
            },
            "observability": {
                "metrics": {
                    "prefix": self.observability.metrics.prefix,
                    "enable_default_metrics": self.observability.metrics.enable_default_metrics,
                },
                "health": {
                    "check_interval": self.observability.health.check_interval,
                },
                "audit": {
                    "enabled": self.observability.audit.enabled,
                    "file_path": self.observability.audit.file_path,
                },
                "enable_tracing": self.observability.enable_tracing,
            },
        }

    def save(self, path: Path) -> None:
        """Save configuration to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()

        if path.suffix in (".yaml", ".yml"):
            content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        else:
            content = json.dumps(data, indent=2)

        path.write_text(content)
        logger.info(f"Configuration saved to {path}")


@lru_cache(maxsize=1)
def get_config() -> SDDConfig:
    """Get the global configuration instance.

    Configuration is loaded from:
    1. Environment variables (highest priority)
    2. Configuration file at DEFAULT_CONFIG_FILE (if exists)
    3. Default values (lowest priority)
    """
    SDDConfig()

    # Try to load from file first
    if DEFAULT_CONFIG_FILE.exists():
        try:
            SDDConfig.from_file(DEFAULT_CONFIG_FILE)
            logger.debug(f"Loaded configuration from {DEFAULT_CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load config file: {e}")

    # Merge environment variables (highest priority)
    env_config = SDDConfig.from_env()

    # Return env config (env has highest priority)
    return env_config


def reload_config() -> SDDConfig:
    """Reload configuration from sources.

    Clears the cache and reloads configuration.
    """
    get_config.cache_clear()
    return get_config()
